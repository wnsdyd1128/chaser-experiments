"""Paper-style measured TAT bars with the release-aware Partitioned placement (P') added.

G/C/C2/P come from the main run (zigzag placement); P' comes from the cohort
control on the same task sets. The control has no CV = 0 sets, so that slot is empty.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path(__file__).resolve().parents[4] / '.cache/period-distribution-v2'
CONTROL = Path(__file__).resolve().parents[4] / '.cache/period-distribution-cohort-v2'
main = [json.loads(l) for l in open(O / 'results.jsonl')]
main = [r for r in main if all(r[a]['status'] == 'ok' for a in ('g', 'c', 'p', 'c2'))]
control = {(r['mean'], r['cv'], r['set_id']): r for r in map(json.loads, open(CONTROL / 'results.jsonl'))
           if r['p']['status'] == 'ok'}
for r in main:
    other = control.get((r['mean'], r['cv'], r['set_id']))
    r['pr'] = other['p'] if other else None
MEANS = sorted({r['mean'] for r in main})
CVS = (0.0, 0.1, 0.2, 0.3)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (zigzag)', '#1baf7a', '\\\\'),
          ('pr', 'Partitioned (release-aware)', '#eda100', 'xx'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


fig, axes = plt.subplots(1, len(MEANS), figsize=(4.9 * len(MEANS), 4.6), dpi=200)
width, x = 0.16, np.arange(len(CVS))
table = []
for ax, mean in zip(axes, MEANS):
    top = 0
    for k, (arch, label, color, hatch) in enumerate(SERIES):
        pos, med, lo, hi = [], [], [], []
        for i, cv in enumerate(CVS):
            v = np.array([r[arch]['tat_ns'] for r in main
                          if r['mean'] == mean and r['cv'] == cv and r[arch] is not None]) / 1e6
            if not len(v):
                continue
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            pos.append(x[i] + (k - 2) * width)
            med.append(m); lo.append(m - q1); hi.append(q3 - m); top = max(top, q3)
            table.append((mean, cv, arch, len(v), m, q1, q3))
        ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.errorbar(pos, med, yerr=[lo, hi], fmt='none', ecolor='black', elinewidth=0.7, capsize=1.6, zorder=4)
        for p, m, h in zip(pos, med, hi):
            ax.annotate(fmt(m), (p, m + h), xytext=(0, 2), textcoords='offset points',
                        ha='center', va='bottom', rotation=90, fontsize=6)
    ax.set_ylim(0, top * 1.34)
    cohorts = [int(np.median([r['p']['cohorts'] for r in main if r['mean'] == mean and r['cv'] == cv])) for cv in CVS]
    ax.set_xticks(x, [f'{cv:g}\n({c} coh.)' for cv, c in zip(CVS, cohorts)], fontsize=9)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_title(f'μ = {mean} ms  (measurement window {18 * mean:,} ms)', loc='left', fontsize=10)
    ax.set_xlabel('Period CV (σ/μ)')
    ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
axes[0].set_ylabel('Measured TAT (ms)')
handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.9))
for ext in ('png', 'pdf'):
    fig.savefig(O / f'figures/v2-tat-bars-release-aware.{ext}', bbox_inches='tight')
with open(O / 'figures/v2-tat-bars-release-aware.csv', 'w') as f:
    f.write('mean_ms,cv,architecture,n,median_ms,q1_ms,q3_ms\n')
    for t in table:
        f.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in t) + '\n')
print(len(table), 'bars written;', sum(r['pr'] is not None for r in main), 'task sets with P\'')
