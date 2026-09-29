"""Adapt the pinned upstream main into reset/kernel/checksum entry points.

This deliberately recognizes the pinned suite's structure, not arbitrary C.
Kernel bodies, initialization formulas, types and dataset headers are retained.
Only storage duration and the benchmark driver change.
"""

from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = ROOT / 'rtems/periodic/polybench'
UPSTREAM = SUPPORT / 'upstream'
REVISION = (UPSTREAM / 'UPSTREAM_REVISION').read_text().strip()


@dataclass(frozen=True)
class Benchmark:
    """Pinned original source, with its published MEDIUM dimensions and type."""

    name: str
    source: Path
    dimensions: dict[str, int]
    element_type: str


def benchmarks() -> list[Benchmark]:
    """Return every entry in the upstream list, without analyzer exclusions."""
    result = []
    for entry in (UPSTREAM / 'utilities/benchmark_list').read_text().splitlines():
        source = UPSTREAM / entry.removeprefix('./')
        header = source.with_suffix('.h').read_text()
        medium = re.search(r'#\s*ifdef MEDIUM_DATASET(.*?)#\s*endif', header, re.S)[1]
        dimensions = {k: int(v) for k, v in re.findall(r'#\s*define (\w+)\s+(\d+)', medium)}
        default = re.search(r'#\s*define DATA_TYPE_IS_(\w+)', header)[1].lower()
        result.append(Benchmark(source.stem, source, dimensions, default))
    return result


def benchmark_named(name: str) -> Benchmark:
    """Resolve a catalog name; paths and arbitrary C fragments are not accepted."""
    for benchmark in benchmarks():
        if benchmark.name == name:
            return benchmark
    raise ValueError(f'Unknown PolyBench benchmark: {name}')


def _call(main: str, name: str) -> str:
    match = re.search(r'\b' + name + r'\s*\(', main)
    if match is None:
        raise ValueError(f'Missing upstream call: {name}')
    start, cursor, depth = match.start(), match.end(), 1
    while depth:
        depth += (main[cursor] == '(') - (main[cursor] == ')')
        cursor += 1
    return main[start:cursor] + ';'


def render(benchmark: Benchmark) -> str:
    """Keep original functions and move all benchmark arrays to named globals.

    Global storage gives RTEMS bounded stacks and YARDA ELF symbol addresses.
    Reset zeroes scratch arrays before calling the original initializer, so
    every periodic job has the same starting state as a fresh native process.
    """
    original, main = re.split(r'\bint main\s*\(int argc, char\*\* argv\)',
                              benchmark.source.read_text(), maxsplit=1)
    arrays = []

    def hoist(match):
        rank = int(match[1])
        fields = [x.strip() for x in match[2].split(',')]
        name, datatype = fields[:2]
        shape = ''.join('[' + d + ']' for d in fields[2:2 + rank])
        arrays.append((name, f'{datatype} {name}{shape} PB_STORAGE({name});'))
        return ''

    pattern = r'POLYBENCH_([123])D_ARRAY_DECL\(([^;]+)\);'
    original = re.sub(pattern, hoist, original)
    main = re.sub(pattern, hoist, main)
    if 'DATA_TYPE z[N];' in original:
        original = original.replace('DATA_TYPE z[N];', '')
        arrays.append(('z', 'DATA_TYPE z[N] PB_STORAGE(z);'))
    if len({n for n, _ in arrays}) != len(arrays):
        raise ValueError('Upstream array names need scope disambiguation')
    # Main contains only problem-size and scalar declarations before init_array.
    clean_main = re.sub(r'/\*.*?\*/', '', main, flags=re.S)
    declarations = clean_main[clean_main.index('{') + 1:clean_main.index('init_array')].strip()
    kernel = re.search(r'\b(kernel_\w+)\s*\(', main)[1]
    # Force only this function inline for the APE pass; native execution is O0.
    original = re.sub(r'void\s+' + kernel + r'\(',
                      '__attribute__((always_inline)) inline void ' + kernel + '(', original)
    header_end = original.index('static')
    storage = '\n#define y1 pb_y1\n' + '\n'.join(row for _, row in arrays) + '\n'
    original = original[:header_end] + storage + original[header_end:]
    reset = '\n'.join(f'  memset({n}, 0, sizeof({n}));' for n, _ in arrays)
    return ('/* Generated driver; original functions follow unchanged except storage. */\n'
            '#define MEDIUM_DATASET\n#define POLYBENCH_USE_SCALAR_LB\n'
            '#define POLYBENCH_STACK_ARRAYS\n#define POLYBENCH_DUMP_ARRAYS\n'
            '#include "adapter.h"\n' + original + '\n' + declarations + '\n'
            'void workload_prepare(void) {}\n'
            'void workload_reset(unsigned task) {\n  (void)task;\n' + reset + '\n  '
            + _call(main, 'init_array') + '\n}\n'
            'PB_ANALYZE uint32_t task_job_polybench(void) {\n  ' + _call(main, kernel)
            + '\n  return 0;\n}\n'
            'uint32_t workload_checksum(unsigned task) {\n  (void)task;\n'
            '  pb_hash = 2166136261u;\n  ' + _call(main, 'print_array')
            + '\n  return pb_hash;\n}\n'
            'uint32_t (*const workload_jobs[])(void) = {task_job_polybench};\n'
            '#ifndef CHASER_EXPECTED\n#define CHASER_EXPECTED 0u\n#endif\n'
            'const uint32_t workload_expected[] = {CHASER_EXPECTED};\n'
            '#ifdef CHASER_NATIVE\n'
            'int main(void) { workload_reset(0); task_job_polybench();\n'
            '  uint32_t first = workload_checksum(0); pb_emit = 0;\n'
            '  workload_reset(0); task_job_polybench();\n'
            '  if (first != workload_checksum(0)) return 1;\n'
            '  printf("%u\\n", first); return 0; }\n#endif\n')
