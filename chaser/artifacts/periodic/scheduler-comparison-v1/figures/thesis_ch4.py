"""Thesis chapter 4 figures 4.1-4.5 and table 4-tet (measured values, full names, no in-figure title).

Figures are drawn at the final 16 cm text width, so the font sizes below are the printed sizes.
figure-4-1  shared-L2 probe (results/l2-probe/probe.json): CPU time per load against concurrent tasks; (a) 32 KiB and
            3 MiB arrays with the 48 ns x tasks and 220 ns x tasks reference lines, (b) 512, 640 and 768 KiB arrays
figure-4-2  32 KiB low-CLS tasks at 50 % of U (results/small-memory-load/results.jsonl): task sets meeting every
            deadline per load for the four Partitioned placements, period CV 0 and 0.2 (no Partitioned run failed to start)
figure-4-3  the same tasks at load 0.5, runs that met every deadline (thesis-ch4/core-load-runs.csv, from
            thesis_ch4_core_load.py): planned and effective (measured job CPU / measured window) U of the cores holding
            the grouped low-CLS tasks and of the other cores. A task stops at its first deadline miss, so runs that
            missed would show the load after some tasks stopped.
figure-4-4  experiment 41 (results/memory-cost-analysis/memory-cost.json): sets meeting every deadline per load,
            L2-hitting against memory-bound tasks with matched CLS (within 0.005) and target U
figure-4-5  the same runs: share of task observations (one per task per run, all loads and sets) with a late job
table-4-tet paired TET gap, release-aware within balanced CLS grouping against release-aware, behind the section 4.3
            text (results/small-memory-load and results/task-count statistics)
Usage: python3 thesis_ch4.py <output dir>
"""
import csv
import json
from pathlib import Path
from statistics import median
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parents[1]
R = HERE / 'results'
CORE_LOAD = HERE / 'thesis-ch4/core-load-runs.csv'
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
WIDTH = 16 / 2.54
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 8, 'axes.titlesize': 8.5,
                     'axes.labelsize': 8, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5,
                     'hatch.linewidth': 0.8, 'axes.linewidth': 0.8})
LABEL = 7  # bar and point value labels, printed size
# Okabe-Ito colour-blind-safe palette (Wong, Nature Methods 8:441, 2011); light tints are 40 % colour on white.
BLUE, VERMILLION, GREEN, ORANGE, PURPLE = '#0072B2', '#D55E00', '#009E73', '#E69F00', '#CC79A7'
LIGHT_BLUE, LIGHT_VERMILLION = '#99C7E0', '#EEBF99'
PLACEMENTS = (('p', 'Partitioned (U-balanced, WFD)', BLUE, ''),
              ('p_ra', 'Partitioned (release-aware)', GREEN, '/'),
              ('p_cgb', 'Partitioned (balanced CLS grouping)', ORANGE, '\\'),
              ('p_racgb', 'Partitioned (release-aware within balanced CLS grouping)', PURPLE, 'x'))


