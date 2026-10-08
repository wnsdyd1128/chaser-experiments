"""Paper-style figures for experiment 41 (memory cost, policy-mix/memcost_analysis.py).

Reads <analysis dir>/memory-cost.json and writes into it:
- memory-cost-met: per placement and load, task sets meeting every deadline when the memory tasks hit L2 (l2)
  and when they go to memory (mem) at the same CLS and U.
- memory-cost-auc: AUC for a missed deadline on this experiment's runs, per placement and pooled, for the cache
  demand D (static rule), max(D, M) with the YARDA memory demand M, the experiment 35 main random forest and the
  same forest with the p_mem distribution statistics (both trained on experiments 17-27).
- memory-cost-who: per placement and cell, tasks late at least once by class.
Usage: python3 memcost_bars.py <analysis dir>
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

D = Path(sys.argv[1]).resolve()
result = json.loads((D / 'memory-cost.json').read_text())
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
PLACEMENTS = (('wfd', 'Partitioned, U-balanced (WFD)'), ('cgb', 'Partitioned, balanced CLS grouping'))
CELLS = (('l2-low25', 'Memory tasks hit L2 (32 KiB)', '#1b9e77', '//'),
         ('mem-low25', 'Memory tasks go to memory (same CLS and U)', '#d95f02', '\\\\'))


def save(fig, name, header, table):
    for ext in ('png', 'pdf'):
        fig.savefig(D / f'{name}.{ext}', bbox_inches='tight')
    with open(D / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')
    print('wrote', name)


def panels(name, title, ylabel, note, groups, series, value, ylim=None, fmt='{}'):
    fig, axes = plt.subplots(1, len(groups), figsize=(13, 4.8), dpi=200, sharey=True)
    table, top = [], 0
    for ax, (group, gtitle, xs) in zip(axes, groups):
        width = 0.8 / len(series)
        for i, (key, _, color, hatch) in enumerate(series):
            for g, (x_key, _) in enumerate(xs):
                y = value(group, key, x_key)
                x = g + (i - (len(series) - 1) / 2) * width
                ax.bar(x, 0 if y is None else y, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                ax.annotate('-' if y is None else fmt.format(y), (x, 0 if y is None else y), xytext=(0, 2), textcoords='offset points',
                            ha='center', va='bottom', fontsize=7.5)
                top = max(top, y or 0)
                table.append((group, key, x_key, y))
        ax.set_title(gtitle, fontsize=9)
        ax.set_xticks(range(len(xs)))
        ax.set_xticklabels([label for _, label in xs], fontsize=8.5)
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    axes[0].set_ylabel(ylabel)
    axes[0].set_ylim(*(ylim or (0, top * 1.18 if top else 1)))
    axes[0].text(0.01, 0.97, note, transform=axes[0].transAxes, fontsize=8, va='top')
    fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series],
               loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.965), fontsize=8.5)
    fig.suptitle(f'{title} (experiment 41, pre-registered)', x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    save(fig, name, 'group,series,x,value', table)


loads = sorted({float(k.split()[1]) for k in result['by_load']})
groups = [(b, f"{t}\n(McNemar p = {result['primary'][b]['p']:.3f}, Holm p = {result['primary'][b]['holm_p']:.3f})",
           [(load, f"per-core load {load}\n({result['by_load'][f'{b} {load}']['pairs']} pairs)") for load in loads])
          for b, t in PLACEMENTS]
panels('memory-cost-met', 'Same CLS and U, memory tasks hitting L2 or going to memory', 'Task sets meeting every deadline',
       'Higher is better ↑', groups, CELLS,
       lambda b, cell, load: result['by_load'][f'{b} {load}']['l2_met' if cell.startswith('l2') else 'mem_met'])

PREDICTORS = (('cache demand D', 'Cache demand D (static rule)', '#8c6d31', '--'),
              ('max(D, M)', 'max(D, M): with the YARDA memory demand M', '#7570b3', '..'),
              ('f35', 'Random forest, experiment 35 main features', '#c51b7d', '++'),
              ('f35 + p_mem statistics', 'Random forest, main features + p_mem statistics', '#66a61e', 'xx'))
auc = result['predictors']['auc']

fig, ax = plt.subplots(figsize=(12, 4.8), dpi=200)
xs, width, table = list(auc), 0.8 / len(PREDICTORS), []
for i, (key, label, color, hatch) in enumerate(PREDICTORS):
    for g, runs in enumerate(xs):
        y = auc[runs][key]
        x = g + (i - (len(PREDICTORS) - 1) / 2) * width
        ax.bar(x, 0 if y is None else y, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.annotate('-' if y is None else f'{y:.3f}', (x, 0 if y is None else y), xytext=(0, 2), textcoords='offset points',
                    ha='center', va='bottom', fontsize=7.5)
        table.append((runs, key, y))
ax.axhline(0.5, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
ax.set_xticks(range(len(xs)))
ax.set_xticklabels({'pooled': 'Both placements', 'wfd': 'U-balanced (WFD)', 'cgb': 'Balanced CLS grouping'}.get(x, x) for x in xs)
ax.set_ylim(0, 1.12)
ax.set_ylabel('AUC for a missed deadline')
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
ax.text(0.005, 0.97, 'Higher is better ↑ (dotted line: chance)', transform=ax.transAxes, fontsize=8, va='top')
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in PREDICTORS],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.965), fontsize=8.5)
fig.suptitle('Predicting a missed deadline on the experiment 41 runs (forests trained on experiments 17-27)',
             x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.86))
save(fig, 'memory-cost-auc', 'runs,predictor,auc', table)

CLASSES = (('memory', 'Memory tasks (low CLS)', '#7570b3', '..'),
           ('other-with-memory', 'Other tasks on a core holding memory tasks', '#e7298a', 'xx'),
           ('other-without-memory', 'Tasks on a core without memory tasks', '#8c6d31', '--'))
groups = [(b, t, [(cell, label) for cell, label, *_ in CELLS]) for b, t in PLACEMENTS]
panels('memory-cost-who', 'Which tasks were late', 'Tasks late at least once (all loads)', 'Lower is better ↓',
       groups, CLASSES, lambda b, cls, cell: result['who_late'][f'{cell} {b}'][cls]['late_tasks'])
