"""Plot overall data-cache hit rates for frozen S1 PolyBench kernels."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from chaser.s1.polybench import read_cachegrind_counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('stock', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text())
    stock = json.loads(args.stock.read_text())
    if sha256(args.suite.read_bytes()).hexdigest() != stock['yarda_suite_sha256']:
        parser.error('Cachegrind capture refers to a different YARDA suite')
    if len(suite['rows']) != 4 or len(stock['rows']) != 4:
        parser.error('Require four frozen kernels')
    rows = []
    for cold, measured in zip(suite['rows'], stock['rows']):
        if cold['id'] != measured['kernel']:
            parser.error('Kernel order differs')
        path = args.stock.parent / cold['id'] / 'cachegrind.out.gz'
        if sha256(path.read_bytes()).hexdigest() != measured['stock_raw_gzip_sha256']:
            parser.error(f'Stock Cachegrind evidence changed: {cold["id"]}')
        with gzip.open(path, 'rt') as stream:
            raw = stream.read()
        source = next(line[3:] for line in raw.splitlines()
                      if line.startswith('fl=') and line.endswith('/workload.c'))
        actual = read_cachegrind_counts(raw, source, cold['function'], set(), None)
        if (actual['counts'] != measured['cachegrind_counts'] or
                actual['selected_events']['Dr'] + actual['selected_events']['Dw'] !=
                measured['cachegrind_function_accesses'] or
                cold['csrd'] != measured['csrd_counts'] or
                cold['sequence']['expected_count'] != measured['csrd_array_accesses']):
            parser.error(f'Count evidence differs: {cold["id"]}')
        rows.append(measured)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.family': 'STIXGeneral', 'mathtext.fontset': 'stix',
                         'font.size': 12, 'axes.linewidth': 1.0,
                         'axes.edgecolor': '#222222', 'legend.frameon': False})
    series = (('cachegrind_counts', 'Cachegrind', '#dd8452',
               'cachegrind_function_accesses', -0.17),
              ('csrd_counts', 'YARDA CSRD', '#4c72b0',
               'csrd_array_accesses', 0.17))
    fig, ax = plt.subplots(figsize=(10.4, 4.5))
    for key, label, color, accesses, offset in series:
        values = [100 * (1 - row[key][2] / row[accesses]) for row in rows]
        positions = [index + offset for index in range(len(rows))]
        ax.bar(positions, values, width=0.34,
               color=color, edgecolor='#202020', linewidth=0.8,
               label=label)
        for position, value in zip(positions, values):
            ax.text(position, value + 0.8, f'{value:.3f}', ha='center',
                    va='bottom', fontsize=9.5)
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.set_xticks(range(len(rows)), [row['kernel'] for row in rows])
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_ylabel('Overall data-cache hit rate (%)')
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.17), ncol=2)
    fig.text(0.5, 0.02,
             'Hit = 1 − LLC misses / data accesses. Cachegrind includes prior '
             'initialization and full kernel function; YARDA counts global arrays '
             'from a cold cache. Y-axis starts at 0%.',
             ha='center', fontsize=9)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.78, bottom=0.17)
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / 'polybench-hit-rates.png', dpi=300)
    fig.savefig(args.output / 'polybench-hit-rates.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