def save(fig, name, header, table):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight', dpi=300)
    with open(OUT / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for row in table:
            f.write(','.join(str(v) for v in row) + '\n')
    plt.close(fig)
    print('wrote', name)


def bar(ax, x, value, width, color, hatch, text=None, hatch_color='black'):
    # Hatch lines take the edge colour (no separate hatch colour in matplotlib 3.10), so the black outline is a second bar.
    ax.bar(x, value, width, color=color, edgecolor=hatch_color, linewidth=0, hatch=hatch, zorder=3)
    ax.bar(x, value, width, fill=False, edgecolor='black', linewidth=0.5, zorder=4)
    ax.annotate(text if text is not None else f'{value}', (x, value), xytext=(0, 1.5), textcoords='offset points',
                ha='center', va='bottom', fontsize=LABEL)


def swatch(color, hatch, hatch_color='black'):
    """Legend handle matching bar(): hatched fill under a black outline (drawn overlaid by HandlerTuple)."""
    return (Patch(facecolor=color, edgecolor=hatch_color, linewidth=0, hatch=hatch),
            Patch(fill=False, edgecolor='black', linewidth=0.5))


def grid(ax):
    ax.grid(axis='y', color='#eeeeee', linewidth=0.5, zorder=0)


# Figure 4.1: shared-L2 probe
probe = json.loads((R / 'l2-probe/probe.json').read_text())
series = {}
for row in probe['rows']:
    series.setdefault(row['kib'], []).append((row['count'], row['ns_per_access']))
name = {32: '32 KiB array per task', 512: '512 KiB array per task', 640: '640 KiB array per task',
        768: '768 KiB array per task', 3072: '3 MiB array per task'}
style = {32: (BLUE, 'o'), 3072: (VERMILLION, 's'), 512: (GREEN, '^'), 640: (PURPLE, 'D'), 768: (ORANGE, 'v')}
fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 6.2), sharex=True, sharey=True)
table = []
for ax, sizes in zip(axes, ((32, 3072), (512, 640, 768))):
    for factor, label in ((48, '48 ns × tasks'), (220, '220 ns × tasks')):
        ax.plot([1, 4], [factor, 4 * factor], color='#888888', linestyle=(0, (3, 3)), linewidth=0.8, zorder=1)
        ax.annotate(label, (4, 4 * factor), xytext=(12, -8 if factor == 220 else 0), textcoords='offset points',
                    fontsize=LABEL, color='#666666', va='center')
    points = {}
    for kib in sizes:
        xs, ys = zip(*sorted(series[kib]))
        color, marker = style[kib]
        ax.plot(xs, ys, color=color, marker=marker, linewidth=1.2, markersize=4.5, label=name[kib], zorder=3)
        for x, y in zip(xs, ys):
            points.setdefault(x, []).append((y, color))
            table.append((kib, x, y))
    for x, values in points.items():  # values within 3 % share one label (gray), others keep their series colour
        groups = []
        for y, color in sorted(values):
            if groups and y <= groups[-1][0][0] * 1.03:
                groups[-1].append((y, color))
            else:
                groups.append([(y, color)])
        previous = None
        for g in groups:
            lo, hi = g[0][0], g[-1][0]
            text = f'{lo:.1f}' if hi - lo < 0.05 else f'{lo:.1f}–{hi:.1f}'
            below = previous is not None and lo <= previous * 1.15  # a close neighbour: put this label below right
            ax.annotate(text, (x, hi), xytext=(5, -10) if below else (-5, 5), textcoords='offset points', fontsize=LABEL,
                        ha='left' if below else 'right', color=g[0][1] if len(g) == 1 else '#444444')
            previous = hi
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlim(0.7, 4.9)
    ax.set_ylim(0, 960)
    ax.set_ylabel('CPU time per load (ns)')
    grid(ax)
    ax.legend(loc='upper left', frameon=False)
axes[1].set_xlabel('Concurrent tasks (one per core, released together)')
axes[0].set_title('(a) arrays that fit in the shared L2 or far exceed it')
axes[1].set_title('(b) arrays whose total reaches or exceeds the 2 MiB L2 as tasks are added')
fig.tight_layout()
save(fig, 'figure-4-1', 'array_kib,concurrent_tasks,ns_per_load', table)

# Figure 4.2: task sets meeting every deadline, 32 KiB low-CLS tasks at 50 % of U
rows = [json.loads(line) for line in (R / 'small-memory-load/results.jsonl').read_text().splitlines()]
loads = sorted({r['load'] for r in rows})
fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 5.6), sharey=True)
table, width = [], 0.2
for ax, (cell, title) in zip(axes, (('cv00-low50', 'Period CV 0'), ('cv20-low50', 'Period CV 0.2'))):
    sets = []
    for i, load in enumerate(loads):
        rs = [r for r in rows if r['heaviness'] == cell and r['load'] == load]
        sets.append(len(rs))
        for j, (key, _, color, hatch) in enumerate(PLACEMENTS):
            assert not any(r[key]['state'] not in ('ok', 'deadline') for r in rs), 'a Partitioned run failed to start'
            met = sum(r[key]['state'] == 'ok' for r in rs)
            bar(ax, i + (j - 1.5) * width, met, width * 0.92, color, hatch)
            table.append((cell, load, key, met, len(rs)))
    ax.set_xticks(range(len(loads)))
    ax.set_xticklabels([f'Per-core load {l:g}\n({n} sets)' for l, n in zip(loads, sets)])
    ax.set_ylim(0, 20)
    ax.set_yticks(range(0, 21, 5))
    ax.set_ylabel('Task sets meeting\nevery deadline')
    ax.set_title(title)
    grid(ax)
