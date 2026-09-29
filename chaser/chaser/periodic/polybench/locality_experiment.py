"""Measure locality of one original PolyBench MEDIUM kernel with YARDA."""

import argparse
import json
from pathlib import Path

from chaser.locality.analyzer import analyze_task
from chaser.periodic.polybench.analysis import analyze_source
from chaser.periodic.polybench.native import verify_native, write_sources
from chaser.periodic.polybench.sources import ROOT, REVISION, benchmark_named
from tools.rtems_smoke import write_json


def run(benchmark_name: str, output: Path, *, timeout: float) -> dict:
    """Keep source, native validation, APE, three YARDA exports and scalar results."""
    benchmark = benchmark_named(benchmark_name)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_sources(benchmark, output / 'source')
    native = verify_native(output, benchmark, timeout=timeout)
    cache = ROOT / 'rtems/baseline/cache.yaml'
    source = output / 'source/workload.c'
    elf = output / 'native.exe'
    frontend = analyze_source(source, {'native': elf}, cache,
                              output / 'native-analysis', timeout=timeout)
    if frontend['cases']['native']['execution_status'] != 'passed':
        raise ValueError('PolyBench frontend or hierarchy analysis did not pass')
    prior = json.loads((output / 'native-analysis/native.json').read_text())['tasks'][0]
    record = analyze_task('task_job_polybench',
                          ape=output / 'native-analysis/kernel.ape.json',
                          elf=elf, cache=cache, source=source,
                          executable=ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp',
                          output_dir=output / 'locality-analysis',
                          max_cumulative_loop_iterations=2_000_000_000,
                          max_source_accesses=prior['source_accesses'],
                          max_line_references=prior['modeled_accesses'], timeout=timeout)
    current = json.loads((output / 'locality-analysis/hierarchy.json').read_text())['tasks'][0]
    for key in ('source_accesses', 'modeled_accesses', 'l1_first_hit_count',
                'llc_first_hit_count', 'all_cache_miss_count'):
        if prior[key] != current[key]:
            raise ValueError(f'Independent hierarchy runs differ in {key}')
    result = dict(benchmark=benchmark.name, dataset='MEDIUM',
                  upstream_revision=REVISION, dimensions=benchmark.dimensions,
                  element_type=benchmark.element_type, native_validation=native['status'],
                  hierarchy_validation='passed', trace_validation='not-validated',
                  dataset_eligible=False, case=record['case'],
                  provenance=record['provenance'])
    write_json(output / 'case.json', result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('benchmark')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    result = run(args.benchmark, args.output, timeout=args.timeout)
    print(json.dumps({'benchmark': result['benchmark'], 'case': result['case']},
                     sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
