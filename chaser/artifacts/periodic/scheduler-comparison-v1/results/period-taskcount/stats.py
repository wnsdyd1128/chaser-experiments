"""Test G/C/P gaps per period-distribution cell and across cells.

The simulator is deterministic, so the sampling unit is the task set. Within
a cell, each set gives one paired relative gap (X_a - X_b) / X_b. Sets with the
same id share their standard draws across means and CVs, so cross-cell tests
block on the set id.
"""

import argparse
import json
from pathlib import Path
import random
from statistics import mean, median

from scipy import stats

PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'), ('g', 'c'), ('g', 'c2'), ('c', 'c2'))
METRICS = ('tet_ns', 'tat_ns')
ALPHA = 0.05
BOOTSTRAP = 10_000


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def gap(row, metric, a, b):
    if row[a]['status'] != 'ok' or row[b]['status'] != 'ok':
        return None
    return (row[a][metric] - row[b][metric]) / row[b][metric]


def median_ci(values, seed=0):
    rng = random.Random(seed)
    boot = sorted(median(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP))
    return boot[int(0.025 * BOOTSTRAP)], boot[int(0.975 * BOOTSTRAP) - 1]


def holm(pvalues):
    """Return Holm-Bonferroni adjusted p-values in input order."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def cell_tests(rows):
    cells = sorted({(r['mean'], r['cv']) for r in rows})
    out = []
    for metric in METRICS:
        for a, b in PAIRS:
            group = []
            for cell in cells:
                members = [r for r in rows if (r['mean'], r['cv']) == cell]
                values = [v for v in (gap(r, metric, a, b) for r in members) if v is not None]
                entry = dict(metric=metric, pair=f'{a}-{b}', mean=cell[0], cv=cell[1],
                             n=len(values), failures={x: sum(r[x]['status'] != 'ok'
                                                             for r in members) for x in 'gcp'})
                if values:
                    entry.update(median=median(values), mean_gap=mean(values),
                                 positive=sum(v > 0 for v in values))
                if len(values) >= 6:
                    entry['median_ci95'] = median_ci(values)
                    entry['wilcoxon_p'] = float(stats.wilcoxon(values).pvalue)
                group.append(entry)
            tested = [e for e in group if 'wilcoxon_p' in e]
            for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
                entry['holm_p'] = adjusted
                entry['significant'] = adjusted < ALPHA
            out.extend(group)
    return out


def blocked(rows, metric, a, b, fixed_key, fixed_value, factor, levels):
    """Gaps per set id for every level of one factor, keeping complete blocks."""
    table = {}
    for r in rows:
        if r[fixed_key] == fixed_value and r[factor] in levels and r['cv'] > 0:
            value = gap(r, metric, a, b)
            if value is not None:
                table.setdefault(r['set_id'], {})[r[factor]] = value
    return [[block[level] for level in levels] for block in table.values()
            if len(block) == len(levels)]


def factor_tests(rows):
    means = sorted({r['mean'] for r in rows})
    cvs = sorted({r['cv'] for r in rows if r['cv'] > 0})
    out = []
    for metric in METRICS:
        for a, b in PAIRS:
            for fixed_key, fixed_values, factor, levels in (
                    ('mean', means, 'cv', cvs), ('cv', cvs, 'mean', means)):
                for fixed in fixed_values:
                    data = blocked(rows, metric, a, b, fixed_key, fixed, factor, levels)
                    entry = dict(metric=metric, pair=f'{a}-{b}', fixed=f'{fixed_key}={fixed}',
                                 factor=factor, levels=levels, blocks=len(data))
                    if len(data) >= 5 and len(levels) >= 3:
                        columns = list(zip(*data))
                        entry['friedman_p'] = float(stats.friedmanchisquare(*columns).pvalue)
                        entry['page_increasing_p'] = float(stats.page_trend_test(data).pvalue)
                        entry['level_medians'] = [median(c) for c in columns]
                    out.append(entry)
    return out


def per_cohort_tat_gap(rows):
    """Median absolute G-P TAT gap per measured cohort, in microseconds."""
    out = {}
    for r in rows:
        if r['g']['status'] == r['p']['status'] == 'ok':
            key = f'm{r["mean"]}/cv{r["cv"]}'
            out.setdefault(key, []).append(
                (r['g']['tat_ns'] - r['p']['tat_ns']) / r['p']['cohorts'] / 1000)
    return {k: dict(n=len(v), median_us=median(v)) for k, v in sorted(out.items())}


def markdown(cells):
    lines = ['| metric | pair | mean (ms) | CV | n | median gap | 95% CI | G>0 sets | Holm p | sig |',
             '|---|---|---:|---:|---:|---:|---|---:|---:|---|']
    for e in cells:
        ci = e.get('median_ci95')
        lines.append('| {metric} | {pair} | {mean} | {cv} | {n} | {med} | {ci} | {pos} | {p} | {sig} |'.format(
            metric=e['metric'][:3].upper(), pair=e['pair'].upper(), mean=e['mean'], cv=e['cv'],
            n=e['n'], med=f'{e["median"]:+.2%}' if 'median' in e else '-',
            ci=f'{ci[0]:+.2%} … {ci[1]:+.2%}' if ci else '-',
            pos=e.get('positive', '-'), p=f'{e["holm_p"]:.3g}' if 'holm_p' in e else '-',
            sig='yes' if e.get('significant') else 'no' if 'holm_p' in e else '-'))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = load(args.output / 'results.jsonl')
    cells = cell_tests(rows)
    report = dict(alpha=ALPHA, bootstrap=BOOTSTRAP, task_sets=len(rows), cells=cells,
                  factors=factor_tests(rows), per_cohort_tat_gap_g_minus_p=per_cohort_tat_gap(rows))
    (args.output / 'stats.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    (args.output / 'stats.md').write_text(markdown(cells))
    print(markdown(cells))


if __name__ == '__main__':
    main()
