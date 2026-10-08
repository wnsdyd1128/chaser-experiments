"""Paper-style figures for the exploratory period-spread miss analysis (policy-mix/cv_miss_analysis.py).

Reads <dir>/cv-miss-<run>.json for each given run and writes into <dir>:
  cv-miss-core-load-<run>  two panels (planned core U, effective core U = measured job CPU over the
                           measured window): balanced CLS grouping and release-aware within it, cores
                           holding memory tasks against the other cores, per period cell (medians)
  cv-miss-memory-<run>     two panels per period cell and Partitioned placement: time-average number of
                           cores running memory-task jobs at once, and median worst memory-task inflation
Usage: python3 cv_miss_bars.py <dir> <run>[:<cell>,<cell>...] ...   (cells default to all)
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

D = Path(sys.argv[1]).resolve()
NAMES = {'wfd': ('Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
         'cgb': ('Partitioned (balanced CLS grouping)', '#9e9ac8', 'oo'),
         'ra': ('Partitioned (release-aware)', '#1baf7a', '\\\\'),
         'ra-cgb': ('Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', '++')}
KIND = {'deadline-small-v1': '32 KiB low-CLS tasks hold 50% of U (experiment 27)',
        'deadline-big-v1': '768 KiB tasks hold 25% of U (experiment 27)',
        'small-memory-load-v1': '32 KiB low-CLS tasks (experiment 24)',
        'task-count-v1': '768 KiB tasks, periods 20/40/80 ms (experiment 20)'}
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def cv_label(cell):
    if cell.startswith('mem'):
        return f"768 KiB tasks hold {int(cell[3:])}% of U"
    parts = cell.split('-')
    label = f"Period CV {int(parts[0][2:]) / 100}"
    return label + (f", {int(parts[1][3:])}% of U" if len(parts) > 1 and parts[1].startswith('low') else '')


def save(fig, handles, title, stem, table, header, ncol=2):
    fig.legend(handles=handles, loc='upper center', ncol=ncol, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    for ext in ('png', 'pdf'):
        fig.savefig(D / f'{stem}.{ext}', bbox_inches='tight')
    with open(D / f'{stem}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


def bars(ax, groups, series, value, fmt, ylabel, better):
    width = 0.8 / len(series)
    top = 0
    for i, (key, label, color, hatch) in enumerate(series):
        for g, group in enumerate(groups):
            v = value(group, key)
            if v is None:
                continue
            x = g + (i - (len(series) - 1) / 2) * width
            ax.bar(x, v, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.annotate(fmt.format(v), (x, v), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7)
            top = max(top, v)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([cv_label(g) for g in groups])
    ax.set_ylim(0, top * 1.2)
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.02, 0.97, better, transform=ax.transAxes, fontsize=8, va='top')


for arg in sys.argv[2:]:
    run, _, only = arg.partition(':')
    result = json.loads((D / f'cv-miss-{run}.json').read_text())
    summary = result['summary']
    cells = only.split(',') if only else sorted(summary)
    series = []
    for b in ('cgb', 'ra-cgb'):
        name, color, hatch = NAMES[b]
        series += [((b, 'group'), f'{name}: cores holding memory tasks', color, hatch),
                   ((b, 'other'), f'{name}: other cores', 'white', hatch)]
    fig, axes = plt.subplots(1, 2, figsize=(max(12, 4.5 * len(cells)), 5.0), dpi=200)
    table = []
    for ax, (field, ylabel) in zip(axes, (('planned', 'Planned core U (nominal)'), ('effective', 'Effective core U (measured job CPU / window)'))):
        key = (lambda b, side: f'planned_{side}') if field == 'planned' else (lambda b, side: f'{side}_load')
        value = lambda cell, k: summary[cell][k[0]][key(*k)]
        bars(ax, cells, series, value, '{:.2f}', ylabel, 'Values, not a ranking')
        table += [(field, cell, k[0], k[1], value(cell, k)) for cell in cells for k, *_ in series]
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series]
    save(fig, handles, f'Core loads near the deadline boundary: {KIND[run]}, loads {result["loads"]}',
         f'cv-miss-core-load-{run}', table, 'quantity,cell,placement,cores,median_u')

    series = [(b, *NAMES[b]) for b in ('wfd', 'cgb', 'ra', 'ra-cgb')]
    fig, axes = plt.subplots(1, 2, figsize=(max(12, 4.5 * len(cells)), 5.0), dpi=200)
    table = []
    for ax, (field, ylabel, fmt, better) in zip(axes, (
            ('memory_cores', 'Cores running memory-task jobs at once (time average)', '{:.2f}', 'Lower is better ↓'),
            ('inflation', 'Worst memory-task job CPU / planned budget', '{:.2f}x', 'Lower is better ↓'))):
        value = lambda cell, b: summary[cell][b][field]
        bars(ax, cells, series, value, fmt, ylabel, better)
        table += [(field, cell, b, value(cell, b)) for cell in cells for b, *_ in series]
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series]
    save(fig, handles, f'Memory-task overlap and execution inflation: {KIND[run]}, loads {result["loads"]}',
         f'cv-miss-memory-{run}', table, 'quantity,cell,placement,median')
