"""Thesis chapter 3 assets (section 3.4) from the stored S1 results: figure 3.3 and the table that replaces the kernel figure.

Figure 3.3: per hierarchy level (L1 hit, L2 first hit, memory access), the fraction of accesses of each of the 25
load-only synthetic workloads under cold-start Cachegrind (x) against the static analyses (y): HARA (CSRD) and the
global reuse distance baseline. Every workload is plotted at its exact value; workloads with equal values overlap,
so fewer than 25 markers are visible per model (the thesis caption says so). No in-figure title or note.
Drawn at the final 16 cm text width, so the font sizes are the printed sizes.
Table: per PolyBench-derived kernel, array accesses and L1/L2 misses under Cachegrind, HARA and global reuse distance.
Inputs: artifacts/s1/cachegrind-cold-v1/results.csv and artifacts/s1/polybench-cold-v1/results.csv.
Usage: python3 -m tools.plot_s1_thesis --output artifacts/s1/thesis-ch3
"""

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / 'artifacts/s1/cachegrind-cold-v1/results.csv'
KERNELS = ROOT / 'artifacts/s1/polybench-cold-v1/results.csv'
LEVELS = ('L1 hit', 'L2 first hit', 'Memory access')
# Okabe-Ito colour-blind-safe palette (Wong, Nature Methods 8:441, 2011): blue and vermillion.
MODELS = (('csrd', 'HARA (CSRD)', 'P', '#0072B2'), ('global_rd', 'Global reuse distance', 'o', '#D55E00'))


def fractions(row: dict, prefix: str) -> tuple[float, ...]:
    counts = [int(row[f'{prefix}_{k}']) for k in ('l1', 'll', 'memory')]
    return tuple(c / sum(counts) for c in counts)


def figure(output: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 8, 'axes.titlesize': 8.5,
                         'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5, 'axes.linewidth': 0.8})
    rows = list(csv.DictReader(SYNTHETIC.open()))
    fig, axes = plt.subplots(1, 3, figsize=(16 / 2.54, 2.3), sharex=True, sharey=True)
    for i, (axis, level) in enumerate(zip(axes, LEVELS)):
        axis.plot([0, 1], [0, 1], color='#777777', linestyle=(0, (3, 3)), linewidth=0.8, zorder=1)
        for model, label, marker, color in MODELS:
            points = [(fractions(r, 'cachegrind')[i], fractions(r, model)[i]) for r in rows]
            style = dict(facecolors='none', edgecolors=color, s=30) if marker == 'o' else dict(color=color, s=20)
            axis.scatter(*zip(*points), marker=marker, linewidths=1.0, label=label, zorder=3 if marker == 'o' else 4, **style)
        axis.set(title=level, xlim=(-0.06, 1.06), ylim=(-0.06, 1.06), aspect='equal')
        axis.set_xticks([0, 0.25, 0.5, 0.75, 1])
        axis.set_yticks([0, 0.25, 0.5, 0.75, 1])
        axis.grid(color='#eeeeee', linewidth=0.5, zorder=0)
    axes[0].set_ylabel('Static analysis\n(fraction of accesses)')
    fig.supxlabel('Cachegrind, cold start (fraction of accesses)', fontsize=8)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout()
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(output / f'figure-3-3.{ext}', bbox_inches='tight', dpi=300)
    plt.close(fig)


def table(output: Path) -> None:
    rows = list(csv.DictReader(KERNELS.open()))
    n = lambda v: f'{int(v):,}'
    lines = ['| 커널 | 배열 접근 | L1 미스 (Cachegrind / HARA / Global RD) | L2 미스 (Cachegrind / HARA / Global RD) |',
             '|---|---:|---|---|']
    for r in rows:
        lines.append(f"| {r['kernel']} | {n(r['array_accesses'])} | {n(r['cg_l1_misses'])} / {n(r['csrd_l1_misses'])} / "
                     f"{n(r['global_l1_misses'])} | {n(r['cg_llc_misses'])} / {n(r['csrd_llc_misses'])} / {n(r['global_llc_misses'])} |")
    total = sum(int(r['array_accesses']) for r in rows)
    lines.append(f'| 합계 | {total:,} | | |')
    (output / 'table-3-polybench.md').write_text('\n'.join(lines) + '\n')
    columns = [c for c in rows[0] if c != 'ordered_trace_equal']
    with (output / 'table-3-polybench.csv').open('w', newline='') as f:
        csv.writer(f).writerows([columns] + [[r[c] for c in columns] for r in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    figure(args.output)
    table(args.output)
    print('wrote', args.output)


if __name__ == '__main__':
    main()