fig.legend([swatch(c, h) for _, _, c, h in PLACEMENTS], [l for _, l, _, _ in PLACEMENTS],
           loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
save(fig, 'figure-4-2', 'cell,load,placement,sets_met,sets', table)

# Figure 4.3: planned and effective core U at load 0.5, runs that met every deadline
runs = [r for r in csv.DictReader(CORE_LOAD.open()) if r['load'] == '0.5' and r['met'] == '1']
bars = (('planned_group', 'Planned U, cores with grouped low-CLS tasks', LIGHT_VERMILLION, '/', VERMILLION),
        ('planned_other', 'Planned U, other cores', LIGHT_BLUE, '/', BLUE),
        ('effective_group', 'Effective U, cores with grouped low-CLS tasks', VERMILLION, '', 'black'),
        ('effective_other', 'Effective U, other cores', BLUE, '', 'black'))
placements = (('cgb', 'CGB'), ('ra-cgb', 'RA-CGB'))
fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 5.4), sharey=True)
table, width = [], 0.2
for ax, (cell, title) in zip(axes, (('cv00-low50', 'Period CV 0'), ('cv20-low50', 'Period CV 0.2'))):
    labels = []
    for i, (key, label) in enumerate(placements):
        rs = [r for r in runs if r['cell'] == cell and r['placement'] == key]
        labels.append(f'{label}\n({len(rs)} runs meeting every deadline)')
        for j, (field, _, color, hatch, hatch_color) in enumerate(bars):
            value = median(float(r[field]) for r in rs)
            bar(ax, i + (j - 1.5) * width, value, width * 0.92, color, hatch, text=f'{value:.2f}', hatch_color=hatch_color)
            table.append((cell, key, field, len(rs), f'{value:.4f}'))
    ax.set_xticks(range(len(placements)))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel('Core U (median over runs)')
    ax.set_title(title)
    grid(ax)
fig.legend([swatch(c, h, hc) for _, _, c, h, hc in bars], [l for _, l, _, _, _ in bars],
           loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
save(fig, 'figure-4-3', 'cell,placement,quantity,runs,median_u', table)

# Figure 4.4: L2-hitting against memory-bound tasks, sets meeting every deadline per load
cost = json.loads((R / 'memory-cost-analysis/memory-cost.json').read_text())
kinds = (('l2_met', 'Low-CLS tasks hit the shared L2', BLUE, ''),
         ('mem_met', 'Low-CLS tasks go to memory (matched CLS within 0.005 and target U)', VERMILLION, '/'))
fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.0), sharey=True)
table, width = [], 0.38
for ax, (placement, title) in zip(axes, (('wfd', 'WFD'), ('cgb', 'CGB'))):
    keys = sorted((k for k in cost['by_load'] if k.startswith(placement + ' ')), key=lambda k: float(k.split()[1]))
    for i, k in enumerate(keys):
        entry = cost['by_load'][k]
        for j, (field, _, color, hatch) in enumerate(kinds):
            bar(ax, i + (j - 0.5) * width, entry[field], width * 0.92, color, hatch)
            table.append((placement, k.split()[1], field, entry[field], entry['pairs']))
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([f"{k.split()[1]}\n({cost['by_load'][k]['pairs']} pairs)" for k in keys])
    ax.set_xlabel('Per-core load')
    ax.set_ylim(0, 27)
    ax.set_title(title)
    grid(ax)
