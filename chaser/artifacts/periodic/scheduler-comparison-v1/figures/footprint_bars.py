"""Paper-style bars of measured values for the CLS x footprint run.

Panels are the special-task kinds (small/big footprint x low/high CLS); bars are
the configurations. Bars: median over the task sets of a kind (runs with a
deadline miss or another failure excluded); whiskers: IQR. Files in
<run dir>/figures: footprint-{tet,tat,response,overlap}. The overlap figure shows
the mechanism (other special jobs running during a special job), not a cost.
Usage: python3 footprint_bars.py <run output dir>
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
protocol = json.loads((O / 'protocol.json').read_text())
KINDS = ('SL', 'BL', 'SH', 'BH')
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
          ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (special mixed)', '#1baf7a', '\\\\'),
          ('p_grp', 'Partitioned (special grouped)', '#e0b83a', 'xx'))
METRICS = (('tet_ns', 'TET (ms)', 1e6, True), ('tat_ns', 'TAT (ms)', 1e6, True),
           ('max_response_ratio', 'max response time / period', 1.0, True),
           ('special_overlap', 'other special jobs running alongside', 1.0, False))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def fmt(v):
    return f'{v:.2f}' if v < 10 else f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def title(kind):
    cls = protocol['special_levels'][kind]['cls']
    return f"{kind}: footprint {protocol['footprint_kib'][kind]} KiB, CLS {cls:.2f}"


for metric, label, scale, lower in METRICS:
    fig, axes = plt.subplots(1, len(KINDS), figsize=(15.5, 4.2), dpi=200)
    table, top = [], 0
    for j, kind in enumerate(KINDS):
        ax, members = axes[j], [r for r in rows if r['kind'] == kind]
        for k, (key, _, color, hatch) in enumerate(SERIES):
            v = np.array([r[key][metric] / scale for r in members
                          if r[key].get('state') == 'ok' and r[key].get(metric) is not None])
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(k, m, 0.75, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8,
                        capsize=2, zorder=4)
            ax.annotate(fmt(m), (k, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize=7.5)
            table.append((metric, kind, key, len(v), m, q1, q3))
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(title(kind), loc='left', fontsize=9.5)
        if lower:
            ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    for ax in axes:
        ax.set_ylim(0, top * 1.22)
    axes[0].set_ylabel(f'Measured {label}')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=len(SERIES), frameon=False,
               bbox_to_anchor=(0.5, 1.0), fontsize=9.5)
    # The five-entry legend spans the width, so the title sits above it.
    fig.suptitle('4 special + 12 high-CLS tasks, 5.5 ms jobs, period 200 ms, workload O2',
                 x=0.01, ha='left', y=1.05, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    stem = f"footprint-{metric.replace('_ns', '').replace('max_response_ratio', 'response').replace('special_overlap', 'overlap')}"
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('metric,kind,configuration,n,median,q1,q3\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)
