"""Paper-style grouped bars of measured makespan (ms) for G/C/P/C2 per mu and CV (v2 main run).

Makespan runs from the measurement-window start (earliest nominal release of a
measured job) to the last measured job completion, recomputed from raw jobs.
"""
import glob
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path('/workspace/experiments/chaser/.cache/period-distribution-v2')
import sys
# Primary analysis keeps every random draw (n = 20); --dedup merges identical task sets.
DEDUP = '--dedup' in sys.argv
SUFFIX = '-dedup' if DEDUP else ''
RESULTS = 'results-dedup.jsonl' if DEDUP else 'results.jsonl'
STATS = 'stats-dedup.json' if DEDUP else 'stats.json'
ARCHS = ('g', 'c', 'c2', 'p')
KEEP = {(r['mean'], r['cv'], r['set_id']) for r in map(json.loads, open(O / RESULTS))} if DEDUP else None
rows = []
for d in sorted(glob.glob(str(O / 'm*/cv*/s*'))):
    cfg = json.load(open(f'{d}/configuration.json'))
    pd = cfg['period_distribution']
    if KEEP is not None and (pd['mean_ticks'], pd['cv'], pd['set_id']) not in KEEP:
        continue
    warm = {i: cfg['warmup_ticks'] // t['period_ticks'] for i, t in enumerate(cfg['tasks'])}
    recs = {a: json.loads(open(f'{d}/{a}/measurements.jsonl').read().splitlines()[0]) for a in ARCHS}
    if any(r['execution_status'] != 'ok' for r in recs.values()):
        continue
    measured = {a: [j for j in r['jobs'] if j['job'] >= warm[j['task']]] for a, r in recs.items()}
    start = min(j['release_ns'] for j in measured['p'])
    row = dict(mean=cfg['period_distribution']['mean_ticks'], cv=cfg['period_distribution']['cv'])
    for a in ARCHS:
        row[a] = max(j['completion_ns'] for j in measured[a]) - start
    rows.append(row)
MEANS = sorted({r['mean'] for r in rows})
CVS = (0.0, 0.1, 0.2, 0.3)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned', '#1baf7a', '\\\\'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


fig, axes = plt.subplots(1, len(MEANS), figsize=(4.6 * len(MEANS), 4.6), dpi=200)
width, x = 0.2, np.arange(len(CVS))
table = []
for ax, mean in zip(axes, MEANS):
    top = 0
    for k, (arch, label, color, hatch) in enumerate(SERIES):
        med, lo, hi = [], [], []
        for cv in CVS:
            v = np.array([r[arch] for r in rows if r['mean'] == mean and r['cv'] == cv]) / 1e6
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            med.append(m); lo.append(m - q1); hi.append(q3 - m); top = max(top, q3)
            table.append(('makespan', mean, cv, arch, len(v), m, q1, q3))
        pos = x + (k - 1.5) * width
        ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.errorbar(pos, med, yerr=[lo, hi], fmt='none', ecolor='black', elinewidth=0.7, capsize=1.8, zorder=4)
        for p, m, h in zip(pos, med, hi):
            ax.annotate(fmt(m), (p, m + h), xytext=(0, 2), textcoords='offset points',
                        ha='center', va='bottom', rotation=90, fontsize=6.5)
    ax.set_ylim(0, top * 1.32)
    ax.set_xticks(x, [f'{cv:g}' for cv in CVS], fontsize=9)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_title(f'μ = {mean} ms  (measurement window {18 * mean:,} ms)', loc='left', fontsize=10)
    ax.set_xlabel('Period CV (σ/μ)')
    ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
axes[0].set_ylabel('Measured makespan (ms)')
handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
fig.legend(handles=handles, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.9))
for ext in ('png', 'pdf'):
    fig.savefig(O / f'figures/v2-makespan-bars{SUFFIX}.{ext}', bbox_inches='tight')
with open(O / f'figures/v2-makespan-bars{SUFFIX}.csv', 'w') as f:
    f.write('metric,mean_ms,cv,architecture,n,median_ms,q1_ms,q3_ms\n')
    for t in table:
        f.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in t) + '\n')
print(len(rows), 'task sets,', len(table), 'bars written')
