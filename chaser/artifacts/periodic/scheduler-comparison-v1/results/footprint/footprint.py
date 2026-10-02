"""CLS x footprint task sets: does a co-run L2 capacity effect, not CLS, drive TAT gaps?

Each set has 16 hot-cold tasks with the same 5.5 ms isolated job at a 200 ms
period. Twelve background tasks are high-CLS (center 0.90, CV 0.1 toward 1.0,
as in the bimodal study). Four special tasks share one of four kinds:

  kind  footprint  CLS    shape per job
  SL    32 KiB     ~0.09  1-line hot x 2 + 32 KiB cold, 72 sweeps
  BL    768 KiB    ~0.06  1-line hot x 2 + 768 KiB cold, 3 sweeps
  SH    32 KiB     ~0.66  64-line hot x R + 32 KiB cold, 48 sweeps
  BH    768 KiB    ~0.67  64-line hot x 24R + 768 KiB cold, 2 sweeps

Within a CLS level the small and big kinds make the same number of array
loads and about the same L1 misses per job (SL/BL equal, SH +6% over BH), so
they differ only in the cold region's reuse distance. The l2_probe showed that
three concurrent 768 KiB streams already thrash the 2 MiB L2 and four thrash it
fully, while one or two fit. yarda_cpp CLS models a task alone and cannot see
this co-run effect.

Placements: mixed (CLS zigzag) puts one special task on every core; grouped
puts all four on core 0, so they never run at the same time. Common random
numbers: set k uses bimodal.draws(k) for task positions and background CLS,
shared by all four kinds.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cls-bimodal'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cls-distribution'))

import bimodal
from chaser.periodic.measurement import CONTRACT
from clsset import grouped, zigzag

BUDGET_NS = 5_500_000
PERIOD = 200
WARMUP_JOBS, MEASURED_JOBS = 5, 10
SETS = 20
SPECIAL = 4
BACKGROUND_CV = 0.1
SMALL_LINES, BIG_LINES = 1024, 24576
KINDS = ('SL', 'BL', 'SH', 'BH')
FOOTPRINT_KIB = {'SL': 32, 'BL': 768, 'SH': 32, 'BH': 768}
CLS_LEVEL = {'SL': 'low', 'BL': 'low', 'SH': 'high', 'BH': 'high'}
# The big high-CLS kind runs 24 times the hot repeats of the small one in
# 1/24 of its sweeps, so both make the same number of loads.
HIGH_HOT, HIGH_SWEEPS = 64, {'SH': 48, 'BH': 2}
LOW_SWEEPS = {'SL': 72, 'BL': 3}
PLACEMENTS = ('mixed', 'grouped')


def _cold(kind):
    return BIG_LINES if FOOTPRINT_KIB[kind] == 768 else SMALL_LINES


def _time(model, shape):
    return float(bimodal.job_ns(model, shape['hot'], shape['repeats'], shape['sweeps'], 0,
                                shape['tail'], shape['cold']))


def _fill(model, shape):
    """Add sweep-end register rounds so the planned job equals the budget."""
    rest = BUDGET_NS - _time(model, dict(shape, tail=0))
    if rest < 0:
        raise ValueError(f'{shape} exceeds the job budget')
    tail = int((rest - shape['sweeps'] * model['tail_loops']) // (shape['sweeps'] * model['tail_rounds']))
    shape = dict(shape, tail=tail if tail >= bimodal.MIN_LOOP_ROUNDS else 0)
    return dict(shape, u_error=_time(model, shape) / BUDGET_NS - 1,
                cls=float(bimodal.cls_model(shape['hot'], shape['repeats'], shape['sweeps'], shape['cold'])))


def special_levels(model: dict) -> dict:
    """Shape (hot, repeats, sweeps, cold, tail, u_error, cls) of each special kind."""
    levels = {kind: dict(hot=1, repeats=2, sweeps=LOW_SWEEPS[kind], cold=_cold(kind), tail=0)
              for kind in ('SL', 'BL')}
    ratio = HIGH_SWEEPS['SH'] // HIGH_SWEEPS['BH']
    small = 1
    while _time(model, dict(hot=HIGH_HOT, repeats=small + 1, sweeps=HIGH_SWEEPS['SH'], cold=SMALL_LINES,
                            tail=0)) <= BUDGET_NS and _time(model, dict(
            hot=HIGH_HOT, repeats=(small + 1) * ratio, sweeps=HIGH_SWEEPS['BH'], cold=BIG_LINES,
            tail=0)) <= BUDGET_NS:
        small += 1
    levels['SH'] = dict(hot=HIGH_HOT, repeats=small, sweeps=HIGH_SWEEPS['SH'], cold=SMALL_LINES, tail=0)
    levels['BH'] = dict(hot=HIGH_HOT, repeats=small * ratio, sweeps=HIGH_SWEEPS['BH'], cold=BIG_LINES, tail=0)
    return {kind: _fill(model, shape) for kind, shape in levels.items()}


def background_targets(set_id: int) -> tuple[list[int], list[float]]:
    """Special task positions and the background CLS target of every position."""
    order, z = bimodal.draws(set_id)
    special = sorted(order[:SPECIAL])
    targets = [None] * bimodal.TASKS
    for slot in range(SPECIAL, bimodal.TASKS):
        targets[order[slot]] = bimodal.HIGH_BOUND - (bimodal.HIGH_BOUND - bimodal.HIGH_CENTER) * (
            1 + BACKGROUND_CV * z[slot])
    return special, targets


def configuration(kind: str, set_id: int, tables: dict, levels: dict, placement: str) -> dict:
    special, targets = background_targets(set_id)
    shapes = []
    for i in range(bimodal.TASKS):
        if i in special:
            shapes.append(('special', None, levels[kind]))
        else:
            lv = bimodal.level(tables, 'high', 'as-is', targets[i])
            shapes.append(('background', targets[i], dict(lv, cold=SMALL_LINES)))
    values = [shape['cls'] for _, _, shape in shapes]
    cores = zigzag(values) if placement == 'mixed' else grouped(values)
    tasks = []
    for i, ((role, target, shape), core) in enumerate(zip(shapes, cores)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=shape['hot'] + shape['cold'],
                    hot_distinct=shape['hot'], hot_repeats=shape['repeats'], cold_repeats=1,
                    stride=bimodal.STRIDE, sweeps=shape['sweeps'], core=core, period_ticks=PERIOD,
                    role=role, kind=kind if role == 'special' else 'background',
                    footprint_kib=(shape['hot'] + shape['cold']) * bimodal.STRIDE / 1024,
                    cls_target=target, cls_planned=shape['cls'],
                    u_planned=BUDGET_NS / (PERIOD * 1e6) * (1 + shape['u_error']),
                    l1_misses_planned=shape['sweeps'] * (shape['hot'] + shape['cold']))
        if shape.get('pad'):
            task['pad_rounds'] = shape['pad']
        if shape['tail']:
            task['pad_tail'] = shape['tail']
        tasks.append(task)
    return dict(workload_id=f'footprint-{kind.lower()}-s{set_id:02d}-{placement}-v1',
                family_id='footprint-hot-cold-v1', policy_id=f'footprint-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization='O2', horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * PERIOD,
                warmup_ticks=WARMUP_JOBS * PERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                footprint=dict(kind=kind, footprint_kib=FOOTPRINT_KIB[kind], cls_level=CLS_LEVEL[kind],
                               set_id=set_id, seed=bimodal.SEED_BASE + set_id, placement=placement,
                               budget_ns=BUDGET_NS, background_cv=BACKGROUND_CV, special=SPECIAL))
