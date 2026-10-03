"""Paper-style bars of the high-load and partition-infeasible runs: schedulability, response, TAT, TET.

One file per metric and task-size condition (light / heavy, or 4 / 5 / 6 heavy
tasks for the infeasible design); panels are the
per-core load levels, bars the configurations. Schedulability bars are the
share of task sets without a deadline miss (startup failures excluded). The
other bars are medians over the task sets of a cell whose run met every
deadline, with IQR whiskers; the response figure marks the deadline.
Usage: python3 high_load_bars.py <run output dir>
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
DESIGN = protocol.get('design', 'high-load')
LOADS = sorted({r['load'] for r in rows})
ALL_SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'),
              ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'), ('p', 'Partitioned (U-balanced)', '#8c6d31', '--'),
              ('p_inf', 'Partitioned (informed)', '#1baf7a', '\\\\'), ('c_inf', 'Clustered (1+3, informed)', '#e0b83a', 'xx'),
              ('c_cap', 'Clustered (1+3, capacity)', '#e0b83a', 'xx'), ('c2_cap', 'Clustered (1+1+2, capacity)', '#d95f02', '++'))
SERIES = tuple(s for s in ALL_SERIES if s[0] in protocol['runs'])
METRICS = (('schedulable', 'schedulable share', 'Higher is better ↑'),
           ('max_response_ratio', 'max response time / period', 'Lower is better ↓'),
           ('tat_ns', 'TAT (ms)', 'Lower is better ↓'), ('tet_ns', 'TET (ms)', 'Lower is better ↓'))
TITLES = {'light': 'all tasks U <= 0.35', 'heavy': '2 heavy tasks (U 0.5-0.8) + 14 light',
          'h4': '4 heavy tasks (U 0.51-0.55), partition feasible',
          'h5': '5 heavy tasks (U 0.51-0.55), no feasible partition',
          'h6': '6 heavy tasks (U 0.51-0.55), no feasible partition'}
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def fmt(v):
    return f'{v:.2f}' if v < 10 else f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def values(members, key, metric):
    if metric == 'schedulable':
        states = [r[key]['state'] for r in members if r[key]['state'] in ('ok', 'deadline')]
        return np.array([np.mean([s == 'ok' for s in states])]) if states else np.array([])
    scale = 1e6 if metric.endswith('_ns') else 1.0
    return np.array([r[key][metric] / scale for r in members if r[key]['state'] == 'ok'])


for heaviness in protocol['heaviness']:
    for metric, label, direction in METRICS:
        fig, axes = plt.subplots(1, len(LOADS), figsize=(14 if len(LOADS) > 2 else 11, 4.2), dpi=200)
        table, top = [], 0
        for j, load in enumerate(LOADS):
            ax = axes[j]
            members = [r for r in rows if r['heaviness'] == heaviness and r['load'] == load]
            for k, (key, _, color, hatch) in enumerate(SERIES):
                v = values(members, key, metric)
                if not len(v):
                    continue
                q1, m, q3 = np.percentile(v, [25, 50, 75])
                top = max(top, q3)
                ax.bar(k, m, 0.75, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                if metric != 'schedulable':
                    ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8,
                                capsize=2, zorder=4)
                ax.annotate(fmt(m), (k, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                            va='bottom', fontsize=7.5)
                table.append((heaviness, metric, load, key, len(v) if metric != 'schedulable' else len(members),
                              m, q1, q3))
            if not any(t[2] == load for t in table):
                ax.text(0.5, 0.5, 'no task set met every deadline', transform=ax.transAxes, ha='center',
                        va='center', fontsize=9)
            if metric == 'max_response_ratio':
                ax.axhline(1.0, color='black', linestyle='--', linewidth=0.9, zorder=5)
                ax.text(0.98, 1.0, 'deadline', transform=ax.get_yaxis_transform(), ha='right', va='bottom', fontsize=7.5)
            ax.set_xticks([])
            ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
            ax.set_title(f'U per core {load}', loc='left', fontsize=10)
            ax.text(0.02, 0.95, direction, transform=ax.transAxes, fontsize=8, va='top')
        for ax in axes:
            ax.set_ylim(0, 1.15 if metric == 'schedulable' else max(top * 1.22, 1.1 if metric == 'max_response_ratio' else 0))
        axes[0].set_ylabel(f'Measured {label}')
        handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
        fig.legend(handles=handles, loc='upper center', ncol=3 if len(SERIES) <= 6 else 4, frameon=False,
                   bbox_to_anchor=(0.5, 1.0), fontsize=9.5)
        # The legend takes two rows, so the title sits above it.
        fig.suptitle(f'16 compute-bound tasks, periods 20/40/80 ms, {TITLES[heaviness]}', x=0.01, ha='left',
                     y=1.07, fontsize=10.5)
        fig.tight_layout(rect=(0, 0, 1, 0.88))
        stem = f"{DESIGN}-{metric.replace('_ns', '').replace('max_response_ratio', 'response')}-{heaviness}"
        for ext in ('png', 'pdf'):
            fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
        with open(O / f'figures/{stem}.csv', 'w') as f:
            f.write('heaviness,metric,load,configuration,n,median,q1,q3\n')
            for t in table:
                f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
        plt.close(fig)
        print('wrote', stem)
