"""Experiment 45's technical report (pre-registered, EXPERIMENTS.md 45) with a calibration check of the frozen RF.

- task values: CLS, p_mem, L1-miss rate per microsecond and working set of the real-kernel tasks (decisions.json, per
  kernel) against experiment 44's synthetic tasks (chaser.policy.pfirst.inputs.load_case on its outputs, per task type)
- placement: sets whose CHASER (ra-cgb) mapping differs from the U-balanced one, tasks with CLS <= 0.5
- per load: judged sets, CHASER met, RF status, mean RF probability for CHASER, mean D, M and D + M
- calibration: per bin of the RF probability for CHASER, sets and the share where CHASER met every deadline, for
  experiments 44 and 45 (sets judged by confirm_analysis)
- false accepts of the RF: load, probability, D + M
Run with PYTHONPATH=<workspace>:policy-mix:period-distribution.
Experiment 46 runs it with --design heldout-kernels --output heldout-kernels-v1 (same report, its kernels).
Usage: python3 kernel_report.py --cache <.cache dir> --output real-kernels-v1 --dest <dir> [--design NAME]
"""

import argparse
import json
from pathlib import Path
from statistics import mean

import numpy as np

import confirm_analysis as ca
import kernel_set as ks
from chaser.policy.pfirst import inputs, placement

VALUES = ('cls', 'p_mem', 'rate', 'working_set_kib')
QUANTILES = (5, 25, 50, 75, 95)
BINS = (0.0, 0.5, 0.8, 0.9, 0.95, 0.99, 1.0001)
EXPERIMENT = {'real-kernels-v1': 'experiment 45', 'heldout-kernels-v1': 'experiment 46'}


def summary(rows) -> dict:
    out = dict(tasks=len(rows), low_cls_share=float(np.mean([r['cls'] <= placement.CLS_LOW for r in rows])))
    for v in VALUES:
        out[v] = dict(zip((f'p{q}' for q in QUANTILES), map(float, np.percentile([r[v] for r in rows], QUANTILES))))
    return out


def calibration(records) -> list[dict]:
    out = []
    for lo, hi in zip(BINS, BINS[1:]):
        rs = [r for r in records if r['p_chaser'] is not None and lo <= r['p_chaser'] < hi]
        out.append(dict(low=lo, high=min(hi, 1.0), sets=len(rs), met=sum(r['met']['ra-cgb'] for r in rs),
                        mean_probability=mean(r['p_chaser'] for r in rs) if rs else None))
    return out


def synthetic_values(cache: Path, records) -> dict:
    out = {}
    for r in records:
        case = cache / r['design'] / r['label']
        tasks = json.loads((case / 'wfd/configuration.json').read_text())['tasks']
        plan = [dict(task_id=t['task_id'], u=t['u_planned'], period=t['period_ticks']) for t in tasks]
        out.setdefault(r['design'], []).extend(inputs.load_case(case, plan))
    return out


def real_values(output: Path) -> dict:
    """Kernel name -> task values (decisions.json, the values the pre-run check used)."""
    decisions = json.loads((output / 'decisions.json').read_text())['cases']
    kernels = {}
    for case in ks.cases():
        label = ks.label(case)
        kernel = {t['task_id']: t['kernel'] for t in json.loads((output / label / 'design.json').read_text())['tasks']}
        for v in decisions[label]['task_values']:
            kernels.setdefault(kernel[v['task_id']], []).append(v)
    return dict(sorted(kernels.items()))


def v1_records(cache: Path, name: str) -> tuple[list[dict], dict]:
    """confirm_analysis.sets with the frozen v1 policy's decision. Experiment 46's run recorded the dropped policy v2
    as status and v1 under compare (EXPERIMENTS.md 46); every other output records v1 as status."""
    records, excluded = ca.sets(cache, (name,))
    decisions = json.loads((cache / name / 'decisions.json').read_text())['cases']
    for r in records:
        v1 = decisions[r['label']].get('compare', decisions[r['label']])
        r['status'], r['choice'] = v1['status'], 'ra-cgb' if v1['status'] == 'P' else v1['choice']
        r['rf'] = ca.outcome(v1['status'] in ('P', 'fallback_gc'), r['choice'], r['met'])
    return records, excluded


