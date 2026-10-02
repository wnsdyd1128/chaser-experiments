"""Paper-style bars of measured TET, TAT and per-mode job CPU for the bimodal CLS run.

Bars: median over the task sets of a cell (failed runs excluded); whiskers: IQR.
Files (in <run dir>/figures):
  cls-bimodal-{tet,tat}-cv{00,10,20,30}   traffic as-is; panels = share of low-CLS tasks
  cls-bimodal-{tet,tat}-traffic[-pNNN]    one share of low-CLS tasks with matched cells
                                          (suffix omitted for 8 of 16); panels = CV; as-is vs matched
  cls-bimodal-jobcpu-{as-is,matched}[-pNNN]  same shares; mean job CPU of high- and low-CLS
                                          tasks, dashed line = isolated
Usage: python3 cls_bimodal_bars.py <run output dir> [results file] [--matched-only]
  results file  e.g. results-combined.jsonl of the matched extension (default results.jsonl)
  --matched-only  skip the as-is share figures (they belong to the main run)
"""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
O = Path(ARGS[0]).resolve()
rows = [json.loads(l) for l in open(Path(ARGS[1]).resolve() if len(ARGS) > 1 else O / 'results.jsonl')]
MATCHED_ONLY = '--matched-only' in sys.argv
MATCHED_FRACTIONS = sorted({r['mean'] for r in rows if r['traffic'] == 'matched'})
FRACTIONS, CVS = (0.0, 0.25, 0.5, 0.75, 1.0), (0.0, 0.1, 0.2, 0.3)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (mixed)', '#1baf7a', '\\\\'),
          ('p_grp', 'Partitioned (grouped)', '#e0b83a', 'xx'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def fmt(v):
    return f'{v:.2f}' if v < 10 else f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def cell(traffic, fraction, cv):
    return [r for r in rows if r['traffic'] == traffic and r['mean'] == fraction and r['cv'] == cv]


def draw(ax, groups, table, key):
    """groups: [(tick label, {series: values})]; one bar per series with data."""
    top, ticks = 0, []
    for g, (name, values) in enumerate(groups):
        for k, (series, _, color, hatch) in enumerate(SERIES):
            v = np.asarray(values.get(series, []), dtype=float)
            if not len(v):
                continue
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            x = g * (len(SERIES) + 1) + k
            top = max(top, q3)
            ax.bar(x, m, 0.8, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(x, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black',
                        elinewidth=0.8, capsize=2, zorder=4)
            ax.annotate(fmt(m), (x, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize=8.5 if len(groups) == 1 else 6.5)
            table.append((*key, name, series, len(v), m, q1, q3))
        ticks.append(g * (len(SERIES) + 1) + (len(SERIES) - 1) / 2)
    ax.set_ylim(0, top * 1.22)
    ax.set_xticks(ticks if len(groups) > 1 else [], [name for name, _ in groups] if len(groups) > 1 else [])
    ax.tick_params(axis='x', length=0)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')


def finish(fig, title, stem, table, header):
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, bbox_to_anchor=(0.55, 1.0), fontsize=10.5)
    fig.suptitle(title, x=0.01, ha='left', y=0.975, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write(header + ',group,series,n,median,q1,q3\n')
        for t in table:
            f.write(','.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


def metric_values(members, metric):
    return {s: [r[s][metric] / 1e6 for r in members if r[s]['status'] == 'ok'] for s, *_ in SERIES}


def suffix(fraction):
    return '' if fraction == 0.5 else f'-p{round(fraction * 100):03d}'


for metric, name in (('tet_ns', 'TET'), ('tat_ns', 'TAT')):
    for cv in () if MATCHED_ONLY else CVS:
        fig, axes = plt.subplots(1, len(FRACTIONS), figsize=(17, 4.2), dpi=200)
        table = []
        for j, fraction in enumerate(FRACTIONS):
            draw(axes[j], [('', metric_values(cell('as-is', fraction, cv), metric))], table, (name, cv, fraction))
            axes[j].set_title(f'Low-CLS tasks: {round(16 * fraction)} of 16', loc='left', fontsize=10)
        axes[0].set_ylabel(f'Measured {name} (ms)')
        finish(fig, f'CV = {cv}, workload O2', f'cls-bimodal-{name.lower()}-cv{round(cv * 100):02d}',
               table, 'metric,cv,low_fraction')
    for fraction in MATCHED_FRACTIONS:
        fig, axes = plt.subplots(1, len(CVS), figsize=(15, 4.2), dpi=200)
        table = []
        for j, cv in enumerate(CVS):
            draw(axes[j], [(f'traffic {t}', metric_values(cell(t, fraction, cv), metric)) for t in ('as-is', 'matched')],
                 table, (name, fraction, cv))
            axes[j].set_title(f'CV = {cv}', loc='left', fontsize=10)
        axes[0].set_ylabel(f'Measured {name} (ms)')
        finish(fig, f'{round(16 * fraction)} of 16 low-CLS tasks, workload O2',
               f'cls-bimodal-{name.lower()}-traffic{suffix(fraction)}', table, 'metric,low_fraction,cv')

for fraction in MATCHED_FRACTIONS:
    for traffic in ('as-is', 'matched'):
        fig, axes = plt.subplots(1, len(CVS), figsize=(15, 4.2), dpi=200)
        table = []
        for j, cv in enumerate(CVS):
            members = cell(traffic, fraction, cv)
            groups = []
            for mode in ('high', 'low'):
                pick = lambda r, values: np.mean([v for v, m in zip(values, r['modes']) if m == mode]) / 1e6
                groups.append((f'{mode}-CLS tasks', {s: [pick(r, r[s]['task_cpu_ns']) for r in members
                                                         if r[s]['status'] == 'ok'] for s, *_ in SERIES}))
            draw(axes[j], groups, table, (traffic, fraction, cv))
            isolated = np.median([np.mean(r['isolated_cpu_ns']) for r in members]) / 1e6
            axes[j].axhline(isolated, color='black', linestyle='--', linewidth=0.9, zorder=5)
            axes[j].text(0.98, isolated, 'isolated', transform=axes[j].get_yaxis_transform(), ha='right',
                         va='bottom', fontsize=7.5)
            axes[j].set_title(f'CV = {cv}', loc='left', fontsize=10)
        axes[0].set_ylabel('Measured job CPU (ms)')
        finish(fig, f'{round(16 * fraction)} of 16 low-CLS tasks, traffic {traffic}, workload O2',
               f'cls-bimodal-jobcpu-{traffic}{suffix(fraction)}', table, 'traffic,low_fraction,cv')
