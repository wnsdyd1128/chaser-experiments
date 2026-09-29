"""Execute YARDA on original source kernels without inventing missing traces."""

import json
from pathlib import Path
import subprocess
import time

from chaser.periodic.build import YARDA
from tools.rtems_smoke import file_hash, write_json


class Commands:
    """Record every attempted command, exit status and elapsed wall time."""

    def __init__(self, directory: Path, timeout: float):
        self.directory, self.timeout = directory, timeout
        self.rows = []

    def run(self, argv: list[str], name: str) -> None:
        """Retain failures/timeouts in the command log before propagating them."""
        row = dict(argv=argv, log=name + '.log')
        self.rows.append(row)
        started = time.monotonic()
        try:
            with (self.directory / row['log']).open('w') as stream:
                process = subprocess.run(argv, cwd=self.directory, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=self.timeout)
            row['returncode'] = process.returncode
            process.check_returncode()
        except subprocess.TimeoutExpired:
            row['timed_out'] = True
            raise
        finally:
            row['wall_seconds'] = time.monotonic() - started
            write_json(self.directory / 'commands.json', self.rows)


def analyze_source(source: Path, elfs: dict[str, Path], cache: Path, output: Path,
                   *, timeout: float = 120) -> dict:
    """Attempt hierarchy analysis for every ELF, retaining unsupported results.

    No Python uint32 reference is substituted for original floating-point C.
    Successful execution alone is not a proof of a correct dynamic trace.
    Reports remain diagnostic and cannot enter the calibrated timing dataset.
    """
    if not 0 < timeout < float('inf'):
        raise ValueError('Analysis timeout must be positive and finite')
    output.mkdir(parents=True, exist_ok=False)
    commands = Commands(output, timeout)
    plugin, backend = YARDA / 'libMemoryAccessPatterns.so', YARDA / 'backend/yarda_cpp'
    tools = {str(p): file_hash(p) for p in (plugin, backend)}
    cases = {}
    try:
        commands.run(['clang-14', '-O0', '-ffp-contract=off', '-Xclang', '-disable-O0-optnone',
            '-g', '-I', str(source.parent), '-emit-llvm', '-S', str(source),
            '-o', str(output / 'workload.ll')], 'clang')
        commands.run(['opt-14', '-passes=always-inline,function(mem2reg)', '-S',
            'workload.ll', '-o', 'inlined.ll'], 'inline')
        commands.run(['llvm-extract-14', '--func=task_job_polybench',
            '--glob=llvm.global.annotations', r'--rglob=^\.str', '-S',
            'inlined.ll', '-o', 'kernel.ll'], 'extract')
        commands.run(['opt-14', f'-load-pass-plugin={plugin}',
            '-passes=function(mem2reg),loop-simplify,loop-annotated-trace',
            'kernel.ll', '-o', '/dev/null'], 'ape')
        raw = json.loads((output / 'kernel_ape.json').read_text())
        roots = [f for f in raw['functions'] if f['function'] == 'task_job_polybench']
        if len(roots) != 1:
            raise ValueError('Missing original PolyBench job root')
        # Retain emitted loop bounds, indices and guards verbatim.
        raw['functions'] = roots
        ape = output / 'kernel.ape.json'
        write_json(ape, raw)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        cases = {name: dict(execution_status='blocked', stage='frontend',
                           reason=str(error), log=commands.rows[-1]['log'],
                           trace_validation='unavailable', elf_sha256=file_hash(elf))
                 for name, elf in elfs.items()}
        ape = None
    for name, elf in (elfs.items() if ape is not None else ()):
        target = output / (name + '.json')
        argv = [str(backend), str(ape), '--analysis', 'hierarchy-rd', '--cache', str(cache),
            '--elf', str(elf), '--export', str(target),
            '--max-source-accesses', '2000000000', '--max-line-references', '2000000000',
            '--max-single-loop-iterations', '2000000000',
            '--max-cumulative-loop-iterations', '2000000000']
        try:
            commands.run(argv, name)
            result = json.loads(target.read_text())
            complete = (len(result.get('tasks', [])) == 1
                        and result['tasks'][0]['coverage']['complete']
                        and result['tasks'][0]['modeled_accesses'] > 0
                        and result['tasks'][0]['invariants']['all_passed'])
            task = result['tasks'][0] if result.get('tasks') else {}
            cases[name] = dict(execution_status='passed' if complete else 'failed',
                trace_validation='not-validated', result=target.name, elf_sha256=file_hash(elf),
                modeled_accesses=task.get('modeled_accesses'), coverage=task.get('coverage'))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            cases[name] = dict(execution_status='timeout' if isinstance(error, subprocess.TimeoutExpired)
                              else 'failed', trace_validation='unavailable',
                              log=name + '.log', elf_sha256=file_hash(elf))
    report = dict(cases=cases, source_sha256=file_hash(source), map_sha256=file_hash(ape) if ape else None,
                  cache_sha256=file_hash(cache), tools=tools, dataset_eligible=False,
                  scope='cold-task-local-original-polybench',
                  commands_hash=file_hash(output / 'commands.json'))
    if any(file_hash(Path(p)) != h for p, h in tools.items()):
        raise ValueError('Analyzer changed during analysis')
    write_json(output / 'locality.json', report)
    write_json(output / 'manifest.json', dict(files={str(p.relative_to(output)): file_hash(p)
        for p in output.rglob('*') if p.is_file()}))
    return report


def analyze_prepared(prepared: Path, *, timeout: float = 120) -> dict:
    """Analyze the immutable original-source snapshot against all G/C/P ELFs."""
    from chaser.periodic.kernels.inputs import check_current_inputs
    from tools.rtems_smoke import check_inputs
    prepared = prepared.resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    check_current_inputs(manifest)
    report = analyze_source(prepared / 'source/workload.c',
        {n: prepared / f'build/{n}.exe' for n in ('g', 'c', 'p')},
        prepared / 'cache.yaml', prepared / 'analysis', timeout=timeout)
    check_inputs(prepared, manifest)
    return report
