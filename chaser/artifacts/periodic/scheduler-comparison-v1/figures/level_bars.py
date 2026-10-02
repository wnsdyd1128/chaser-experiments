"""Paper-style bars of measured values per level for the load-level and task-U imbalance runs.

Panels are the levels (period, ordered by increasing load, or task-U CV); bars are
the configurations. Bars: median over the task sets of a level (runs with a
deadline miss or another failure excluded); whiskers: IQR. Files in
<run dir>/figures: <design>-{tet,tat,response} and, for u-imbalance, -core-load.
The response figure marks the deadline (max response time / period = 1).
Usage: python3 level_bars.py <run output dir>
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
DESIGN = json.loads((O / 'protocol.json').read_text())['design']
SERIES = {
    'load-level': (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
                   ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (mixed)', '#1baf7a', '\\\\'),
                   ('p_grp', 'Partitioned (grouped)', '#e0b83a', 'xx')),
    'u-imbalance': (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
                    ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p_bal', 'Partitioned (U-balanced)', '#8c6d31', '--'),
                    ('p', 'Partitioned (CLS mixed)', '#1baf7a', '\\\\'), ('p_grp', 'Partitioned (CLS grouped)', '#e0b83a', 'xx'),
                    ('p_grp_bal', 'Partitioned (grouped + U-balanced)', '#d95f02', '++')),
}[DESIGN]
KEY = 'period' if DESIGN == 'load-level' else 'u_cv'
LEVELS = sorted({r[KEY] for r in rows}, reverse=KEY == 'period')
METRICS = [('tet_ns', 'TET (ms)', 1e6), ('tat_ns', 'TAT (ms)', 1e6),
           ('max_response_ratio', 'max response time / period', 1.0)]
if DESIGN == 'u-imbalance':
    METRICS.append(('core_imbalance', 'busiest core CPU / mean core CPU', 1.0))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def fmt(v):
    return f'{v:.2f}' if v < 10 else f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def panel_title(level, members):
    if KEY == 'period':
        return f'Period {level} ms (U per core {2.5 * 4 / level:.3g})'
    realized = np.median([np.std(u := [c / (r['period'] * 1e6) for c in r['isolated_cpu_ns']]) / np.mean(u)
                          for r in members])
    return f'Task-U CV {level} (realized {realized:.2f})'


for metric, label, scale in METRICS:
    fig, axes = plt.subplots(1, len(LEVELS), figsize=(3.6 * len(LEVELS) + 1.5, 4.2), dpi=200)
    table, top = [], 0
    for j, level in enumerate(LEVELS):
        ax, members = axes[j], [r for r in rows if r[KEY] == level]
        for k, (key, _, color, hatch) in enumerate(SERIES):
            v = np.array([r[key][metric] / scale for r in members if r[key].get('state') == 'ok'
                          and r[key].get(metric) is not None])
            if not len(v):
                continue
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(k, m, 0.75, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8,
                        capsize=2, zorder=4)
            ax.annotate(fmt(m), (k, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize=7.5)
            table.append((metric, level, key, len(v), m, q1, q3))
        if metric == 'max_response_ratio':
            ax.axhline(1.0, color='black', linestyle='--', linewidth=0.9, zorder=5)
            ax.text(0.98, 1.0, 'deadline', transform=ax.get_yaxis_transform(), ha='right', va='bottom', fontsize=7.5)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(panel_title(level, members), loc='left', fontsize=9.5)
        ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    for ax in axes:
        ax.set_ylim(0, max(top * 1.22, 1.08 if metric == 'max_response_ratio' else 0))
    axes[0].set_ylabel(f'Measured {label}')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=len(SERIES) if len(SERIES) <= 5 else 4, frameon=False,
               bbox_to_anchor=(0.55, 1.0 if len(SERIES) <= 4 else 1.02), fontsize=10)
    title = ('8 high- + 8 low-CLS tasks, 2.5 ms jobs, workload O2' if DESIGN == 'load-level'
             else '8 high- + 8 low-CLS tasks, total U 1.0, period 40 ms, workload O2')
    # With more than five configurations the legend takes two rows; the title then sits above it.
    fig.suptitle(title, x=0.01, ha='left', y=0.975 if len(SERIES) <= 5 else 1.06, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93 if len(SERIES) <= 4 else 0.88))
    stem = f"{DESIGN}-{metric.replace('_ns', '').replace('max_response_ratio', 'response').replace('core_imbalance', 'core-load')}"
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write(f'metric,{KEY},configuration,n,median,q1,q3\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)
