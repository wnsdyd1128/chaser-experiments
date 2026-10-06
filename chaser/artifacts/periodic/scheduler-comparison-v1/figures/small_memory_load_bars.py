"""Paper-style bars for the small-memory load run: schedulable sets and worst execution inflation.

Files in <run dir>/figures, one per cell (period CV x low-CLS share), panels = per-core load:
  small-memory-load-schedulable-<cell>  bars = G, C2 (1+1+2) and the four Partitioned placements;
        sets meeting every deadline (startup failures are labelled and not counted)
  small-memory-load-wcet-<cell>  bars = the four Partitioned placements; median over the sets where
        all four met every deadline of the worst memory-task job CPU / planned budget, whiskers IQR
        (needs rt_metrics.py's rt-metrics.json)
Usage: python3 small_memory_load_bars.py <run output dir>
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
rt = json.loads((O / 'rt-metrics.json').read_text())['cases']
SERIES = (('g', None, 'Global', '#2a78d6', ''), ('c2', None, 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('p', 'wfd', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
          ('p_cgb', 'cgb', 'Partitioned (balanced CLS grouping)', '#9e9ac8', 'oo'),
          ('p_ra', 'ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
          ('p_racgb', 'ra-cgb', 'Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', '++'))
PARTITIONED = [s for s in SERIES if s[1]]
CELLS = sorted({r['heaviness'] for r in rows})
LOADS = sorted({r['load'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def describe(cell):
    cv, low = cell.split('-')
    return f'32 KiB low-CLS tasks hold {int(low[3:])}% of U, period CV {int(cv[2:]) / 100}'


def save(fig, series, title, stem, table, header):
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, _, l, c, h in series]
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


for cell in CELLS:
    fig, axes = plt.subplots(1, len(LOADS), figsize=(4.4 * len(LOADS) + 1, 5.0), dpi=200)
    table = []
    for ax, load in zip(axes, LOADS):
        members = [r for r in rows if r['heaviness'] == cell and r['load'] == load]
        for k, (key, _, _, color, hatch) in enumerate(SERIES):
            ok = sum(r[key].get('state') == 'ok' for r in members)
            excluded = sum(r[key].get('state') in ('startup', 'other') for r in members)
            ax.bar(k, ok, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.annotate(f'{ok}' + (f'\n{excluded} excl.' if excluded else ''), (k, ok), xytext=(0, 2),
                        textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
            table.append((load, key, len(members), ok, excluded))
        ax.set_ylim(0, len(members) * 1.25)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(f'Per-core U {load} ({len(members)} sets)', loc='left', fontsize=9.5)
        ax.text(0.02, 0.97, 'Higher is better ↑', transform=ax.transAxes, fontsize=8, va='top')
    axes[0].set_ylabel('Task sets meeting every deadline')
    save(fig, SERIES, f'Schedulable task sets: {describe(cell)}, 12-20 tasks, workload O2',
         f'small-memory-load-schedulable-{cell}', table, 'load,configuration,sets,schedulable,excluded')

    fig, axes = plt.subplots(1, len(LOADS), figsize=(4.4 * len(LOADS) + 1, 5.0), dpi=200)
    table = []
    for ax, load in zip(axes, LOADS):
        keys = [k for k, v in rt.items() if k.startswith(f'{cell}/u{round(load * 100):03d}/')
                and all(v.get(b) and v[b]['worst_memory_inflation'] for _, b, *_ in PARTITIONED)]
        top = 0
        for k, (_, build, _, color, hatch) in enumerate(PARTITIONED):
            v = np.array([rt[c][build]['worst_memory_inflation'] for c in keys])
            if not len(v):
                continue
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2,
                        zorder=4)
            ax.annotate(f'{m:.2f}x', (k, q3), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=7.5)
            table.append((load, build, len(v), m, q1, q3))
        ax.set_ylim(0, top * 1.25 if top else 1)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(f'Per-core U {load} ({len(keys)} sets, all four met deadlines)', loc='left', fontsize=9)
        ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0].set_ylabel('Worst memory-task job CPU / isolated budget')
    save(fig, PARTITIONED, f'Worst execution inflation of memory-bound tasks: {describe(cell)}, 12-20 tasks',
         f'small-memory-load-wcet-{cell}', table, 'load,placement,sets,median,q1,q3')
