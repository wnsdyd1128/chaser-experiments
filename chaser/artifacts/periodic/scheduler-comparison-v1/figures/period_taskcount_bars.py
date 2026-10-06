"""Paper-style bars for the 12-20 task rerun of experiments 1 and 2: measured TAT / TET.

Files in <main>/figures: period-taskcount-{tat,tet}-m<mean>-cv{10,20,30}; panels = task-count
group (12-14, 15-17, 18-20); bars = G, C (1+3), C2 (1+1+2) and P on the period snake, then
P, C (1+3), C2 (1+1+2) on the cohort-aware placement (control run); median over the sets,
whiskers IQR. One mean (default 100 ms): every mean scales the periods alike.
Usage: python3 period_taskcount_bars.py --main <main output> --control <control output> [--mean 100]
"""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--main', type=Path, required=True)
parser.add_argument('--control', type=Path, required=True)
parser.add_argument('--mean', type=int, default=100)
args = parser.parse_args()
M, C = args.main.resolve(), args.control.resolve()
counts = json.loads((M / 'protocol.json').read_text())['task_counts']
rows = [json.loads(l) for l in open(C / 'results.jsonl') if json.loads(l)['mean'] == args.mean]
# Control rows carry the main run's G and snake P/C/C2 as g, ps, cs, c2s.
SERIES = (('g', 'Global', '#2a78d6', ''), ('cs', 'Clustered (1+3), period zigzag', '#7f7fbf', 'xx'),
          ('c2s', 'Clustered (1+1+2), period zigzag', '#4a3aa7', '..'),
          ('ps', 'Partitioned, period zigzag', '#8c6d31', '--'),
          ('c', 'Clustered (1+3), release-aware', '#9ecae1', '//'),
          ('c2', 'Clustered (1+1+2), release-aware', '#c51b7d', 'oo'),
          ('p', 'Partitioned, release-aware', '#1baf7a', '\\\\'))
GROUPS = (('12-14 tasks', range(12, 15)), ('15-17 tasks', range(15, 18)), ('18-20 tasks', range(18, 21)))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(M / 'figures').mkdir(exist_ok=True)
ok = lambda r, k: r[k]['status'] == 'ok'

for metric, label in (('tat_ns', 'TAT'), ('tet_ns', 'TET')):
    for cv in sorted({r['cv'] for r in rows}):
        fig, axes = plt.subplots(1, len(GROUPS), figsize=(4.8 * len(GROUPS) + 1, 5.0), dpi=200)
        table = []
        for ax, (group, values) in zip(axes, GROUPS):
            members = [r for r in rows if r['cv'] == cv and counts[r['set_id']] in values]
            top, bottom = 0, float('inf')
            for k, (key, _, color, hatch) in enumerate(SERIES):
                v = np.array([r[key][metric] / 1e6 for r in members if ok(r, key)])
                failed = sum(not ok(r, key) for r in members)
                if not len(v):
                    continue
                q1, m, q3 = np.percentile(v, [25, 50, 75])
                top, bottom = max(top, q3), min(bottom, q1)
                ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2,
                            zorder=4)
                ax.annotate(f'{m:.0f}' + (f'\n{failed} excl.' if failed else ''), (k, q3), xytext=(0, 2),
                            textcoords='offset points', ha='center', va='bottom', fontsize=7)
                table.append((group, key, len(v), m, q1, q3, failed))
            ax.set_ylim(0, top * 1.22)
            ax.set_xticks([])
            ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
            ax.set_title(f'{group} ({len(members)} sets)', loc='left', fontsize=9.5)
            ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
        axes[0].set_ylabel(f'Measured {label} (ms)')
        handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
        fig.legend(handles=handles, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.55, 0.96),
                   fontsize=8.5)
        fig.suptitle(f'{label}: mean period {args.mean} ms, period CV {cv}, equal task U (per-core 0.5), '
                     'workload O0', x=0.01, ha='left', y=0.995, fontsize=10.5)
        fig.tight_layout(rect=(0, 0, 1, 0.84))
        stem = f'period-taskcount-{label.lower()}-m{args.mean:03d}-cv{round(cv * 100):02d}'
        for ext in ('png', 'pdf'):
            fig.savefig(M / f'figures/{stem}.{ext}', bbox_inches='tight')
        with open(M / f'figures/{stem}.csv', 'w') as f:
            f.write('group,configuration,n,median_ms,q1_ms,q3_ms,excluded\n')
            for t in table:
                f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
        plt.close(fig)
        print('wrote', stem)
