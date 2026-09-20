"""Prepare, analyze, and run immutable periodic G/C/P measurement snapshots."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import time
import shutil

from chaser.periodic import parse_log
from chaser.periodic_build import prepare, read_symbols
from tools.rtems_smoke import SIMULATOR, check_inputs, file_hash, write_json


def run(prepared: Path, output: Path, *, architecture: int, runs: int,
        timeout: float = 60, mode: int = 0, trace: bool = False,
        empty: bool = False,
        simulator: Path = SIMULATOR) -> list[dict]:
    """Keep every planned fresh-process attempt, including invalid/timeout runs.

    Mode zero executes the taskset; mode i+1 runs task i alone on core zero in
    the very same P ELF. Simulator boot writes select mode before execution;
    the executed ELF remains unchanged and is checked before and after runs.
    Trace runs are separate evidence and must not enter the timing dataset.
    """
    if (type(runs) is not int or runs < 1 or not 0 < timeout < float('inf')
            or type(architecture) is not int or architecture not in range(3)):
        raise ValueError('Positive runs/timeout and a valid architecture are required')
    prepared, output, simulator = prepared.resolve(), output.resolve(), simulator.resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    name = ('g', 'c', 'p')[architecture]
    plan = json.loads((prepared / name / 'plan.json').read_text())
    if type(mode) is not int or not 0 <= mode <= len(plan['tasks']) or (mode and architecture != 2):
        raise ValueError('Characterization needs one task and the P ELF')
    elf = prepared / f'build/{name}.exe'
    symbols = read_symbols(elf)
    output.mkdir(parents=True, exist_ok=False)
    implementation = output / 'implementation'
    implementation.mkdir()
    root = Path(__file__).resolve().parents[1]
    for relative in ('chaser/periodic.py', 'chaser/periodic_build.py',
                     'chaser/periodic_dataset.py', 'tools/rtems_periodic.py',
                     'tools/rtems_smoke.py'):
        destination = implementation / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, destination)
    batch = output / 'boot.batch'
    batch.write_text(f'wmem 0x{symbols["chaser_mode"][0]:x} 0x{mode:x}\n'
                     f'wmem 0x{symbols["chaser_trace"][0]:x} 0x{int(trace):x}\n'
                     f'wmem 0x{symbols["chaser_empty"][0]:x} 0x{int(empty):x}\nrun\nquit\n')
    command = ['timeout', '--signal=TERM', '--kill-after=5s', f'{timeout}s',
               'script', '-q', '-e', '-c', shlex.join([
                   str(simulator), '-core0', str(elf), '-batch', str(batch)]), '/dev/null']
    simulator_hash = file_hash(simulator)
    protocol = dict(runs=runs, timeout_seconds=timeout, command=command,
                    boot_hash=file_hash(batch), elf_hash=file_hash(elf),
                    simulator_hash=simulator_hash, manifest_hash=file_hash(prepared / 'manifest.json'),
                    plan_hash=plan['plan_hash'], mode=mode, trace=trace, empty=empty,
                    implementation_hashes={str(p.relative_to(output)): file_hash(p)
                                           for p in implementation.rglob('*.py')},
                    execution_backend='laysim-gr740', measurement_source='measured',
                    scope='scheduler-trace' if trace else 'empty-overhead' if empty else 'periodic-timing')
    write_json(output / 'protocol.json', protocol)
    records = []
    with (output / 'measurements.jsonl').open('x') as stream:
        for index in range(runs):
            record = dict(run_id=str(index), workload_id=plan['workload_id'],
                          architecture=architecture, mapping_hash=plan['mapping_hash'],
                          topology_id=plan['topology_id'], allocator_id=plan['policy_id'],
                          plan_hash=plan['plan_hash'], elf_hash=protocol['elf_hash'],
                          mode=mode, trace=trace, empty=empty, measurement_source='measured', time_unit='ns',
                          tet_ns=None, tat_ns=None, makespan_ns=None,
                          started_utc=datetime.now(timezone.utc).isoformat())
            log_path = output / f'{index}.log'
            started = time.monotonic()
            try:
                check_inputs(prepared, manifest)
                if file_hash(simulator) != simulator_hash or file_hash(batch) != protocol['boot_hash']:
                    raise ValueError('Simulator or boot configuration changed')
                with log_path.open('xb') as log:
                    process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                                             stderr=subprocess.STDOUT)
                record.update(returncode=process.returncode, log=log_path.name,
                              log_hash=file_hash(log_path))
                # Parse partial evidence even if the process failed or timed out.
                record.update(parse_log(log_path.read_text(errors='replace'), plan,
                                        mode=mode, trace=trace, empty=empty))
                if process.returncode:
                    record['execution_status'] = 'failed'
                    record['errors'].append('process_exit')
                check_inputs(prepared, manifest)
                if (file_hash(simulator) != simulator_hash
                        or file_hash(batch) != protocol['boot_hash']):
                    raise ValueError('Simulator or boot configuration changed during execution')
            except (ValueError, KeyError, OSError) as error:
                record.update(execution_status='failed', error=str(error))
            record['wall_seconds'] = time.monotonic() - started
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
            records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    build.add_argument('configuration', type=Path)
    build.add_argument('--output', type=Path, required=True)
    execute = commands.add_parser('run')
    execute.add_argument('prepared', type=Path)
    execute.add_argument('--output', type=Path, required=True)
    execute.add_argument('--architecture', choices=('g', 'c', 'p'), required=True)
    execute.add_argument('--runs', type=int, required=True)
    execute.add_argument('--timeout', type=float, default=60)
    execute.add_argument('--mode', type=int, default=0)
    execute.add_argument('--trace', action='store_true')
    execute.add_argument('--empty', action='store_true')
    analysis = commands.add_parser('analyze')
    analysis.add_argument('prepared', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(json.loads(args.configuration.read_text()), args.output)
    elif args.command == 'analyze':
        from chaser.periodic_analysis import analyze
        analyze(args.prepared)
    else:
        records = run(args.prepared, args.output, architecture=('g', 'c', 'p').index(args.architecture),
                      runs=args.runs, timeout=args.timeout, mode=args.mode, trace=args.trace, empty=args.empty)
        passed = sum(r['execution_status'] == 'ok' for r in records)
        print(f'{passed}/{len(records)} successful runs: {args.output}')
        if passed != len(records):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
