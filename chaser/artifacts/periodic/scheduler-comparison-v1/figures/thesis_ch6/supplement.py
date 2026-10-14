"""Post-hoc base-set sensitivity analyses for chapter 6, from frozen result bundles.

No model fitting, simulation or changes to the preregistered result bundles.
Usage: python3 supplement.py <output.json>
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import binomtest, rankdata, wilcoxon

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'results'
SEED, REPLICATES = 20264400, 2000
RUN_KEYS = {'ra-cgb': 'p_racgb', 'g': 'g', 'c13': 'c', 'c112': 'c2'}
SOURCES = {}


def path(relative):
    p = RESULTS / relative
    SOURCES[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p


def label(row):
    return f"{row['heaviness']}/u{round(row['load']*100):03d}/s{row['set_id']:02d}"


def records(name, group_seed):
    decisions = json.loads(path(f'{name}/decisions.json').read_text())['cases']
    out = []
    for line in path(f'{name}/results.jsonl').read_text().splitlines():
        r = json.loads(line)
        states = {c: r[k]['state'] for c, k in RUN_KEYS.items()}
        if any(s not in ('ok', 'deadline') for s in states.values()):
            continue
        d = decisions[label(r)]
        met = {k: v == 'ok' for k, v in states.items()}
        rf_ok = d['status'] in ('P', 'fallback_gc') and met[d['choice']]
        static_ok = d['static_rule'] == 'P' and met['ra-cgb']
        out.append(dict(group=(group_seed, r['set_id']), kind=name,
                        y=int(met['ra-cgb']), rf=d['probabilities']['ra-cgb'],
                        d=-d['cache_demand'], dm=-d['occupancy'],
                        success_difference=int(rf_ok)-int(static_ok)))
    return out


def auc(y, score):
    npos = y.sum()
    ranks = rankdata(score, method='average')
    return float((ranks[y == 1].sum()-npos*(npos+1)/2)/(npos*(len(y)-npos)))


def bootstrap(rows, stratified=False):
    ids = sorted({r['group'] for r in rows})
    ix = {g: np.array([i for i, r in enumerate(rows) if r['group'] == g]) for g in ids}
    kinds = list(dict.fromkeys(r['kind'] for r in rows))
    strata = [[g for g in ids if any(r['group'] == g and r['kind'] == k for r in rows)] for k in kinds]
    if not stratified:
        strata = [ids]
    y = np.array([r['y'] for r in rows])
    scores = np.array([[r[k] for r in rows] for k in ('rf', 'd', 'dm')])
    point = [auc(y, s) for s in scores]
    rng = np.random.default_rng(SEED)
    draws = []
    # All valid loads of a sampled base set travel together; repeated draws of
    # that set repeat its rows, rather than reweighting or imputing missing runs.
    while len(draws) < REPLICATES:
        chosen = [groups[i] for groups in strata for i in rng.integers(0, len(groups), len(groups))]
        selected = np.concatenate([ix[g] for g in chosen])
        yy = y[selected]
        if not 0 < yy.sum() < len(yy):
            continue
        a = [auc(yy, s[selected]) for s in scores]
        draws.append((a[0]-a[1], a[0]-a[2]))
    ci = np.quantile(draws, [.025, .975], axis=0)
    return dict(cases=len(rows), base_groups=len(ids), positives=int(y.sum()),
                strata=[len(s) for s in strata], seed=SEED, replicates=REPLICATES,
                auc=dict(zip(('rf', 'd', 'dm'), point)),
                rf_minus_d=dict(difference=point[0]-point[1], ci95=ci[:, 0].tolist()),
                rf_minus_dm=dict(difference=point[0]-point[2], ci95=ci[:, 1].tolist()),
                nonpositive_replicates=np.sum(np.array(draws) <= 0, axis=0).tolist())


def placement():
    out, tost = [], []
    for kind in ('small', 'big'):
        runs = [json.loads(line) for line in path(f'deadline-{kind}/results.jsonl').read_text().splitlines()]
        rt = json.loads(path(f'deadline-{kind}/rt-metrics.json').read_text())['cases']
        for ref, key in (('ra', 'p_ra'), ('wfd', 'p')):
            for metric in ('tet_ns', 'worst_memory_inflation'):
                groups = defaultdict(list)
                pairs = 0
                for r in runs:
                    if r['p_racgb']['state'] != 'ok' or r[key]['state'] != 'ok':
                        continue
                    a, b = (r['p_racgb'], r[key]) if metric == 'tet_ns' else (rt[label(r)]['ra-cgb'], rt[label(r)][ref])
                    groups[r['set_id']].append(np.log(a[metric]/b[metric]))
                    pairs += 1
                x = np.array([np.median(v) for v in groups.values()])
                out.append(dict(type=kind, reference=ref, metric=metric, pairs=pairs, base_groups=len(x),
                                median_change=float(np.exp(np.median(x))-1),
                                decreased_groups=int(sum(x < 0)), increased_groups=int(sum(x > 0))))
        groups = defaultdict(list)
        pairs = 0
        for r in runs:
            if r['p_racgb']['state'] == 'ok' and r['p_ra']['state'] == 'ok':
                groups[r['set_id']].append(np.log(r['p_racgb']['tat_ns']/r['p_ra']['tat_ns']))
                pairs += 1
        x = np.array([np.median(v) for v in groups.values()])
        upper = float(wilcoxon(x-np.log(1.02), alternative='less').pvalue)
        lower = float(wilcoxon(x-np.log(.98), alternative='greater').pvalue)
        tost.append(dict(type=kind, pairs=pairs, base_groups=len(x), median_ratio=float(np.exp(np.median(x))),
                         p_upper=upper, p_lower=lower, p=max(upper, lower)))
    # Holm over the two pre-existing type contrasts, applied here to the new
    # base-set summaries. This remains a post-hoc sensitivity analysis.
    order = sorted(range(len(tost)), key=lambda i: tost[i]['p'])
    previous = 0
    for rank, i in enumerate(order):
        previous = min(1, max(previous, (len(order)-rank)*tost[i]['p']))
        tost[i]['holm_p'] = previous
    return dict(time_metrics=out, tat_equivalence=tost)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    dest = parser.parse_args().output
    syn = []
    for kind in ('small', 'big', 'mem'):
        name = f'confirm-{kind}'
        seed = json.loads(path(f'{name}/protocol.json').read_text())['seed_base']
        syn.extend(records(name, seed))
    kernels = records('real-kernels', 20264501)
    # Check the stored seed lineage used to group the kernel cases.
    with gzip.open(path('real-kernels/per-set.jsonl.gz'), 'rt') as f:
        seeds = {(x['set_id'], x['seed']) for line in f
                 if 'set_id' in (x := json.loads(line)['content']) and 'seed' in x}
    assert seeds == {(i, 20264501+i) for i in range(24)}
    net = defaultdict(int)
    for r in syn:
        net[r['group']] += r['success_difference']
    positive, negative = sum(v > 0 for v in net.values()), sum(v < 0 for v in net.values())
    result = dict(analysis_status='post-hoc sensitivity; not preregistered',
                  resampling='paired base-set bootstrap; all valid loads retained; percentile linear quantiles',
                  synthetic_pooled=bootstrap(syn), synthetic_stratified=bootstrap(syn, True),
                  kernels=bootstrap(kernels), placement=placement(),
                  success_sign=dict(positive=positive, negative=negative, ties=sum(v == 0 for v in net.values()),
                                    net_cases=sum(net.values()), p=float(binomtest(positive, positive+negative).pvalue)))
    result['sources_sha256'] = dict(sorted(SOURCES.items()))
    result['implementation_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['versions'] = dict(numpy=np.__version__, scipy=scipy.__version__)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('synthetic_stratified', 'kernels', 'success_sign')}, indent=2))


if __name__ == '__main__':
    main()
