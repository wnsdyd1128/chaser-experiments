"""Paper-style bars of measured TET and TAT (ms) for the cache-affinity run.

One file per metric and sweeps-per-job level; panels are the per-core working set
as a share of L1.
Bars: median over the task sets of a cell (failed runs excluded); whiskers: IQR.
Usage: python3 cache_affinity_bars.py <run output dir>
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
optimization = json.load(open(O / 'protocol.json')).get('workload_optimization', 'O0')
LEVELS, SWEEPS = (25, 50, 100, 150), (2, 8, 32)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned', '#1baf7a', '\\\\'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def fmt(v):
    return f'{v:.2f}' if v < 10 else f'{v:.1f}'


for metric, name in (('tet_ns', 'TET'), ('tat_ns', 'TAT')):
    for sweeps in SWEEPS:
        fig, axes = plt.subplots(1, len(LEVELS), figsize=(15, 4.2), dpi=200)
        table = []
        for j, level in enumerate(LEVELS):
            ax = axes[j]
            members = [r for r in rows if r['mean'] == level and r['cv'] == sweeps]
            top = 0
            for k, (arch, label, color, hatch) in enumerate(SERIES):
                v = np.array([r[arch][metric] for r in members if r[arch]['status'] == 'ok']) / 1e6
                q1, m, q3 = np.percentile(v, [25, 50, 75])
                top = max(top, q3)
                ax.bar(k, m, 0.7, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black',
                            elinewidth=0.8, capsize=2.5, zorder=4)
                ax.annotate(fmt(m), (k, q3), xytext=(0, 2), textcoords='offset points',
                            ha='center', va='bottom', fontsize=8.5)
                table.append((name, level, sweeps, arch, len(v), m, q1, q3))
            ax.set_ylim(0, top * 1.22)
            ax.set_xticks([])
            ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
            ax.set_title(f'WS {level}% of L1 (T = {members[0]["period_ticks"]} ms)', loc='left', fontsize=10)
            if j == 0:
                ax.set_ylabel(f'Measured {name} (ms)')
            ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
        handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
        fig.legend(handles=handles, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
        fig.suptitle(f'{sweeps} sweeps per job, workload {optimization}', x=0.01, ha='left', y=0.975, fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        stem = f'cache-affinity-{name.lower()}-s{sweeps:02d}-{optimization.lower()}'
        (O / 'figures').mkdir(exist_ok=True)
        for ext in ('png', 'pdf'):
            fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
        with open(O / f'figures/{stem}.csv', 'w') as f:
            f.write('metric,ws_level_pct,sweeps,architecture,n,median_ms,q1_ms,q3_ms\n')
            for t in table:
                f.write(','.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in t) + '\n')
        plt.close(fig)
        print('wrote', stem)
