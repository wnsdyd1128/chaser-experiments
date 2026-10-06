"""Paper-style figures for experiment 27 (deadline-small / deadline-big): deadlines, violated jobs, inflation, TET.

Files in <run dir>/figures:
  <study>-met-<cell>       lines over per-core U: task sets meeting every deadline, per configuration
                           (G, C2 (1+1+2), the four Partitioned placements, random as the mean of its
                           three draws); startup failures are not counted
  <study>-violated-<cell>  lines over per-core U: violated jobs / released jobs of the Partitioned runs
                           (rt_metrics.py), summed over the sets of each point
  <study>-inflation        bars per period cell: median worst memory-task job CPU / planned budget over
                           the cases where all four deterministic placements met every deadline, whiskers IQR
  <study>-tet              the same cases: median TET (ms), whiskers IQR
Usage: python3 deadline_confirm_bars.py <deadline run output dir>
"""
import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

O = Path(sys.argv[1]).resolve()
STUDY = O.name.removesuffix('-v1')
rows = [json.loads(l) for l in open(O / 'results.jsonl')]
rt = json.loads((O / 'rt-metrics.json').read_text())['cases']
DRAWS = ('p_rnd0', 'p_rnd1', 'p_rnd2')
SERIES = (('g', None, 'Global', '#2a78d6', 'o', '-'),
          ('c2', None, 'Clustered (1+1+2)', '#4a3aa7', 's', '-'),
          ('p', 'wfd', 'Partitioned (U-balanced, WFD)', '#8c6d31', 'v', '--'),
          ('p_cgb', 'cgb', 'Partitioned (balanced CLS grouping)', '#9e9ac8', 'D', '--'),
          ('p_ra', 'ra', 'Partitioned (release-aware)', '#1baf7a', '^', '--'),
          ('p_racgb', 'ra-cgb', 'Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', 'P', '-'),
          ('rnd', 'rnd', 'Partitioned (random, mean of 3 draws)', '#7f7f7f', 'x', ':'))
PARTITIONED = [s for s in SERIES if s[1]]
DETERMINISTIC = [s for s in PARTITIONED if s[1] != 'rnd']
HATCHES = {'wfd': '--', 'cgb': 'oo', 'ra': '\\\\', 'ra-cgb': '++'}
CELLS = sorted({r['heaviness'] for r in rows})
LOADS = sorted({r['load'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def label(r):
    return f"{r['heaviness']}/u{round(r['load'] * 100):03d}/s{r['set_id']:02d}"


def describe(cell):
    cv, memory = cell.split('-')
    share = int(memory[-2:])
    kind = '32 KiB low-CLS tasks' if memory.startswith('low') else '768 KiB tasks'
    return f'{kind} hold {share}% of U, period CV {int(cv[2:]) / 100}'


def save(fig, handles, title, stem, table, header, ncol=2):
    fig.legend(handles=handles, loc='upper center', ncol=ncol, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


def met_count(members, key):
    if key == 'rnd':
        runs = [r[d]['state'] for r in members for d in DRAWS if r[d]['state'] in ('ok', 'deadline')]
        return sum(s == 'ok' for s in runs) / 3, len(runs) / 3
    runs = [r[key]['state'] for r in members if r[key]['state'] in ('ok', 'deadline')]
    return sum(s == 'ok' for s in runs), len(runs)


def violated(members, build):
    builds = ('rnd0', 'rnd1', 'rnd2') if build == 'rnd' else (build,)
    entries = [rt[label(r)][b] for r in members for b in builds]
    entries = [e for e in entries if e and e['state'] in ('ok', 'deadline')]
    return 100 * sum(e['missed_jobs'] for e in entries) / sum(e['expected_jobs'] for e in entries)


line_handles = [Line2D([], [], color=c, marker=m, linestyle=ls, label=l) for _, _, l, c, m, ls in SERIES]
for cell in CELLS:
    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=200)
    table = []
    for key, _, name, color, marker, ls in SERIES:
        ys = []
        for load in LOADS:
            members = [r for r in rows if r['heaviness'] == cell and r['load'] == load]
            ok, n = met_count(members, key)
            ys.append(ok)
            table.append((load, name, n, ok))
        ax.plot(LOADS, ys, color=color, marker=marker, linestyle=ls, linewidth=1.4, markersize=5, zorder=3)
    ax.set_xticks(LOADS)
    ax.set_xlabel('Per-core nominal U')
    ax.set_ylabel('Task sets meeting every deadline (of 18)')
    ax.set_ylim(-0.5, 19.5)
    ax.grid(color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.98, 0.97, 'Higher is better ↑', transform=ax.transAxes, fontsize=8, va='top', ha='right')
    save(fig, line_handles, f'Schedulable task sets: {describe(cell)}, 12-20 tasks, new sets (experiment 27)',
         f'{STUDY}-met-{cell}', table, 'load,configuration,measured_sets,sets_meeting_every_deadline')

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=200)
    table = []
    for _, build, name, color, marker, ls in PARTITIONED:
        ys = [violated([r for r in rows if r['heaviness'] == cell and r['load'] == load], build) for load in LOADS]
        table += [(load, name, y) for load, y in zip(LOADS, ys)]
        ax.plot(LOADS, ys, color=color, marker=marker, linestyle=ls, linewidth=1.4, markersize=5, zorder=3)
    ax.set_xticks(LOADS)
    ax.set_xlabel('Per-core nominal U')
    ax.set_ylabel('Deadline-violating jobs / released jobs (%)')
    ax.grid(color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    save(fig, line_handles[2:], f'Deadline-violating jobs: {describe(cell)}, 12-20 tasks, new sets (experiment 27)',
         f'{STUDY}-violated-{cell}', table, 'load,placement,violated_percent')

for metric, field, scale, ylabel, unit in (
        ('inflation', 'worst_memory_inflation', 1.0, 'Worst memory-task job CPU / planned budget', 'x'),
        ('tet', 'tet_ns', 1e-6, 'Total execution time, TET (ms)', ' ms')):
    fig, axes = plt.subplots(1, len(CELLS), figsize=(5.2 * len(CELLS) + 1, 5.0), dpi=200)
    table = []
    for ax, cell in zip(axes, CELLS):
        members = [r for r in rows if r['heaviness'] == cell and all(r[k]['state'] == 'ok' for k, *_ in DETERMINISTIC)]
        top = 0
        for i, (key, build, _, color, _, _) in enumerate(DETERMINISTIC):
            v = np.array([(rt[label(r)][build][field] if field != 'tet_ns' else r[key]['tet_ns']) * scale
                          for r in members])
            if not len(v):
                continue
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(i, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=HATCHES[build], zorder=3)
            ax.errorbar(i, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2, zorder=4)
            ax.annotate(f'{m:.2f}{unit}' if unit == 'x' else f'{m:.0f}{unit}', (i, q3), xytext=(0, 2),
                        textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
            table.append((cell, build, len(v), m, q1, q3))
        ax.set_ylim(0, top * 1.2 if top else 1)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(f'{describe(cell)} ({len(members)} cases, all four met deadlines)', loc='left', fontsize=8.5)
        ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0].set_ylabel(ylabel)
    handles = [Patch(facecolor=c, edgecolor='black', hatch=HATCHES[b], label=l) for _, b, l, c, _, _ in DETERMINISTIC]
    what = 'Worst execution inflation of memory-bound tasks' if metric == 'inflation' else 'Total execution time'
    save(fig, handles, f'{what}: 12-20 tasks, all loads pooled, new sets (experiment 27)', f'{STUDY}-{metric}',
         table, 'cell,placement,cases,median,q1,q3')
