"""Plot cold Cachegrind and static miss counts for the fixed external kernel probe."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.suite.read_text())
    if (report['status'] != 'ok' or len(report['rows']) != 4 or
            not all(row['sequence']['equal'] for row in report['rows'])):
        parser.error('Require four successful, trace-validated kernels')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams.update({'font.family': 'STIXGeneral', 'mathtext.fontset': 'stix',
                         'font.size': 12, 'axes.linewidth': 1.0,
                         'axes.edgecolor': '#222222', 'legend.frameon': False})
    rows = report['rows']
    x = range(len(rows))
    fig, ax = plt.subplots(figsize=(10.4, 4.5))

    def misses(row, origin, level):
        counts = row[origin]['counts'] if origin == 'cachegrind' else row[origin]
        return sum(counts[1:]) if level == 0 else counts[2]

    offsets = (-0.30, -0.11, 0.11, 0.30)
    for j, (origin, color) in enumerate((('cachegrind', '#dd8452'), ('csrd', '#4c72b0'))):
        for level, hatch in enumerate(('', '///')):
            positions = [i + offsets[level * 2 + j] for i in x]
            values = [misses(row, origin, level) for row in rows]
            ax.bar(positions, values, width=0.19, color=color, hatch=hatch,
                   edgecolor='#202020', linewidth=0.8)
    ax.set_yscale('log')
    ax.set_ylabel('Data-cache misses (count)')
    ax.set_xticks(list(x), [row['id'] for row in rows])
    ax.set_ylim(bottom=90)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.spines[['top', 'right']].set_visible(False)
    legend = [Patch(facecolor='#dd8452', edgecolor='#202020', label='Cachegrind'),
              Patch(facecolor='#4c72b0', edgecolor='#202020', label='YARDA CSRD'),
              Patch(facecolor='white', edgecolor='#202020', label='L1 misses'),
              Patch(facecolor='white', edgecolor='#202020', hatch='///', label='LLC misses')]
    ax.legend(handles=legend, loc='upper center', bbox_to_anchor=(0.5, 1.17), ncol=4)
    differences = [abs(misses(row, 'csrd', level) - misses(row, 'cachegrind', level))
                   for row in rows for level in (0, 1)]
    exact = sum(difference == 0 for difference in differences)
    ax.text(0.05, 0.94,
            f'Miss-count agreement: {exact}/{len(differences)} pairs\n'
            f'Max. absolute error: {max(differences):,} misses', transform=ax.transAxes,
            ha='left', va='top', fontsize=11)
    accesses = sum(row['sequence']['expected_count'] for row in rows)
    fig.text(0.5, 0.015,
             'PolyBench-derived global-array kernels; cold entry, 16 KiB L1 / 2 MiB LLC. '
             f'{accesses:,} ordered accesses trace-checked. Correlation excluded.',
             ha='center', fontsize=9)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.78, bottom=0.17)
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / 'polybench-cachegrind.png', dpi=300)
    fig.savefig(args.output / 'polybench-cachegrind.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
