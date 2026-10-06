"""Paper-style figures for experiment 28: CAAS Algorithm 1 against the CLS steps on experiment 27's sets.

Reads experiment 27's and 28's outputs through policy-mix/ladder_analysis.load_type. Files in <dest>:
  ladder-met-<type>-<cell>       lines over per-core U: task sets placed and meeting every deadline
                                 (a set Algorithm 1 cannot place counts as not meeting)
  ladder-placeable-<type>        lines over per-core U: task sets each Algorithm 1 variant can place
  ladder-violated-<type>-<cell>  lines over per-core U: violated jobs / released jobs over the placed runs
  ladder-inflation-<type>, ladder-tet-<type>  bars per period cell: median over the cases where CAAS,
                                 CLS + Algorithm 1 and both CLS groupings met every deadline, whiskers IQR;
                                 skipped when fewer than MIN_COMMON such cases
Usage: python3 ladder_bars.py --small <27> --small-caas <28> --big <27> --big-caas <28> --dest <dir>
"""
import argparse
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'policy-mix'))
import ladder_analysis as la

SERIES = (('caas', 'CAAS (CA-CSRD + Algorithm 1)', '#d95f02', 'o', '-', '//'),
          ('cls-a1', 'CLS + Algorithm 1 (threshold 0.5)', '#e6ab02', 's', '-', '..'),
          ('cls-a1-cal', 'CLS + Algorithm 1 (calibrated threshold 0.887)', '#a6761d', 'D', ':', 'xx'),
          ('cgb', 'Partitioned (balanced CLS grouping)', '#9e9ac8', 'v', '--', 'oo'),
          ('ra-cgb', 'Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', 'P', '-', '++'),
          ('wfd', 'Partitioned (U-balanced, WFD)', '#8c6d31', '^', '--', '--'))
ALGORITHM1 = [s for s in SERIES if s[0] in la.ALGORITHM1]
BARS = [s for s in SERIES if s[0] in ('caas', 'cls-a1', 'cgb', 'ra-cgb')]
KIND = {'small': '32 KiB low-CLS tasks hold 50% of U', 'big': '768 KiB tasks hold 25% of U'}
MIN_COMMON = 10  # fewer common cases than this make the bars a few anecdotes
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def save(fig, handles, title, stem, table, header, dest, ncol=2):
    fig.legend(handles=handles, loc='upper center', ncol=ncol, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    for ext in ('png', 'pdf'):
        fig.savefig(dest / f'{stem}.{ext}', bbox_inches='tight')
    with open(dest / f'{stem}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


def lines(dest, stem, title, ylabel, series, loads, value, header, better, ylim=None):
    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=200)
    table = []
    for key, name, color, marker, ls, _ in series:
        ys = [value(load, key) for load in loads]
        table += [(load, name, y) for load, y in zip(loads, ys)]
        ax.plot(loads, [np.nan if y is None else y for y in ys], color=color, marker=marker, linestyle=ls,
                linewidth=1.4, markersize=5, zorder=3)
    ax.set_xticks(loads)
    ax.set_xlabel('Per-core nominal U')
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.98 if better == 'Higher is better ↑' else 0.02, 0.97, better, transform=ax.transAxes, fontsize=8,
            va='top', ha='right' if better == 'Higher is better ↑' else 'left')
    handles = [Line2D([], [], color=c, marker=m, linestyle=ls, label=n) for _, n, c, m, ls, _ in series]
    save(fig, handles, title, stem, table, header, dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ('--small', '--small-caas', '--big', '--big-caas', '--dest'):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    for t, base, caas in (('small', args.small, args.small_caas), ('big', args.big, args.big_caas)):
        cases, _ = la.load_type(base.resolve(), caas.resolve())
        cells = sorted({c['heaviness'] for c in cases})
        loads = sorted({c['load'] for c in cases})
        at = lambda cell, load: [c for c in cases if c['heaviness'] == cell and c['load'] == load]
        state = lambda r: r['state'] if r else None

        def placeable(load, key):
            return sum(state(c['runs'][key]) in ('ok', 'deadline') for c in cases if c['load'] == load)

        lines(args.dest, f'ladder-placeable-{t}', f'Task sets Algorithm 1 can place: {KIND[t]}, both period cells',
              'Task sets placed (of 36)', ALGORITHM1, loads, placeable, 'load,placement,placed_sets',
              'Higher is better ↑', (-1, 38))
        for cell in cells:
            cv = int(cell.split('-')[0][2:]) / 100
            met = lambda load, key: sum(state(c['runs'][key]) == 'ok' for c in at(cell, load))

            def violated(load, key):
                runs = [c['runs'][key] for c in at(cell, load) if state(c['runs'][key]) in ('ok', 'deadline')]
                return 100 * sum(r['missed_jobs'] for r in runs) / sum(r['expected_jobs'] for r in runs) if runs else None

            lines(args.dest, f'ladder-met-{t}-{cell}', f'Task sets placed and meeting every deadline: {KIND[t]}, period CV {cv}',
                  'Task sets meeting every deadline (of 18)', SERIES, loads, met, 'load,placement,sets',
                  'Higher is better ↑', (-0.5, 19.5))
            lines(args.dest, f'ladder-violated-{t}-{cell}', f'Deadline-violating jobs of placed runs: {KIND[t]}, period CV {cv}',
                  'Deadline-violating jobs / released jobs (%)', SERIES, loads, violated, 'load,placement,violated_percent',
                  'Lower is better ↓')
        common = sum(all(state(c['runs'][k]) == 'ok' for k, *_ in BARS) for c in cases)
        if common < MIN_COMMON:
            print(f'{t}: {common} cases where all four met every deadline; inflation and TET bars skipped')
            continue
        for metric, field, scale, ylabel, fmt in (('inflation', 'worst_memory_inflation', 1.0,
                                                   'Worst memory-task job CPU / planned budget', '{:.2f}x'),
                                                  ('tet', 'tet_ns', 1e-6, 'Total execution time, TET (ms)', '{:.0f} ms')):
            fig, axes = plt.subplots(1, len(cells), figsize=(5.2 * len(cells) + 1, 5.0), dpi=200)
            table = []
            for ax, cell in zip(axes, cells):
                members = [c for c in cases if c['heaviness'] == cell
                           and all(state(c['runs'][k]) == 'ok' for k, *_ in BARS)]
                top = 0
                for i, (key, _, color, _, _, hatch) in enumerate(BARS):
                    v = np.array([c['runs'][key][field] * scale for c in members])
                    if not len(v):
                        continue
                    q1, m, q3 = np.percentile(v, [25, 50, 75])
                    top = max(top, q3)
                    ax.bar(i, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                    ax.errorbar(i, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2,
                                zorder=4)
                    ax.annotate(fmt.format(m), (i, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                                va='bottom', fontsize=7.5)
                    table.append((cell, key, len(v), m, q1, q3))
                ax.set_ylim(0, top * 1.2 if top else 1)
                ax.set_xticks([])
                ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
                cv = int(cell.split('-')[0][2:]) / 100
                ax.set_title(f'Period CV {cv} ({len(members)} cases, all four met deadlines)', loc='left', fontsize=9)
                ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
            axes[0].set_ylabel(ylabel)
            handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=n) for _, n, c, _, _, h in BARS]
            what = 'Worst execution inflation of memory-bound tasks' if metric == 'inflation' else 'Total execution time'
            save(fig, handles, f'{what}: {KIND[t]}, all loads pooled', f'ladder-{metric}-{t}', table,
                 'cell,placement,cases,median,q1,q3', args.dest)


if __name__ == '__main__':
    main()
