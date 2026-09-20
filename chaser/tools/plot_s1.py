"""Plot S1 prediction/reference ratios using the environment's Matplotlib installation."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='S1 model, execution trace, or Cachegrind suite.json')
    parser.add_argument('--output', type=Path, required=True, help='New plot directory')
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        'font.family': 'STIXGeneral',
        'mathtext.fontset': 'stix',
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.1,
        'axes.edgecolor': '#1a1a1a',
        'text.color': '#1a1a1a',
        'axes.labelcolor': '#1a1a1a',
        'xtick.color': '#1a1a1a',
        'ytick.color': '#1a1a1a',
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'legend.frameon': False,
    })

    report = json.loads(args.report.read_text())
    rows = [r for r in report['rows'] if r['status'] in ('ok', 'mismatch')]
    if not rows:
        parser.error('No evaluated workloads to plot')
    cachegrind = report.get('execution_validation') == 'cachegrind-source-line-attribution'
    execution = report.get('execution_validation') == 'valgrind-lackey-ordered-accesses'
    if execution:
        rows = [{**r, 'reference': r['trace_reference_ratios'],
                 'global_rd': r['global_rd']['ratios'], 'csrd': r['csrd']['ratios']} for r in rows]
    xlabel = 'Trace-replay fraction of accesses' if execution else 'Reference fraction of accesses'
    if cachegrind:
        xlabel = 'Cachegrind fraction of accesses'
    args.output.mkdir(parents=True)
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.1), sharex=True, sharey=True)
    for i, (axis, level) in enumerate(zip(axes, ('L1 hit', 'LLC first hit', 'All-cache miss (Memory)'))):
        axis.plot([0, 1], [0, 1], color='#777777', linestyle=(0, (3, 3)), linewidth=1,
                  zorder=1)
        for model, label, marker, color in (('global_rd', 'Global RD', 'o', '#c44e52'),
                                            ('csrd', 'CSRD', '+', '#8172b3')):
            style = {'facecolors': 'none', 'edgecolors': color} if model == 'global_rd' else {'color': color}
            axis.scatter([r['reference'][i] for r in rows], [r[model][i] for r in rows],
                         label=label, marker=marker, s=58, linewidths=1.6, zorder=3, **style)
        axis.set(title=level, xlabel=xlabel, xlim=(-0.04, 1.04),
                 ylim=(-0.04, 1.04), aspect='equal')
        axis.set_xticks([0, 0.25, 0.5, 0.75, 1])
        axis.set_yticks([0, 0.25, 0.5, 0.75, 1])
    axes[0].set_ylabel('Predicted fraction of accesses')
    fig.legend(*axes[-1].get_legend_handles_labels(), loc='upper center',
               bbox_to_anchor=(0.5, 0.93), ncol=2, fontsize=12)
    title = 'S1 Cachegrind vs. static prediction' if cachegrind else 'S1 cold demand-cache model'
    fig.suptitle(f'{title}: {len(rows)} load-only workloads', fontsize=14)
    note = ('Host Lackey trace; function/array filtered, cold LRU replay. Target validation: not performed.'
            if execution else 'All fractions use total accesses. Overlapping points are retained. '
            'Execution validation: not performed.')
    if cachegrind:
        state = 'post-initialization state'
        note = f'Cachegrind: {state}, full traffic. Static prediction: cold, array only.'
    fig.text(0.5, 0.035, note, ha='center', fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.18, top=0.76, wspace=0.25)
    fig.savefig(args.output / 'prediction-reference.png', dpi=300)
    fig.savefig(args.output / 'prediction-reference.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
