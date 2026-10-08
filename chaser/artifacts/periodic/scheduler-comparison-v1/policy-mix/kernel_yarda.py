"""Lightweight YARDA analysis of a prepared real-kernel workload (experiment 45): the P ELF, hierarchy-rd only.

The same scope as cls-bimodal/yarda_counts in the synthetic studies: one clang/opt MAP extraction, then one
hierarchy-rd run per task against the P executable (a cold task-local job), without event export. Each run must model
exactly the plan's source accesses with complete coverage and passing invariants. The full check of
chaser.periodic.analysis (every exported event against the reference order, on all four ELFs) stays covered by
tests/periodic/multi_array; at experiment sizes it exports up to 240 MB of events per task and ELF (2026-10-08).
Writes <prepared>/analysis/locality.json ({cases: {task: {cls: {'0.5': ...}, clp, modeled_accesses}}}) and
<prepared>/analysis/p/<task_id>/hierarchy.json, the layout chaser.policy.pfirst.inputs.load_analysis reads.
"""

import json
from pathlib import Path
import subprocess

from chaser.locality.cls import cls
from chaser.periodic.build import YARDA

ALPHA = 0.5


def analyze(prepared: Path, timeout: float = 1800) -> dict:
    prepared = prepared.resolve()
    plan = json.loads((prepared / 'p/plan.json').read_text())
    output = prepared / 'analysis'
    output.mkdir(exist_ok=False)
    source = prepared / 'source/workload.c'
    subprocess.run(['clang-14', '-O0', '-Xclang', '-disable-O0-optnone', '-g', '-emit-llvm', '-S', str(source),
                    '-o', str(output / 'workload.ll')], check=True, capture_output=True, timeout=timeout)
    subprocess.run(['opt-14', f'-load-pass-plugin={YARDA / "libMemoryAccessPatterns.so"}',
                    '-passes=function(mem2reg),loop-simplify,loop-annotated-trace', 'workload.ll', '-o', '/dev/null'],
                   check=True, capture_output=True, cwd=output, timeout=timeout)
    raw = json.loads((output / 'workload_ape.json').read_text())
    cases = {}
    for task in plan['tasks']:
        task_id, root, helper = task['task_id'], 'task_job_' + task['task_id'], 'kernel_' + task['task_id']
        functions = [f for f in raw['functions'] if f['function'] in (root, helper) or f['function'].startswith(helper + '_')]
        if not any(f['function'] == root for f in functions):
            raise ValueError(f'{task_id}: expected the emitted job wrapper and inline kernel')
        ape = output / f'{task_id}.ape.json'
        ape.write_text(json.dumps({**raw, 'functions': functions}))
        directory = output / 'p' / task_id
        directory.mkdir(parents=True)
        accesses, limit = task['source_accesses'], task['loop_iterations'] + 10
        subprocess.run([str(YARDA / 'backend/yarda_cpp'), str(ape), '--analysis', 'hierarchy-rd',
                        '--cache', str(prepared / 'cache.yaml'), '--elf', str(prepared / 'build/p.exe'),
                        '--max-source-accesses', str(accesses), '--max-line-references', str(accesses),
                        '--max-single-loop-iterations', str(limit), '--max-cumulative-loop-iterations', str(limit),
                        '--export', str(directory / 'hierarchy.json')], check=True, capture_output=True, timeout=timeout)
        result = json.loads((directory / 'hierarchy.json').read_text())
        entry = next(t for t in result['tasks'] if t['task_id'] == root)
        if (entry['modeled_accesses'] != accesses or not entry['coverage']['complete']
                or not entry['invariants']['all_passed']):
            raise ValueError(f'{task_id}: YARDA stream differs from the plan ({entry["modeled_accesses"]} of {accesses})')
        levels = {level['role']: level['size_bytes'] for level in result['cache_hierarchy']['levels']}
        cases[task_id] = dict(modeled_accesses=accesses,
                              clp=[entry['l1_first_hit_ratio'], entry['llc_first_hit_ratio'], entry['all_cache_miss_ratio']],
                              cls={str(ALPHA): cls(entry, dict(l1_capacity=levels['L1'], llc_capacity=levels['LLC']), ALPHA)})
    report = dict(cases=cases, scope='cold-task-local-job, P ELF, hierarchy-rd only (kernel_yarda)')
    (output / 'locality.json').write_text(json.dumps(report, indent=1) + '\n')
    return report
