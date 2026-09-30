"""Paper-style figures for the CLS-distribution run.

cls-gap-bars: median relative difference vs Partitioned (CLS zigzag), TAT and TET,
              per period and mean CLS; * marks Holm-adjusted Wilcoxon p < 0.05.
cls-{tet,tat}-bars: measured values of the five schedulers/placements.
Bars are medians over the task sets of a cell (CV = 0: one set); whiskers are IQR.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path('/workspace/experiments/chaser/.cache/cls-distribution-v1')
KEYS = ('g', 'c', 'c2', 'p', 'c_grp', 'c2_grp', 'p_grp')
rows = [r for r in map(json.loads, open(O / 'results.jsonl')) if all(r[k]['status'] == 'ok' for k in KEYS)]
stats = {p: json.load(open(O / f'stats-p{p:03d}.json')) for p in (20, 100)}
PERIODS, MEANS, CVS = (20, 100), (0.3, 0.5, 0.7), (0.0, 0.1, 0.2, 0.3)
G, C, C2, PZ, PG = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
                    ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (CLS zigzag)', '#1baf7a', '\\\\'),
                    ('p_grp', 'Partitioned (CLS grouped)', '#e87ba4', 'oo'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def cell(period, mean, cv):
    return [r for r in rows if r['period'] == period and r['mean'] == mean and r['cv'] == cv]


def significant(period, metric, key, mean, cv):
    return any(e['metric'] == metric and e['pair'] == f'{key}-p' and e['mean'] == mean and e['cv'] == cv
               and e.get('significant') for e in stats[period]['cells'])


def bars(ax, groups, series, width, label_fmt):
    """groups: list of per-CV dicts key -> array; draws medians with IQR whiskers."""
    x = np.arange(len(groups))
    for k, (key, label, color, hatch) in enumerate(series):
        pos = x + (k - (len(series) - 1) / 2) * width
        values = [np.array(g[key]) for g in groups]
        med = [np.median(v) for v in values]
        q1 = [np.percentile(v, 25) for v in values]
        q3 = [np.percentile(v, 75) for v in values]
        ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.errorbar(pos, med, yerr=[np.subtract(med, q1), np.subtract(q3, med)], fmt='none',
                    ecolor='black', elinewidth=0.7, capsize=1.6, zorder=4)
        for i, (p, m, lo, hi) in enumerate(zip(pos, med, q1, q3)):
            text = label_fmt(key, i, m)
            if text:
                y, va, dy = (hi, 'bottom', 2) if m >= 0 else (lo, 'top', -2)
                ax.annotate(text, (p, y), xytext=(0, dy), textcoords='offset points',
                            ha='center', va=va, rotation=90, fontsize=5.5)
    ax.set_xticks(x, [f'{cv:g}' for cv in CVS], fontsize=9)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)


def gap_figure():
    series = (G, C, C2, PG)
    fig, axes = plt.subplots(2, 6, figsize=(26, 8.4), dpi=200, sharey='row')
    table = []
    for i, (metric, name) in enumerate((('tat_ns', 'TAT'), ('tet_ns', 'TET'))):
        for j, (period, mean) in enumerate((p, m) for p in PERIODS for m in MEANS):
            ax = axes[i, j]
            groups = []
            for cv in CVS:
                members = cell(period, mean, cv)
                groups.append({key: [100 * (r[key][metric] / r['p'][metric] - 1) for r in members]
                               for key, *_ in series})
                for key, *_ in series:
                    v = groups[-1][key]
                    table.append((name, period, mean, cv, key, len(v), float(np.median(v)),
                                  significant(period, metric, key, mean, cv)))
            bars(ax, groups, series, 0.19, lambda key, idx, m: f'{m:+.2f}' + (
                '*' if significant(period, metric, key, mean, CVS[idx]) else ''))
            ax.axhline(0, color='black', linewidth=1.0, zorder=5)
            ax.set_title(f'({"ab"[i]}{j + 1}) {name}, T = {period} ms, mean CLS = {mean}', loc='left', fontsize=10)
            if j == 0:
                ax.set_ylabel(f'{name} difference vs.\nPartitioned (CLS zigzag) (%)')
            if i == 1:
                ax.set_xlabel('CLS coefficient of variation (σ/μ)')
            ax.text(0.02, 0.04, 'Lower is better ↓', transform=ax.transAxes, fontsize=8)
    axes[0, 0].set_ylim(-3.2, 3.2)
    axes[1, 0].set_ylim(-3.2, 2.4)
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series]
    fig.legend(handles=handles, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/cls-gap-bars.{ext}', bbox_inches='tight')
    with open(O / 'figures/cls-gap-bars.csv', 'w') as f:
        f.write('metric,period_ms,mean_cls,cv,series,n,median_pct,significant\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')


def absolute_figure(metric, name):
    series = (G, C, C2, PZ, PG)
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.6), dpi=200)
    table = []
    for i, period in enumerate(PERIODS):
        for j, mean in enumerate(MEANS):
            ax = axes[i, j]
            groups = [{key: [r[key][metric] / 1e6 for r in cell(period, mean, cv)] for key, *_ in series}
                      for cv in CVS]
            for cv, g in zip(CVS, groups):
                for key, *_ in series:
                    table.append((period, mean, cv, key, len(g[key]), float(np.median(g[key]))))
            bars(ax, groups, series, 0.16,
                 lambda key, idx, m: f'{m:.1f}' if m < 1000 else f'{m:.0f}')
            top = max(np.percentile(g[key], 75) for g in groups for key, *_ in series)
            ax.set_ylim(0, top * 1.3)
            ax.set_title(f'T = {period} ms, mean CLS = {mean}', loc='left', fontsize=10)
            if j == 0:
                ax.set_ylabel(f'Measured {name} (ms)')
            if i == 1:
                ax.set_xlabel('CLS coefficient of variation (σ/μ)')
            ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series]
    fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    stem = f'cls-{name.lower()}-bars'
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('period_ms,mean_cls,cv,series,n,median_ms\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')


gap_figure()
absolute_figure('tet_ns', 'TET')
absolute_figure('tat_ns', 'TAT')
print(len(rows), 'task sets plotted')
