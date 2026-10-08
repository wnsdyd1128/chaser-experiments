"""Paper-style figures for experiment 44 (confirming the pre-run check, policy-mix/confirm_analysis.py).

Reads <analysis dir>/confirm.json and the three confirm-* outputs, and writes into the analysis dir:
- confirm-outcomes: per task type and overall, sets accepted and met (success), accepted but missed (false accept),
  rejected although some configuration met (false reject) and rejected with none meeting (true reject), for the
  frozen RF, the static D + M rule and always using CHASER's placement.
- confirm-auc: AUC for CHASER meeting every deadline, overall and per task type, for the RF's probability, the
  static D + M score and the cache demand D (per-type values are descriptive; H1 is the overall comparison).
Usage: python3 confirm_bars.py <analysis dir> <.cache dir>   (PYTHONPATH: policy-mix, period-distribution)
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

import confirm_analysis as ca
import rf_devcheck as rd

D, CACHE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
result = json.loads((D / 'confirm.json').read_text())
records, _ = ca.sets(CACHE)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
GROUPS = (('all', 'All types'), ('confirm-small-v1', '32 KiB tasks'), ('confirm-big-v1', '768 KiB tasks'),
          ('confirm-mem-v1', 'Memory-bound tasks'))
METHODS = (('rf', 'Random forest (CHASER pre-run check)'), ('static', 'Static rule D + M < 0.975'),
           ('always', 'Always CHASER placement'))
OUTCOMES = (('success', 'Accepted and met every deadline', '#1b9e77', '//'),
            ('false_accept', 'Accepted but missed (false accept)', '#d95f02', 'xx'),
            ('false_reject', 'Rejected although a configuration met (false reject)', '#7570b3', '..'),
            ('true_reject', 'Rejected, no configuration met (true reject)', '#bbbbbb', '--'))


def save(fig, name, header, table):
    for ext in ('png', 'pdf'):
        fig.savefig(D / f'{name}.{ext}', bbox_inches='tight')
    with open(D / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')
    print('wrote', name)


fig, axes = plt.subplots(1, len(GROUPS), figsize=(15, 5.2), dpi=200, sharey=False)
table = []
for ax, (group, title) in zip(axes, GROUPS):
    t = result['overall'] if group == 'all' else result['groups'][group]
    for m, (method, _) in enumerate(METHODS):
        bottom = 0
        for key, _, color, hatch in OUTCOMES:
            v = t[method][key]
            ax.bar(m, v, 0.7, bottom=bottom, color=color, edgecolor='black', linewidth=0.6, hatch=hatch, zorder=3)
            if v:
                ax.text(m, bottom + v / 2, f'{v}', ha='center', va='center', fontsize=7.5,
                        bbox=dict(facecolor='white', edgecolor='none', pad=0.6, alpha=0.85))
            bottom += v
            table.append((group, method, key, v))
    ax.set_title(f"{title}\n({t['sets']} sets)", fontsize=9)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels(['Random\nforest', 'Static\nD + M', 'Always\nCHASER'], fontsize=8.5)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
axes[0].set_ylabel('Task sets')
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in OUTCOMES],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.97), fontsize=8.5)
fig.suptitle('Pre-run decisions on fresh task sets: outcome of the accepted or rejected configuration (experiment 44, pre-registered)',
             x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.87))
save(fig, 'confirm-outcomes', 'group,method,outcome,sets', table)

SCORES = (('p_chaser', 'Random forest probability', '#c51b7d', '++'), ('occupancy', 'Static D + M (L2 and memory)', '#7570b3', '..'),
          ('cache_demand', 'Cache demand D (earlier static rule)', '#8c6d31', '--'))
fig, ax = plt.subplots(figsize=(12, 4.8), dpi=200)
width, table = 0.8 / len(SCORES), []
for g, (group, title) in enumerate(GROUPS):
    rs = [r for r in records if r['p_chaser'] is not None and (group == 'all' or r['design'] == group)]
    y = [int(r['met']['ra-cgb']) for r in rs]
    for i, (key, _, color, hatch) in enumerate(SCORES):
        v = rd.auc(y, [r[key] if key == 'p_chaser' else -r[key] for r in rs])
        x = g + (i - (len(SCORES) - 1) / 2) * width
        ax.bar(x, v, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.annotate(f'{v:.3f}', (x, v), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
        table.append((group, key, f'{v:.4f}'))
ax.axhline(0.5, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
ax.set_xticks(range(len(GROUPS)))
ax.set_xticklabels([f"{title}\n({sum(1 for r in records if group == 'all' or r['design'] == group)} sets)" for group, title in GROUPS], fontsize=8.5)
ax.set_ylim(0, 1.12)
ax.set_ylabel('AUC, CHASER placement meets every deadline')
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
ax.text(0.005, 0.97, 'Higher is better ↑ (dotted line: chance)', transform=ax.transAxes, fontsize=8, va='top')
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SCORES],
           loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.965), fontsize=8.5)
fig.suptitle('Predicting whether CHASER\'s placement meets every deadline on fresh task sets (experiment 44, pre-registered)',
             x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.9))
save(fig, 'confirm-auc', 'group,score,auc', table)
