"""Paper-style bars for the task-count run: measured TAT / TET and schedulable sets.

Files in <run dir>/figures:
  task-count-{tat,tet}-mem{00,25,50}-u{035,045}  panels = task-count group (12-14, 15-17,
        18-20); bars = G, C2 (1+1+2) and the four Partitioned placements; median over the
        sets where that configuration met every deadline, whiskers IQR, label = sets with a
        deadline miss
  task-count-schedulable-u{035,045}  panels = memory share; bars = sets meeting every
        deadline per configuration
Usage: python3 task_count_bars.py <run output dir>
"""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path(sys.argv[1]).resolve()
rows = [json.loads(l) for l in open(O / 'results.jsonl')]
counts = json.loads((O / 'protocol.json').read_text())['task_counts']
SERIES = (('g', 'Global', '#2a78d6', ''), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('p', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
          ('p_cgb', 'Partitioned (balanced CLS grouping)', '#9e9ac8', 'oo'),
          ('p_ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
          ('p_racgb', 'Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', '++'))
GROUPS = (('12-14 tasks', range(12, 15)), ('15-17 tasks', range(15, 18)), ('18-20 tasks', range(18, 21)))
MEMORY = sorted({r['heaviness'] for r in rows})
LOADS = sorted({r['load'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)
ok = lambda r, k: r[k].get('state') == 'ok'


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def finish(fig, title, stem, table, header):
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.55, 0.96), fontsize=9)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


for metric, label in (('tat_ns', 'TAT'), ('tet_ns', 'TET')):
    for memory in MEMORY:
        for load in LOADS:
            fig, axes = plt.subplots(1, len(GROUPS), figsize=(4.6 * len(GROUPS) + 1, 5.0), dpi=200)
            table = []
            for ax, (group, values) in zip(axes, GROUPS):
                members = [r for r in rows if r['heaviness'] == memory and r['load'] == load
                           and counts[r['set_id']] in values]
                top = 0
                for k, (key, _, color, hatch) in enumerate(SERIES):
                    v = np.array([r[key][metric] / 1e6 for r in members if ok(r, key)])
                    misses = sum(not ok(r, key) for r in members)
                    if len(v):
                        q1, m, q3 = np.percentile(v, [25, 50, 75])
                        top = max(top, q3)
                        ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                        ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8,
                                    capsize=2, zorder=4)
                        ax.annotate(fmt(m) + (f'\n{misses} miss' if misses else ''), (k, q3), xytext=(0, 2),
                                    textcoords='offset points', ha='center', va='bottom', fontsize=7)
                        table.append((group, key, len(v), m, q1, q3, misses))
                    else:
                        ax.annotate(f'{misses} miss', (k, 0), xytext=(0, 2), textcoords='offset points',
                                    ha='center', va='bottom', fontsize=7)
                        table.append((group, key, 0, float('nan'), float('nan'), float('nan'), misses))
                ax.set_ylim(0, top * 1.32 if top else 1)
                ax.set_xticks([])
                ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
                ax.set_title(f'{group} ({len(members)} sets)', loc='left', fontsize=9.5)
                ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
            axes[0].set_ylabel(f'Measured {label} (ms)')
            finish(fig, f'{label}: 768 KiB tasks hold {int(memory[3:])}% of U, per-core U {load}, periods {{20, 40, 80}} ms, '
                   'workload O2', f"task-count-{label.lower()}-{memory}-u{round(load * 100):03d}", table,
                   'group,configuration,n,median_ms,q1_ms,q3_ms,deadline_misses')

for load in LOADS:
    fig, axes = plt.subplots(1, len(MEMORY), figsize=(4.6 * len(MEMORY) + 1, 5.0), dpi=200)
    table = []
    for ax, memory in zip(axes, MEMORY):
        members = [r for r in rows if r['heaviness'] == memory and r['load'] == load]
        for k, (key, _, color, hatch) in enumerate(SERIES):
            count = sum(ok(r, key) for r in members)
            ax.bar(k, count, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.annotate(str(count), (k, count), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=8)
            table.append((memory, key, len(members), count))
        ax.set_ylim(0, len(members) * 1.18)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(f'768 KiB tasks hold {int(memory[3:])}% of U ({len(members)} sets)', loc='left', fontsize=9.5)
        ax.text(0.02, 0.97, 'Higher is better ↑', transform=ax.transAxes, fontsize=8, va='top')
    axes[0].set_ylabel('Task sets meeting every deadline')
    finish(fig, f'Schedulable task sets, 12-20 tasks, per-core U {load}, workload O2',
           f'task-count-schedulable-u{round(load * 100):03d}', table, 'memory,configuration,sets,schedulable')
