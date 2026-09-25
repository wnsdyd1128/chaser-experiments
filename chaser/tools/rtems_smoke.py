"""Prepare an immutable three-job RTEMS placement check, then run fresh simulators."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from chaser.periodic.smoke import TASKS, make_plan, parse_log

ROOT = Path(__file__).resolve().parents[1]
SIMULATOR = Path('/opt/laysim-gr740/laysim-gr740-cli')
COMPILER = Path('/opt/rtems/6/bin/sparc-rtems6-gcc')
WAF = Path('/opt/src/rtems/waf')


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def prepare(configuration: dict, locality: dict, output: Path) -> dict:
    """Build from copied inputs, refusing an existing output directory."""
    plan = make_plan(locality['cases'], configuration)
    output.mkdir(parents=True, exist_ok=False)
    sources = output / 'source'
    sources.mkdir()
    for source in ('rtems/smoke/init.c',
                   'rtems/baseline/workload.c', 'rtems/baseline/workload.h'):
        shutil.copyfile(ROOT / source, sources / Path(source).name)
    shutil.copyfile(ROOT / 'rtems/smoke/wscript', output / 'wscript')
    shutil.copyfile(WAF, output / 'waf')
    write_json(output / 'locality.json', locality)
    write_json(output / 'plan.json', plan)
    mapping = plan['mapping']
    (output / 'config.h').write_text(
        '#define CHASER_CORES {' + ', '.join(str(mapping[t]) for t in TASKS) + '}\n'
        f'#define CHASER_MAPPING_HASH "{plan["mapping_hash"]}"\n')
    command = [sys.executable, 'waf', 'configure', 'build', '-v',
               f'--rtems-root={COMPILER.parents[1]}']
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
    shutil.copyfile(output / 'build/workload.exe', output / 'workload.exe')
    files = [*sources.iterdir(), output / 'locality.json', output / 'plan.json',
             output / 'config.h', output / 'workload.exe', output / 'build.log',
             output / 'waf', output / 'wscript', output / 'build/compile_commands.json']
    manifest = {'schema_version': 1, 'build_command': command,
                'compiler': str(COMPILER), 'compiler_hash': file_hash(COMPILER),
                'files': {str(p.relative_to(output)): file_hash(p) for p in files}}
    write_json(output / 'manifest.json', manifest)
    return plan


def check_inputs(prepared: Path, manifest: dict) -> None:
    for name, expected in manifest['files'].items():
        if file_hash(prepared / name) != expected:
            raise ValueError(f'Prepared artifact changed: {name}')


def write_editor_database(prepared: Path,
                          destination: Path = ROOT / 'rtems/smoke/compile_commands.json') -> None:
    """Point the workspace source at a verified snapshot's real generated config."""
    prepared = prepared.resolve()
    check_inputs(prepared, json.loads((prepared / 'manifest.json').read_text()))
    rows = json.loads((prepared / 'build/compile_commands.json').read_text())
    source = ROOT / 'rtems/smoke/init.c'
    row = next(row for row in rows if Path(row['file']).name == 'init.c')
    snapshot = Path(row['file'])
    row['arguments'] = [str(source) if (Path(row['directory']) / arg).resolve() == snapshot
                        else arg for arg in row['arguments']]
    row['arguments'].insert(1, f'-I{ROOT / "rtems/baseline"}')
    row['file'] = str(source)
    write_json(destination, [row])


def run(prepared: Path, *, runs: int, timeout: float,
        simulator: Path = SIMULATOR) -> list[dict]:
    """Retain every attempted run, including timeouts and invalid target output.

    GNU timeout bounds the PTY wrapper and simulator together. Each invocation
    is a new simulator process; previous run directories cannot be overwritten.
    These measured metrics are deliberately not labeling.Measurement records.
    """
    if type(runs) is not int or runs < 1 or not 0 < timeout < float('inf'):
        raise ValueError('Positive repeat count and finite timeout are required')
    prepared = prepared.resolve()
    simulator = simulator.resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    plan = json.loads((prepared / 'plan.json').read_text())
    simulator_hash = file_hash(simulator)
    output = prepared / 'runs'
    output.mkdir(exist_ok=False)
    command = ['timeout', '--signal=TERM', '--kill-after=5s', f'{timeout}s',
               'script', '-q', '-e', '-c',
               shlex.join([str(simulator), '-r', '-core0', str(prepared / 'workload.exe')]),
               '/dev/null']
    write_json(output / 'protocol.json', {
        'runs': runs, 'timeout_seconds': timeout, 'command': command,
        'simulator': str(simulator), 'simulator_hash': simulator_hash,
        'manifest_hash': file_hash(prepared / 'manifest.json'),
        'measurement_protocol': plan['measurement_protocol'],
        'mapping_hash': plan['mapping_hash'], 'measurement_source': 'measured',
        'scope': 'Integration smoke data; not RF labels or calibrated performance evidence'})
    records = []
    with (output / 'measurements.jsonl').open('x') as measurements:
        for index in range(runs):
            check_inputs(prepared, manifest)
            if file_hash(simulator) != simulator_hash:
                raise ValueError('Simulator changed during repeated execution')
            record = {'run_id': str(index), 'measurement_source': 'measured',
                      'mapping_hash': plan['mapping_hash'], 'time_unit': 'ns',
                      'started_utc': datetime.now(timezone.utc).isoformat()}
            log_path = output / f'{index}.log'
            started = time.monotonic()
            with log_path.open('xb') as log:
                process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT)
            record.update(wall_seconds=time.monotonic() - started,
                          returncode=process.returncode, log=log_path.name,
                          log_hash=file_hash(log_path))
            try:
                check_inputs(prepared, manifest)
                if file_hash(simulator) != simulator_hash:
                    raise ValueError('Simulator changed during execution')
                if process.returncode != 0:
                    raise ValueError(f'Process exited with status {process.returncode}')
                record.update(parse_log(log_path.read_text(errors='replace'), plan))
                record['execution_status'] = 'ok'
            except (ValueError, KeyError) as error:
                record.update(execution_status='failed', error=str(error))
            measurements.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            measurements.flush()
            records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    build.add_argument('configuration', type=Path)
    build.add_argument('--locality', type=Path, default=ROOT / 'exports/locality.json')
    build.add_argument('--output', type=Path, required=True)
    execute = commands.add_parser('run')
    execute.add_argument('prepared', type=Path)
    execute.add_argument('--runs', type=int, required=True)
    execute.add_argument('--timeout', type=float, default=60)
    editor = commands.add_parser('editor', help='Use a prepared build for clangd')
    editor.add_argument('prepared', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(json.loads(args.configuration.read_text()),
                json.loads(args.locality.read_text()), args.output)
    elif args.command == 'editor':
        write_editor_database(args.prepared)
    else:
        records = run(args.prepared, runs=args.runs, timeout=args.timeout)
        passed = sum(row['execution_status'] == 'ok' for row in records)
        print(f'{passed}/{len(records)} successful runs; {args.prepared / "runs"}')
        if passed != len(records):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
