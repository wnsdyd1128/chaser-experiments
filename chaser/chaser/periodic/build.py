"""Immutable waf snapshots with shared workload objects and linked APE analysis."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from chaser.periodic.measurement import make_plan
from chaser.periodic.workload import ArraySpec
from chaser.periodic.codegen import workload_source, topology_header, write_project
from chaser.periodic.kernels.inputs import snapshot_inputs, record_inputs
from tools.rtems_smoke import file_hash, write_json, check_inputs

ROOT = Path(__file__).resolve().parents[2]
SDK = Path('/opt/rtems/6')
YARDA = ROOT / 'rtems/baseline/build/yarda'


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


def check_layout(symbols: dict, arrays: list[dict] | list[ArraySpec]) -> list[dict]:
    """Reject any linker movement, misalignment, size change, or data overlap."""
    layout = []
    end = 0x01000000
    for array in arrays:
        array = array if isinstance(array, ArraySpec) else ArraySpec.from_dict(array)
        address, size, alignment = array.address, array.size_bytes, array.alignment_bytes
        if (symbols.get(array.symbol) != (address, size) or address % alignment
                or address < end or address + size > 0x02000000):
            raise ValueError(f'Workload layout mismatch: {array.symbol}')
        layout.append(dict(array_id=array.array_id, symbol=array.symbol, address=address,
                           size=size, alignment=alignment, element_type=array.element_type))
        end = address + size
    return layout


def prepare(configuration: dict, output: Path) -> dict:
    """Build all three final ELFs from a new source/config/launcher snapshot."""
    if configuration.get('workload_optimization', 'O0') not in ('O0', 'O2'):
        raise ValueError('Workload optimization must be O0 or O2')
    plans = [make_plan(configuration, a) for a in range(3)]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    kernel_inputs = snapshot_inputs(output)
    write_project(output, plans)
    shutil.copyfile('/opt/src/rtems/waf', output / 'waf')
    shutil.copyfile(ROOT / 'rtems/baseline/cache.yaml', output / 'cache.yaml')
    write_json(output / 'configuration.json', configuration)
    command = [sys.executable, 'waf', 'configure', 'build', '-v', f'--rtems-root={SDK}']
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
    layouts = {}
    for name in ('g', 'c', 'p'):
        layouts[name] = check_layout(read_symbols(output / f'build/{name}.exe'), plans[0]['arrays'])
    if not layouts['g'] == layouts['c'] == layouts['p']:
        raise ValueError('G/C/P workload layouts differ')
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
    record_inputs(manifest, kernel_inputs)
    write_json(output / 'manifest.json', manifest)
    check_inputs(output, manifest)
    return manifest
