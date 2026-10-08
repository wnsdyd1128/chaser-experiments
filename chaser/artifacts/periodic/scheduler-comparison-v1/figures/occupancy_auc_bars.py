"""Post hoc figure for experiment 41: AUC for a missed deadline of the cache demand D (static rule) and of the
shared memory-system occupancy D + M (L2 requests x 48 ns plus memory accesses x 220 ns, from the YARDA outputs),
per experiment (Partitioned runs of experiments 17-27, and experiment 41).
Reads <dir>/posthoc-occupancy.json (posthoc_occupancy.py), writes <dir>/occupancy-auc.
Usage: python3 occupancy_auc_bars.py <dir>
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

D = Path(sys.argv[1]).resolve()
result = json.loads((D / 'posthoc-occupancy.json').read_text())
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
LABELS = {'17 and 18 mixed tasks': 'Exp. 17 and 18\nmixed tasks', '20 768 KiB': 'Exp. 20\n768 KiB tasks',
          '23 continuous CLS': 'Exp. 23\ncontinuous CLS', '24 32 KiB under load': 'Exp. 24\n32 KiB under load',
          '27 32 KiB': 'Exp. 27\n32 KiB tasks', '27 768 KiB': 'Exp. 27\n768 KiB tasks',
          '17-27 pooled': 'Exp. 17-27\nall runs', '41': 'Exp. 41\nL2 vs memory'}
groups = [k for k in LABELS if k in result and result[k]['d'] is not None]
SERIES = (('d', 'Cache demand D (L2 requests x 48 ns, static rule)', '#8c6d31', '--'),
          ('d_plus_m', 'D + M (plus memory accesses x 220 ns, YARDA p_mem)', '#7570b3', '..'))
fig, ax = plt.subplots(figsize=(13, 4.8), dpi=200)
width, table = 0.8 / len(SERIES), []
for i, (key, _, color, hatch) in enumerate(SERIES):
    for g, name in enumerate(groups):
        y = result[name][key]
        x = g + (i - (len(SERIES) - 1) / 2) * width
        ax.bar(x, y, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.annotate(f'{y:.3f}', (x, y), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
        table.append((name, key, f'{y:.4f}'))
ax.axhline(0.5, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
ax.set_xticks(range(len(groups)))
ax.set_xticklabels([f"{LABELS[g]}\n({result[g]['missed']} of {result[g]['rows']} missed)" for g in groups], fontsize=8)
ax.set_ylim(0, 1.12)
ax.set_ylabel('AUC for a missed deadline')
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
ax.text(0.005, 0.97, 'Higher is better ↑ (dotted line: chance)', transform=ax.transAxes, fontsize=8, va='top')
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.965), fontsize=8.5)
fig.suptitle('Static demand scores without training: L2 demand alone against L2 plus memory occupancy (post hoc, exploratory)',
             x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.88))
for ext in ('png', 'pdf'):
    fig.savefig(D / f'occupancy-auc.{ext}', bbox_inches='tight')
with open(D / 'occupancy-auc.csv', 'w') as f:
    f.write('experiment,score,auc\n')
    for t in table:
        f.write(','.join(t) + '\n')
print('wrote occupancy-auc')
