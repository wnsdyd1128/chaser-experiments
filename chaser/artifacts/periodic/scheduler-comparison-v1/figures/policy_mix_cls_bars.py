"""Paper-style bars of measured TAT and TET: CLS-keyed against traffic-keyed placements.

Cases: the policy-mix sets whose low-CLS 32 KiB tasks have matched traffic (the only ones
where the CLS key and the traffic key give different assignments), paired case by case
across the two runs. Panels = per-core load; bars = six Partitioned placements; median over
the cases where all six met every deadline, whiskers IQR.
Files in <CLS run dir>/figures: policy-mix-cls-tat, policy-mix-cls-tet.
Usage: python3 policy_mix_cls_bars.py <policy-mix-cls run dir> <policy-mix run dir>
"""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O, MIX = (Path(a).resolve() for a in sys.argv[1:3])
factors = json.loads((MIX / 'protocol.json').read_text())['set_factors']
base = {(r['load'], r['set_id']): r for r in map(json.loads, open(MIX / 'results.jsonl'))}
rows = []
for r in map(json.loads, open(O / 'results.jsonl')):
    f = factors[r['set_id']]
    if f['low'] > 0 and f['traffic'] == 'matched':
        rows.append(dict(base[(r['load'], r['set_id'])], p_cg=r['p_cg'], p_racg=r['p_racg']))
SERIES = (('p', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
          ('p_ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
          ('p_tg', 'Partitioned (traffic-grouped + U-balanced)', '#e0b83a', 'xx'),
          ('p_cg', 'Partitioned (CLS-grouped + U-balanced)', '#9e9ac8', 'oo'),
          ('p_ratg', 'Partitioned (release-aware within traffic grouping)', '#d95f02', '++'),
          ('p_racg', 'Partitioned (release-aware within CLS grouping)', '#c51b7d', '..'))
LOADS = sorted({r['load'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


for metric, label in (('tat_ns', 'TAT'), ('tet_ns', 'TET')):
    fig, axes = plt.subplots(1, len(LOADS), figsize=(5.4 * len(LOADS) + 1, 5.2), dpi=200)
    table = []
    for ax, load in zip(axes, LOADS):
        members = [r for r in rows if r['load'] == load and all(r[k].get('state') == 'ok' for k, *_ in SERIES)]
        top = 0
        for k, (key, _, color, hatch) in enumerate(SERIES):
            v = np.array([r[key][metric] / 1e6 for r in members])
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2,
                        zorder=4)
            ax.annotate(fmt(m), (k, q3), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=7.5)
            table.append((load, key, len(v), m, q1, q3))
        ax.set_ylim(0, top * 1.3)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(f'Per-core U {load} ({len(members)} cases)', loc='left', fontsize=9.5)
        ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0].set_ylabel(f'Measured {label} (ms)')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.55, 0.96), fontsize=9)
    fig.suptitle(f'{label} with low-CLS 32 KiB tasks at matched traffic (CLS and traffic keys differ), workload O2',
                 x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    stem = f'policy-mix-cls-{label.lower()}'
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('load,placement,n,median_ms,q1_ms,q3_ms\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)
