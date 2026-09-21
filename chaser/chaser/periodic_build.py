"""Immutable waf snapshots with shared workload objects and linked APE analysis."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from chaser.periodic import make_plan
from chaser.periodic_patterns import kernel_body, wrapper_sweeps
from tools.rtems_smoke import file_hash, write_json, check_inputs

ROOT = Path(__file__).resolve().parents[1]
SDK = Path('/opt/rtems/6')
YARDA = ROOT / 'rtems/baseline/build/yarda'


def workload_source(tasks: list[dict]) -> str:
    """Emit fixed sweep wrappers and private load-only arrays for APE and SPARC."""
    source = ['#include "workload.h"', '#ifdef __clang__',
              '#define ANALYZE __attribute__((annotate("ape.analyze")))',
              '#define INLINE __attribute__((annotate("ape.inline")))',
              '#else', '#define ANALYZE', '#define INLINE', '#endif']
    for i, task in enumerate(tasks):
        name = task['task_id']
        source.extend([
            f'volatile uint8_t data_{name}[{task["data_size"]}] '
            f'__attribute__((aligned(4096), section(".chaser_data.{i:02d}")));',
            f'INLINE static uint32_t kernel_{name}(void) {{',
            '    uint32_t sum = 0;',
            *kernel_body(task), '    return sum;', '}',
            '/** @brief Execute one fixed job without resetting data or cache.',
            ' * @return Load-count checksum, modulo 2^32. */',
            f'ANALYZE uint32_t task_job_{name}(void) {{',
            '    uint32_t sum = 0;',
            f'    for (int s = 0; s < {wrapper_sweeps(task)}; ++s)',
            f'        sum += kernel_{name}();', '    return sum;', '}'])
    source.append('void workload_prepare(void) {')
    for task in tasks:
        source.append(f'    for (int i = 0; i < {task["data_size"]}; ++i) '
                      f'data_{task["task_id"]}[i] = 1;')
    source.extend(['}', 'uint32_t (*const workload_jobs[])(void) = {'])
    source.extend(f'    task_job_{t["task_id"]},' for t in tasks)
    source.extend(['};', 'const uint32_t workload_expected[] = {',
                   ', '.join(str(t['expected_checksum']) + 'U' for t in tasks), '};'])
    return '\n'.join(source) + '\n'


def topology_header(architecture: int) -> str:
    """Configure actual EDF SMP scheduler ownership, not partial affinity masks."""
    assignments = ([0, 0, 0, 0], [0, 1, 1, 1], [0, 1, 2, 3])[architecture]
    count = max(assignments) + 1
    lines = [f'RTEMS_SCHEDULER_EDF_SMP(edf{i});' for i in range(count)]
    lines.append('#define CONFIGURE_SCHEDULER_TABLE_ENTRIES \\\n' + ', \\\n'.join(
        f"RTEMS_SCHEDULER_TABLE_EDF_SMP(edf{i}, rtems_build_name('E','D','F','{i}'))"
        for i in range(count)))
    lines.append('#define CONFIGURE_SCHEDULER_ASSIGNMENTS \\\n' + ', \\\n'.join(
        f'RTEMS_SCHEDULER_ASSIGN({i}, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY)'
        for i in assignments))
    return '\n'.join(lines) + '\n'


def read_symbols(elf: Path) -> dict[str, tuple[int, int]]:
    """Read defined symbol addresses and sizes from the installed SPARC nm."""
    output = subprocess.check_output([str(SDK / 'bin/sparc-rtems6-nm'), '-S',
                                      '--defined-only', str(elf)], text=True)
    symbols = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 4:
            symbols[parts[3]] = (int(parts[0], 16), int(parts[1], 16))
    return symbols


def check_layout(symbols: dict, tasks: list[dict]) -> list[dict]:
    """Reject any linker movement, misalignment, size change, or data overlap."""
    address = 0x01000000
    layout = []
    for task in tasks:
        name = 'data_' + task['task_id']
        if symbols.get(name) != (address, task['data_size']):
            raise ValueError(f'Workload layout mismatch: {name}')
        layout.append(dict(symbol=name, address=address, size=task['data_size'], alignment=4096))
        address += (task['data_size'] + 4095) // 4096 * 4096
    return layout


def prepare(configuration: dict, output: Path) -> dict:
    """Build all three final ELFs from a new source/config/launcher snapshot."""
    plans = [make_plan(configuration, a) for a in range(3)]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    tasks = plans[0]['tasks']
    for name in ('init.c', 'probe.c', 'probe.h'):
        shutil.copyfile(ROOT / 'rtems/periodic' / name, source / name)
    (source / 'workload.h').write_text(
        '#include <stdint.h>\n'
        '/** @brief Initialize all arrays once before workers start. @return None. */\n'
        'void workload_prepare(void);\n'
        'extern uint32_t (*const workload_jobs[])(void);\n'
        'extern const uint32_t workload_expected[];\n')
    (source / 'workload.c').write_text(workload_source(tasks))
    for name, plan in zip(('g', 'c', 'p'), plans):
        directory = output / name
        directory.mkdir()
        write_json(directory / 'plan.json', plan)
        lines = [f'#define TASK_COUNT {len(tasks)}',
                 f'#define MAX_JOBS {max(t["job_count"] for t in tasks)}',
                 f'#define ARCHITECTURE {plan["architecture"]}',
                 f'#define CHASER_CONTRACT_ID "{plan["contract_id"]}"',
                 f'#define CHASER_PLAN_HASH "{plan["plan_hash"]}"']
        for key, macro in (('period_ticks', 'PERIODS'), ('job_count', 'JOB_COUNTS'),
                           ('core', 'CORES')):
            lines.append('#define CHASER_' + macro + ' {' +
                         ', '.join(str(t[key]) for t in tasks) + '}')
        (directory / 'config.h').write_text('\n'.join(lines) + '\n')
        (directory / 'topology.h').write_text(topology_header(plan['architecture']))
    (output / 'layout.ld').write_text(
        'SECTIONS { .chaser_data 0x01000000 (NOLOAD) : {\n'
        '  KEEP(*(SORT_BY_NAME(.chaser_data.*)))\n'
        '} > ram } INSERT BEFORE .bss;\n'
        'ASSERT(SIZEOF(.chaser_data) <= 0x01000000, "workload data overflow")\n')
    shutil.copyfile(ROOT / 'rtems/periodic/wscript', output / 'wscript')
    shutil.copyfile('/opt/src/rtems/waf', output / 'waf')
    shutil.copyfile(ROOT / 'rtems/baseline/cache.yaml', output / 'cache.yaml')
    write_json(output / 'configuration.json', configuration)
    command = [sys.executable, 'waf', 'configure', 'build', '-v', f'--rtems-root={SDK}']
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
    layouts = {}
    for name in ('g', 'c', 'p'):
        layouts[name] = check_layout(read_symbols(output / f'build/{name}.exe'), tasks)
    write_json(output / 'layout.json', layouts)
    files = [*source.iterdir(), *[p for n in ('g', 'c', 'p') for p in (output / n).iterdir()],
             *[output / n for n in ('layout.ld', 'layout.json', 'wscript', 'waf',
                                     'configuration.json', 'cache.yaml', 'build.log',
                                     'build/compile_commands.json')],
             *list((output / 'build').rglob('*.o')), *list((output / 'build').glob('*.exe'))]
    sdk_files = [SDK / 'bin/sparc-rtems6-gcc',
                 SDK / 'lib/pkgconfig/sparc-rtems6-gr740.pc',
                 *[SDK / 'sparc-rtems6/gr740/lib' / n for n in
                   ('librtemscpu.a', 'librtemsbsp.a', 'linkcmds', 'linkcmds.base')]]
    manifest = dict(schema_version=1, build_command=command,
                    tools={str(p): file_hash(p) for p in sdk_files},
                    files={str(p.relative_to(output)): file_hash(p) for p in files})
    write_json(output / 'manifest.json', manifest)
    check_inputs(output, manifest)
    return manifest
