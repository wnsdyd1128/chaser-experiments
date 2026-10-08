"""Pre-registered analysis of experiment 41 (memory cost): the l2 cell against the mem cell, paired by load and set.

Primary, per placement (wfd = results key p, cgb = p_cgb): exact two-sided McNemar on "met every deadline",
Holm over the two placements (alpha 0.05). Secondary 1: AUC for a missed deadline over this experiment's
Partitioned runs of the cache demand D (the static rule), max(D, M) with the YARDA memory demand M, the
experiment 35 main model (f35) and f35 with the p_mem distribution statistics (experiment 36), both forests
trained on experiments 17-27 (rf_rows' table). Secondary 2: two-sided sign test on the whole-run late jobs, mean D and M per
cell, and which tasks were late (task_slack_analysis classes).
Usage: python3 memcost_analysis.py --output <memory-cost run output> --rows <training rows table> --dest <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import mean

from scipy import stats as scipy_stats

from period_swap_analysis import primary
import rf_candidates as rc
import rf_devcheck as rd
import rf_rows
import rf_stats as rs
import task_slack_analysis as ts

L2, MEM = 'l2-low25', 'mem-low25'
PLACEMENTS = {'wfd': 'p', 'cgb': 'p_cgb'}
MEMORY_REQUESTS_PER_US = 1000 / 220  # laysim's memory serves one request at a time, about 220 ns each


def _state(row, key):
    state = row[key]['state']
    return state == 'ok' if state in ('ok', 'deadline') else None


def paired(rows, key) -> list[dict]:
    cells = {}
    for r in rows:
        cells.setdefault((r['load'], r['set_id']), {})[r['heaviness']] = _state(r, key)
    return [dict(load=load, set_id=k, l2=v[L2], mem=v[MEM]) for (load, k), v in sorted(cells.items())
            if v.get(L2) is not None and v.get(MEM) is not None]


def _binomial(a, b) -> float:
    return float(scipy_stats.binomtest(min(a, b), a + b).pvalue) if a + b else 1.0


def mcnemar(pairs) -> dict:
    only_l2 = sum(p['l2'] and not p['mem'] for p in pairs)
    only_mem = sum(p['mem'] and not p['l2'] for p in pairs)
    return dict(pairs=len(pairs), only_l2_met=only_l2, only_mem_met=only_mem, both_met=sum(p['l2'] and p['mem'] for p in pairs),
                neither_met=sum(not p['l2'] and not p['mem'] for p in pairs), p=_binomial(only_l2, only_mem))


def memory_demand(tasks) -> float:
    """Sum of U x memory accesses per microsecond (L1-miss rate x p_mem / (1 - p_L1)) over the memory service rate."""
    return sum(t['u_planned'] * t['traffic_planned'] * t['p_mem'] / (1 - t['p_l1']) for t in tasks) / MEMORY_REQUESTS_PER_US


def late_test(rt, build) -> dict:
    cells = {}
    for label, builds in rt['cases'].items():
        heaviness, load, k = label.split('/')
        entry = builds.get(build)
        if entry and entry['state'] in ('ok', 'deadline'):
            cells.setdefault((load, k), {})[heaviness] = entry['late_jobs_all']
    pairs = [v for v in cells.values() if L2 in v and MEM in v]
    fewer_l2, fewer_mem = sum(p[L2] < p[MEM] for p in pairs), sum(p[MEM] < p[L2] for p in pairs)
    return dict(pairs=len(pairs), fewer_in_l2=fewer_l2, fewer_in_mem=fewer_mem, late_l2=sum(p[L2] for p in pairs),
                late_mem=sum(p[MEM] for p in pairs), p=_binomial(fewer_l2, fewer_mem))


def predictors(output: Path, rows: Path) -> dict:
    """AUC for a missed deadline per placement and pooled, and mean D and M per cell."""
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    source = (('41 memory cost', ((output.name, 'p', 'wfd', 'wfd'), (output.name, 'p_cgb', 'cgb', 'cgb'))),)
    test = rc.load(output.parent, sources=source)
    stats, demand = {}, {}
    for r in test:
        if r['case'] not in stats:
            heaviness, load, k = eval(r['case'].split('/', 1)[1])
            case = output / f'{heaviness}/u{round(load * 100):03d}/s{k:02d}'
            tasks = rc.yarda_tasks(case, json.loads((case / 'wfd/configuration.json').read_text())['tasks'])
            stats[r['case']], demand[r['case']] = rs.distribution_stats(tasks), memory_demand(tasks)
    rs.add_stats(test, stats)
    train = rf_rows.load(rows, sources={source for source, _ in rc.SOURCES})
    probs = {}
    for name, names in (('f35', rs.VARIANTS['f35']), ('f35 + p_mem statistics', rs.VARIANTS['p_mem'])):
        model = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1).fit(*rd.matrix(train, names))
        probs[name] = model.predict_proba(rd.matrix(test, names)[0])[:, 1]
    out = dict(auc={}, cells={})
    for name, keep in (('pooled', lambda r: True), ('wfd', lambda r: r['candidate'] == 'wfd'), ('cgb', lambda r: r['candidate'] == 'cgb')):
        idx = [i for i, r in enumerate(test) if keep(r)]
        y = [1 - test[i]['label'] for i in idx]  # 1 = missed a deadline
        d = [test[i]['features']['cache_demand'] for i in idx]
        m = [demand[test[i]['case']] for i in idx]
        out['auc'][name] = {'cache demand D': rd.auc(y, d), 'max(D, M)': rd.auc(y, [max(a, b) for a, b in zip(d, m)]),
                            **{k: rd.auc(y, [1 - p[i] for i in idx]) for k, p in probs.items()}}
    for heaviness in (L2, MEM):
        rows = [r for r in test if f"'{heaviness}'" in r['case']]
        out['cells'][heaviness] = dict(rows=len(rows), missed=sum(1 - r['label'] for r in rows),
                                       mean_d=mean(r['features']['cache_demand'] for r in rows),
                                       mean_m=mean(demand[r['case']] for r in rows),
                                       mean_cls_weighted=mean(r['features']['weighted_one_minus_cls'] for r in rows),
                                       **{f'mean probability, {k}': float(np.mean([p[i] for i, r in enumerate(test) if f"'{heaviness}'" in r['case']]))
                                          for k, p in probs.items()})
    return out


def who_late(output: Path) -> dict:
    out = {}
    for heaviness in (L2, MEM):
        for build in PLACEMENTS:
            rows = [r for case in sorted((output / heaviness).glob('u0*/s*')) for r in ts.run_rows(('41', case, build))]
            out[f'{heaviness} {build}'] = {c: dict(tasks=sum(r['cls'] == c for r in rows),
                                                   late_tasks=sum(r['cls'] == c and r['late_jobs'] > 0 for r in rows))
                                           for c in ts.CLASSES}
    return out


def markdown(result) -> str:
    f = lambda v: '-' if v is None else f'{v:.3f}'
    lines = ['# Experiment 41: same CLS and U, memory tasks hitting L2 (l2) or going to memory (mem) (pre-registered)', '',
             '## Primary: sets meeting every deadline, exact McNemar, Holm over the placements', '',
             '| placement | pairs | both met | only l2 met | only mem met | neither | p | Holm p | significant |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for name, t in result['primary'].items():
        lines.append(f"| {name} | {t['pairs']} | {t['both_met']} | {t['only_l2_met']} | {t['only_mem_met']} | {t['neither_met']} "
                     f"| {t['p']:.4f} | {t['holm_p']:.4f} | {t['significant']} |")
    lines += ['', '## Sets meeting every deadline per load (l2 / mem)', '', '| placement, load | pairs | l2 | mem |', '|---|---:|---:|---:|']
    lines += [f"| {k} | {v['pairs']} | {v['l2_met']} | {v['mem_met']} |" for k, v in result['by_load'].items()]
    lines += ['', '## Secondary 1: AUC for a missed deadline on this experiment\'s runs', '',
              '| runs | ' + ' | '.join(result['predictors']['auc']['pooled']) + ' |', '|---|' + '---:|' * len(result['predictors']['auc']['pooled'])]
    for name, v in result['predictors']['auc'].items():
        lines.append(f'| {name} | ' + ' | '.join(f(x) for x in v.values()) + ' |')
    lines += ['', '| cell | rows | missed | mean D | mean M | mean U-weighted (1 - CLS) | mean P(met), f35 | mean P(met), f35 + p_mem |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, v in result['predictors']['cells'].items():
        lines.append(f"| {name} | {v['rows']} | {v['missed']} | {v['mean_d']:.3f} | {v['mean_m']:.3f} | {v['mean_cls_weighted']:.3f} "
                     f"| {v['mean probability, f35']:.3f} | {v['mean probability, f35 + p_mem statistics']:.3f} |")
    lines += ['', '## Secondary 2: whole-run late jobs, sign test', '',
              '| placement | pairs | fewer in l2 | fewer in mem | late jobs l2 | late jobs mem | p |', '|---|---:|---:|---:|---:|---:|---:|']
    for name, t in result['late_jobs'].items():
        lines.append(f"| {name} | {t['pairs']} | {t['fewer_in_l2']} | {t['fewer_in_mem']} | {t['late_l2']} | {t['late_mem']} | {t['p']:.4f} |")
    lines += ['', '## Late tasks by class (late / tasks)', '', '| cell, placement | ' + ' | '.join(ts.CLASSES) + ' |', '|---|---|---|---|']
    for k, v in result['who_late'].items():
        lines.append(f'| {k} | ' + ' | '.join(f"{v[c]['late_tasks']} / {v[c]['tasks']}" for c in ts.CLASSES) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    rt = json.loads((output / 'rt-metrics.json').read_text())
    result = dict(primary=primary({name: mcnemar(paired(rows, key)) for name, key in PLACEMENTS.items()}), by_load={})
    for name, key in PLACEMENTS.items():
        for load in sorted({r['load'] for r in rows}):
            pairs = [p for p in paired(rows, key) if p['load'] == load]
            result['by_load'][f'{name} {load}'] = dict(pairs=len(pairs), l2_met=sum(p['l2'] for p in pairs),
                                                       mem_met=sum(p['mem'] for p in pairs))
    result['late_jobs'] = {b: late_test(rt, b) for b in PLACEMENTS}
    result['who_late'] = who_late(output)
    result['predictors'] = predictors(output, args.rows.resolve())
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'memory-cost.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'memory-cost.md').write_text(markdown(result))
    print('wrote', args.dest / 'memory-cost.md')


if __name__ == '__main__':
    main()
