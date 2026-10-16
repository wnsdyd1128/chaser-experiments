"""Per-task values of the pre-run check, from the plan and the YARDA (HARA) outputs of one prepared task set.

The plan gives task_id, u (planned utilization) and period (ms). YARDA gives the CLS (locality.json, computed by
yarda_counts from the hierarchy-rd export) and, per task, the first-hit ratios, the L1 misses and the unique lines of
one cold job (yarda/<task_id>.json). Rates are per microsecond of the task's own execution (u x period). mpki, the
static memory intensity, is the L1 misses per thousand IR instructions of the job when the analysis recorded the
job's instruction count (locality.json ir_instructions, chaser.locality.instructions); None otherwise.
"""

import json
from pathlib import Path

LINE_BYTES = 32  # GR740 L1 and L2 line size


class MissingInput(ValueError):
    """A task lacks a plan value or a YARDA output; the decision is deferred."""


def task_values(plan_tasks, cls: dict, yarda: dict, instructions: dict | None = None) -> list[dict]:
    """plan_tasks: [{task_id, u, period}]; cls: task_id -> CLS; yarda: task_id -> hierarchy-rd task entry;
    instructions: task_id -> IR instructions of one job, where known."""
    instructions = instructions or {}
    out = []
    for t in plan_tasks:
        tid = t['task_id']
        if tid not in cls or tid not in yarda:
            raise MissingInput(f'{tid}: no YARDA output')
        if not (t['u'] > 0 and t['period'] > 0):
            raise MissingInput(f'{tid}: utilization and period must be positive')
        y = yarda[tid]
        out.append(dict(task_id=tid, u=t['u'], period=t['period'], cls=cls[tid],
                        rate=y['l1']['misses'] / (t['u'] * t['period'] * 1000),
                        working_set_kib=y['l1']['unique_lines'] * LINE_BYTES / 1024,
                        p_l1=y['l1_first_hit_ratio'], p_mem=y['all_cache_miss_ratio'],
                        mpki=1000 * y['l1']['misses'] / instructions[tid] if tid in instructions else None))
    return out


def _combined(entries: list[dict]) -> dict:
    """One suspending job's hierarchy-rd entry from its segments, each analyzed from a cold cache (as in
    chaser.periodic.analysis): L1 misses and first-hit counts add up. The segments sweep the same arrays, so the
    job's working set is the largest segment's, not their sum."""
    if len(entries) == 1:
        return entries[0]
    total = sum(e['modeled_accesses'] for e in entries)
    return dict(l1=dict(misses=sum(e['l1']['misses'] for e in entries),
                        unique_lines=max(e['l1']['unique_lines'] for e in entries)),
                l1_first_hit_ratio=sum(e['l1_first_hit_count'] for e in entries) / total,
                all_cache_miss_ratio=sum(e['all_cache_miss_count'] for e in entries) / total)


def load_analysis(prepared: Path, plan_tasks, alpha: str = '0.5') -> list[dict]:
    """Task values from chaser.periodic.analysis output of a prepared snapshot: analysis/locality.json (CLS at
    alpha 0.5, the CLS of this study) and analysis/p/<segment>/hierarchy.json (the P ELF's hierarchy-rd export).
    A suspending job's case lists its segments (task_id, resume_<task_id>, ...); all of them must be present.
    A case's ir_instructions (the whole job's, every segment; None when not countable) gives mpki."""
    cases = json.loads((prepared / 'analysis' / 'locality.json').read_text())['cases']
    cls = {tid: c['cls'][alpha] for tid, c in cases.items()}
    yarda = {}
    for t in plan_tasks:
        segments = list(cases.get(t['task_id'], {}).get('segments', [t['task_id']]))
        paths = [prepared / 'analysis' / 'p' / s / 'hierarchy.json' for s in segments]
        if all(p.exists() for p in paths):
            entries = [json.loads(p.read_text())['tasks'] for p in paths]
            yarda[t['task_id']] = _combined([next((e for e in es if e.get('task_id') == 'task_job_' + s), es[0])
                                             for s, es in zip(segments, entries)])
    instructions = {tid: c['ir_instructions'] for tid, c in cases.items() if c.get('ir_instructions') is not None}
    return task_values(plan_tasks, cls, yarda, instructions)


def load_case(case_dir: Path, plan_tasks) -> list[dict]:
    """Task values of a prepared set directory holding locality.json and yarda/<task_id>.json."""
    cls = {r['task_id']: r['cls'] for r in json.loads((case_dir / 'locality.json').read_text())['tasks']}
    yarda = {}
    for t in plan_tasks:
        path = case_dir / 'yarda' / f"{t['task_id']}.json"
        if path.exists():
            yarda[t['task_id']] = json.loads(path.read_text())['tasks'][0]
    return task_values(plan_tasks, cls, yarda)