def report(cache: Path, name: str) -> dict:
    output = cache / name
    records, excluded = v1_records(cache, name)
    decisions = json.loads((output / 'decisions.json').read_text())['cases']
    kernels = real_values(output)
    real = [v for vs in kernels.values() for v in vs]
    changed = sum(json.loads((output / ks.label(c) / 'design.json').read_text())['mappings']['wfd']
                  != json.loads((output / ks.label(c) / 'design.json').read_text())['mappings']['chaser'] for c in ks.cases())
    loads = {}
    for r in records:
        d = decisions[r['label']]
        g = loads.setdefault(r['load'], dict(sets=0, chaser_met=0, status={}, p=[], d=[], m=[], dm=[]))
        g['sets'] += 1
        g['chaser_met'] += r['met']['ra-cgb']
        g['status'][r['status']] = g['status'].get(r['status'], 0) + 1
        g['p'].append(r['p_chaser'])
        g['d'].append(d['cache_demand'])
        g['m'].append(d['memory_demand'])
        g['dm'].append(d['occupancy'])
    per_load = {str(k): dict(sets=g['sets'], chaser_met=g['chaser_met'], status=g['status'], mean_probability=mean(g['p']),
                             min_probability=min(g['p']), mean_d=mean(g['d']), mean_m=mean(g['m']), mean_dm=mean(g['dm']),
                             max_dm=max(g['dm']))
                for k, g in sorted(loads.items())}
    confirm, _ = ca.sets(cache)
    return dict(
        experiment=EXPERIMENT.get(name, name), sets=len(records), excluded=excluded,
        task_values=dict(real=summary(real), real_by_kernel={k: summary(v) for k, v in kernels.items()},
                         synthetic={k: summary(v) for k, v in synthetic_values(cache, confirm).items()}),
        placement=dict(sets=len(ks.cases()), chaser_differs_from_wfd=changed,
                       low_cls_tasks=sum(v['cls'] <= placement.CLS_LOW for v in real), tasks=len(real)),
        per_load=per_load,
        calibration={'experiment 44': calibration(confirm), EXPERIMENT.get(name, name): calibration(records)},
        false_accepts=[dict(label=r['label'], load=r['load'], probability=r['p_chaser'], occupancy=r['occupancy'])
                       for r in records if r['rf'] == 'false_accept'])


def markdown(result) -> str:
    tv = result['task_values']
    lines = [f"# {result['experiment'].capitalize()}: technical report (pre-registered) and RF calibration", '',
             f"{result['sets']} sets judged; left out: {result['excluded'] or 'none'}", '',
             '## Task values (median [5th, 95th percentile])', '',
             '| source | tasks | CLS | p_mem | L1 misses per µs | working set KiB | CLS <= 0.5 |', '|---|---:|---|---|---|---|---:|']
    fmt = lambda s, v, d: f"{s[v]['p50']:.{d}f} [{s[v]['p5']:.{d}f}, {s[v]['p95']:.{d}f}]"
    rows = [('real kernels', tv['real'])] + [(f'real: {k}', s) for k, s in tv['real_by_kernel'].items()] + \
           [(f'synthetic: {k}', s) for k, s in tv['synthetic'].items()]
    for name, s in rows:
        lines.append(f"| {name} | {s['tasks']} | {fmt(s, 'cls', 3)} | {fmt(s, 'p_mem', 4)} | {fmt(s, 'rate', 3)} | "
                     f"{fmt(s, 'working_set_kib', 1)} | {s['low_cls_share']:.1%} |")
    p = result['placement']
    lines += ['', f"Placement: CHASER's mapping differs from the U-balanced one in {p['chaser_differs_from_wfd']} of {p['sets']} sets; "
              f"{p['low_cls_tasks']} of {p['tasks']} tasks have CLS <= 0.5.", '', '## Per load', '',
              '| load | sets | CHASER met | RF status | mean RF probability (min) | mean D | mean M | mean D + M (max) |',
              '|---|---:|---:|---|---|---:|---:|---|']
    for load, g in result['per_load'].items():
        lines.append(f"| {load} | {g['sets']} | {g['chaser_met']} | {g['status']} | {g['mean_probability']:.3f} ({g['min_probability']:.3f}) | "
                     f"{g['mean_d']:.3f} | {g['mean_m']:.3f} | {g['mean_dm']:.3f} ({g['max_dm']:.3f}) |")
    lines += ['', '## Calibration: RF probability for CHASER against the observed outcome', '',
              '| experiment | probability bin | sets | CHASER met | share met | mean probability |', '|---|---|---:|---:|---:|---:|']
    for exp, bins in result['calibration'].items():
        for b in bins:
            if b['sets']:
                lines.append(f"| {exp} | [{b['low']:.2f}, {b['high']:.2f}) | {b['sets']} | {b['met']} | {b['met'] / b['sets']:.1%} | {b['mean_probability']:.3f} |")
    lines += ['', '## RF false accepts', '', '| set | RF probability | D + M |', '|---|---:|---:|']
    lines += [f"| {f['label']} | {f['probability']:.3f} | {f['occupancy']:.3f} |" for f in result['false_accepts']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', default='real-kernels-v1')
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--design', default='real-kernels', choices=tuple(ks.DESIGNS))
    args = parser.parse_args()
    ks.select(args.design)
    result = report(args.cache.resolve(), args.output)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'report.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'report.md').write_text(markdown(result))
    print('wrote', args.dest / 'report.md')


if __name__ == '__main__':
    main()
