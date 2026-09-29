"""Run all original MEDIUM examples without stopping at the first failure."""

import json
from pathlib import Path
import subprocess

from chaser.periodic.polybench.analysis import analyze_source
from chaser.periodic.polybench.native import write_sources, verify_native
from chaser.periodic.polybench.sources import ROOT, REVISION, benchmarks
from tools.rtems_smoke import file_hash, write_json


def verify_suite(output: Path, *, periodic: bool = False, timeout: float = 120) -> dict:
    """Verify native output and attempt YARDA for all 30 kernels.

    With periodic=True, also build and analyze the actual G/C/P RTEMS ELFs.
    Simulator timing runs are separate: large MEDIUM jobs need explicit runtime
    budgets. No unsupported benchmark is silently dropped from the population.
    """
    from chaser.periodic.build import prepare
    from chaser.periodic.analysis import analyze
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(upstream_revision=REVISION, dataset='MEDIUM', periodic=periodic,
                  dataset_eligible=False, benchmarks={})
    cache = (ROOT / 'rtems/baseline/cache.yaml').resolve()
    for benchmark in benchmarks():
        directory = output / benchmark.name
        row = dict(dimensions=benchmark.dimensions, element_type=benchmark.element_type)
        report['benchmarks'][benchmark.name] = row
        try:
            if periodic:
                configuration = json.loads((ROOT / 'configs/periodic-polybench' /
                                            (benchmark.name + '-medium.json')).read_text())
                prepare(configuration, directory)
                row['rtems_build'] = 'passed'
                row['native'] = json.loads((directory / 'native-validation.json').read_text())['status']
                row['periodic_yarda'] = analyze(directory, timeout=timeout)['cases']
            else:
                write_sources(benchmark, directory / 'source')
                row['native'] = verify_native(directory, benchmark, timeout=timeout)['status']
            row['native_yarda'] = analyze_source(directory / 'source/workload.c',
                {'native': directory / 'native.exe'}, cache,
                directory / 'native-analysis', timeout=timeout)['cases']['native']
            row['source_sha256'] = file_hash(directory / 'source/workload.c')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            row['error'] = str(error)
        write_json(output / 'summary.json', report)
        print(benchmark.name + ': ' + json.dumps(row, sort_keys=True), flush=True)
    return report


def execution_passed(report: dict) -> bool:
    """Return false for missing results, compiler failures or any YARDA failure."""
    return len(report['benchmarks']) == 30 and all(
        'error' not in row and row.get('native') == 'passed'
        and row.get('native_yarda', {}).get('execution_status') == 'passed'
        and (not report['periodic'] or row.get('rtems_build') == 'passed'
             and len(row.get('periodic_yarda', {})) == 3
             and all(c['execution_status'] == 'passed' for c in row['periodic_yarda'].values()))
        for row in report['benchmarks'].values())