axes[0].set_ylabel('Task sets meeting every deadline')
fig.legend([swatch(c, h) for _, _, c, h in kinds], [l for _, l, _, _ in kinds],
           loc='lower center', ncol=1, frameon=False, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
save(fig, 'figure-4-4', 'placement,load,kind,sets_met,pairs', table)

# Figure 4.5: share of task observations with a late job, per task class
classes = (('memory', 'Low-CLS tasks'),
           ('other-with-memory', 'Other tasks on a core\nholding low-CLS tasks'),
           ('other-without-memory', 'Tasks on a core\nwithout low-CLS tasks'))
fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 5.0), sharey=True)
table, width = [], 0.38
for ax, (placement, title) in zip(axes, (('wfd', 'WFD'), ('cgb', 'CGB'))):
    for i, (cls, _) in enumerate(classes):
        for j, (cell, color, hatch) in enumerate((('l2-low25', BLUE, ''), ('mem-low25', VERMILLION, '/'))):
            w = cost['who_late'][f'{cell} {placement}'][cls]
            share = 100 * w['late_tasks'] / w['tasks'] if w['tasks'] else 0.0
            bar(ax, i + (j - 0.5) * width, share, width * 0.92, color, hatch, text=f"{w['late_tasks']}/{w['tasks']}")
            table.append((placement, cell, cls, w['late_tasks'], w['tasks'], f'{share:.2f}'))
    ax.set_xticks(range(len(classes)))
    ax.set_xticklabels([label for _, label in classes])
    ax.set_ylim(0, 12.5)
    ax.set_ylabel('Task observations\nwith a late job (%)')
    ax.set_title(title)
    grid(ax)
fig.legend([swatch(c, h) for _, _, c, h in kinds] + [plt.Line2D([], [], linestyle='none')],
           [l for _, l, _, _ in kinds] + ['Bar labels: observations with a late job / all observations '
                                         '(one per task per run, all loads and sets)'],
           loc='lower center', ncol=1, frameon=False, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
save(fig, 'figure-4-5', 'placement,cell,class,late_observations,observations,share_percent', table)

# Table 4-tet: paired TET gap (release-aware within balanced CLS grouping - release-aware) / release-aware
conditions = (('24', 'small-memory-load/stats-small-memory-load.json', 2, 0.5, '32 KiB 저-CLS task, U의 50%, 코어당 부하 0.5, 주기 CV 0'),
              ('24', 'small-memory-load/stats-small-memory-load.json', 4, 0.5, '32 KiB 저-CLS task, U의 50%, 코어당 부하 0.5, 주기 CV 0.2'),
              ('20', 'task-count/stats-task-count.json', 2, 0.35, '768 KiB task, U의 25%, 코어당 부하 0.35, 조화 주기'),
              ('20', 'task-count/stats-task-count.json', 2, 0.45, '768 KiB task, U의 25%, 코어당 부하 0.45, 조화 주기'))
lines = ['| 실험 | 조건 | 짝지은 set | TET 차이 중앙값 | 95% CI | TET가 늘어난 set | Holm p |', '|---|---|---:|---:|---|---:|---:|']
table = []
for experiment, path, index, load, label in conditions:
    e = next(c for c in json.loads((R / path).read_text())['cells']
             if c['metric'] == 'tet_ns' and c['pair'] == 'p_racgb-p_ra' and c['cv'] == index and c['mean'] == load)
    lo, hi = e['median_ci95']
    lines.append(f"| {experiment}절 | {label} | {e['n']} | {e['median']:+.2%} | {lo:+.2%} … {hi:+.2%} | {e['positive']} | {e['holm_p']:.2g} |")
    table.append((experiment, label, e['n'], f"{e['median']:.6f}", f'{lo:.6f}', f'{hi:.6f}', e['positive'], f"{e['holm_p']:.6g}"))
(OUT / 'table-4-tet.md').write_text('\n'.join(lines) + '\n')
with (OUT / 'table-4-tet.csv').open('w', newline='') as f:
    csv.writer(f).writerows([('experiment', 'condition', 'pairs', 'median_gap', 'ci95_low', 'ci95_high', 'positive', 'holm_p')] + table)
print('wrote table-4-tet')
