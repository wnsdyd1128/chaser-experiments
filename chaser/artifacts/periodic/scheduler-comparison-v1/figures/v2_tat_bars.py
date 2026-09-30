"""Paper-style grouped bars of measured TAT (ms) for G/C/P/C2 per mu and CV (v2 main run)."""
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
rows = [json.loads(l) for l in open(O / RESULTS)]
rows = [r for r in rows if all(r[a]['status'] == 'ok' for a in ('g', 'c', 'p', 'c2'))]
MEANS = sorted({r['mean'] for r in rows})
CVS = (0.0, 0.1, 0.2, 0.3)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned', '#1baf7a', '\\\\'))
METRICS = (('tat_ns', 'TAT'),)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})

def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'

fig, axes = plt.subplots(1, len(MEANS), figsize=(4.6 * len(MEANS), 4.6), dpi=200, squeeze=False)
width, x = 0.2, np.arange(len(CVS))
table = []
for i, (metric, name) in enumerate(METRICS):
    for j, mean in enumerate(MEANS):
        ax = axes[i, j]
        top = 0
        for k, (arch, label, color, hatch) in enumerate(SERIES):
            med, lo, hi = [], [], []
            for cv in CVS:
                v = np.array([r[arch][metric] for r in rows if r['mean'] == mean and r['cv'] == cv]) / 1e6
                q1, m, q3 = np.percentile(v, [25, 50, 75])
                med.append(m); lo.append(m - q1); hi.append(q3 - m); top = max(top, q3)
                table.append((name, mean, cv, arch, len(v), m, q1, q3))
            pos = x + (k - 1.5) * width
            ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(pos, med, yerr=[lo, hi], fmt='none', ecolor='black', elinewidth=0.7, capsize=1.8, zorder=4)
            for p, m, h in zip(pos, med, hi):
                ax.annotate(fmt(m), (p, m + h), xytext=(0, 2), textcoords='offset points',
                            ha='center', va='bottom', rotation=90, fontsize=6.5)
        ax.set_ylim(0, top * 1.32)
        cohorts = [int(np.median([r['p']['cohorts'] for r in rows if r['mean'] == mean and r['cv'] == cv])) for cv in CVS]
        ax.set_xticks(x, [f'{cv:g}\n({c} coh.)' if i == 0 else f'{cv:g}' for cv, c in zip(CVS, cohorts)], fontsize=9)
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        window = 18 * mean
        ax.set_title(f'μ = {mean} ms  (measurement window {window:,} ms)', loc='left', fontsize=10)
        if j == 0:
            ax.set_ylabel(f'Measured {name} (ms)')
        ax.set_xlabel('Period CV (σ/μ)')
        ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
fig.legend(handles=handles, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.9))
for ext in ('png', 'pdf'):
    fig.savefig(O / f'figures/v2-tat-bars{SUFFIX}.{ext}', bbox_inches='tight')
with open(O / f'figures/v2-tat-bars{SUFFIX}.csv', 'w') as f:
    f.write('metric,mean_ms,cv,architecture,n,median_ms,q1_ms,q3_ms\n')
    for t in table:
        f.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in t) + '\n')
print(len(table), 'bars written')
