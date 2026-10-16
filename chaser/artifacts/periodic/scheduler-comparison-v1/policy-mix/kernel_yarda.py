"""Lightweight YARDA analysis of a prepared real-kernel workload (experiment 45): the P ELF, hierarchy-rd only.

The same scope as cls-bimodal/yarda_counts in the synthetic studies: one clang/opt MAP extraction, then one
hierarchy-rd run per task against the P executable (a cold task-local job), without event export. Each run must model
exactly the plan's source accesses with complete coverage and passing invariants. The full check of
chaser.periodic.analysis (every exported event against the reference order, on all four ELFs) stays covered by
tests/periodic/multi_array; at experiment sizes it exports up to 240 MB of events per task and ELF (2026-10-08).
A suspending job is analyzed per segment (task_job_<id>, task_job_resume_<id>, ...), each from a cold cache, and its
case combines them as chaser.periodic.analysis does (first-hit counts summed), listing the segments.
Writes <prepared>/analysis/locality.json ({cases: {task: {cls: {'0.5': ...}, clp, modeled_accesses[, segments]}}})
and <prepared>/analysis/p/<segment>/hierarchy.json, the layout chaser.policy.pfirst.inputs.load_analysis reads.
"""

import json
from pathlib import Path
import subprocess

from chaser.locality.cls import cls
from chaser.periodic.build import YARDA
from chaser.periodic.kernels import segment_tasks, task_from_plan
from chaser.periodic.workload import ArraySpec

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
    registry = {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}
    cases = {}
    for task in plan['tasks']:
        parts = {}
        for segment in segment_tasks(task_from_plan(task), registry):
            name = segment.task_id
            root, helper = 'task_job_' + name, 'kernel_' + name
            functions = [f for f in raw['functions'] if f['function'] in (root, helper) or f['function'].startswith(helper + '_')]
            if not any(f['function'] == root for f in functions):
                raise ValueError(f'{name}: expected the emitted job wrapper and inline kernel')
            ape = output / f'{name}.ape.json'
            ape.write_text(json.dumps({**raw, 'functions': functions}))
            directory = output / 'p' / name
            directory.mkdir(parents=True)
            accesses, limit = segment.metrics.source_accesses, segment.metrics.loop_iterations + 10
            subprocess.run([str(YARDA / 'backend/yarda_cpp'), str(ape), '--analysis', 'hierarchy-rd',
                            '--cache', str(prepared / 'cache.yaml'), '--elf', str(prepared / 'build/p.exe'),
                            '--max-source-accesses', str(accesses), '--max-line-references', str(accesses),
                            '--max-single-loop-iterations', str(limit), '--max-cumulative-loop-iterations', str(limit),
                            '--export', str(directory / 'hierarchy.json')], check=True, capture_output=True, timeout=timeout)
            result = json.loads((directory / 'hierarchy.json').read_text())
            entry = next(t for t in result['tasks'] if t['task_id'] == root)
            if (entry['modeled_accesses'] != accesses or not entry['coverage']['complete']
                    or not entry['invariants']['all_passed']):
                raise ValueError(f'{name}: YARDA stream differs from the plan ({entry["modeled_accesses"]} of {accesses})')
            levels = {level['role']: level['size_bytes'] for level in result['cache_hierarchy']['levels']}
            parts[name] = entry
        caches = dict(l1_capacity=levels['L1'], llc_capacity=levels['LLC'])
        case = lambda e: dict(modeled_accesses=e['modeled_accesses'],
                              clp=[e['l1_first_hit_ratio'], e['llc_first_hit_ratio'], e['all_cache_miss_ratio']],
                              cls={str(ALPHA): cls(e, caches, ALPHA)})
        if len(parts) == 1:
            cases[task['task_id']] = case(entry)
        else:
            total = sum(e['modeled_accesses'] for e in parts.values())
            counts = [sum(e[k] for e in parts.values())
                      for k in ('l1_first_hit_count', 'llc_first_hit_count', 'all_cache_miss_count')]
            combined = dict(modeled_accesses=total, l1_first_hit_ratio=counts[0] / total,
                            llc_first_hit_ratio=counts[1] / total, all_cache_miss_ratio=counts[2] / total)
            cases[task['task_id']] = dict(case(combined), segments={n: case(e) for n, e in parts.items()})
    report = dict(cases=cases, scope='cold-task-local-job, P ELF, hierarchy-rd only (kernel_yarda)')
    (output / 'locality.json').write_text(json.dumps(report, indent=1) + '\n')
    return report
