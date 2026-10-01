"""Paper-style bars of measured time per array-load iteration, O0 vs O2 workload.

Per task: (mean measured-job CPU - empty-job CPU of the same architecture and
period) / (distinct lines x sweeps). A set's value is the median over its 16
tasks; bars are the median over the task sets of a cell, whiskers the IQR.
Isolated is set 0 with each task run alone under Partitioned (median over tasks,
no whisker). The empty-job subtraction assumes additive scheduling overhead.
One file per sweeps-per-job level; panels are the per-core working set as a
share of L1.
Usage: python3 cache_affinity_per_load.py <O0 run dir> <O2 run dir> <output dir>
"""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

RUNS = (('O0', Path(sys.argv[1]).resolve()), ('O2', Path(sys.argv[2]).resolve()))
OUT = Path(sys.argv[3]).resolve()
LEVELS, SWEEPS = (25, 50, 100, 150), (2, 8, 32)
SERIES = (('iso', 'Isolated', '#b0b0b0', 'xx'), ('g', 'Global', '#2a78d6', ''),
          ('c', 'Clustered (1+3)', '#eb6834', '//'), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('p', 'Partitioned', '#1baf7a', '\\\\'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def load(run):
    rows = [json.loads(l) for l in open(run / 'results.jsonl')]
    configs = {(r['mean'], r['cv'], r['set_id']): json.loads(
        (run / f"ws{r['mean']:03d}/s{r['cv']:02d}/set{r['set_id']:02d}/configuration.json").read_text())
        for r in rows}
    return rows, configs, json.load(open(run / 'isolated.json')), json.load(open(run / 'empty.json'))


def per_load(task_cpu, tasks, sweeps, overhead):
    return np.median([(cpu - overhead) / (t['distinct'] * sweeps) for cpu, t in zip(task_cpu, tasks)])


def cell(data, level, sweeps):
    """Return {series: (median, q1, q3, n)} in ns per load iteration."""
    rows, configs, isolated, empty = data
    first = configs[(level, sweeps, 0)]
    overhead = empty[f"p{first['tasks'][0]['period_ticks']:02d}"]
    values = {'iso': [per_load(isolated[f'ws{level:03d}/s{sweeps:02d}/set00']['task_cpu_ns'],
                               first['tasks'], sweeps, overhead['p']['tet_ns'] / 160)]}
    for arch in ('g', 'c', 'c2', 'p'):
        values[arch] = [per_load(r[arch]['task_cpu_ns'], configs[(level, sweeps, r['set_id'])]['tasks'],
                                 sweeps, overhead[arch]['tet_ns'] / 160)
                        for r in rows if r['mean'] == level and r['cv'] == sweeps and r[arch]['status'] == 'ok']
    return {k: (*np.percentile(v, [50, 25, 75]), len(v)) for k, v in values.items()}


def fmt(v):
    return f'{v:.0f}' if v >= 100 else f'{v:.1f}'


data = {name: load(run) for name, run in RUNS}
OUT.mkdir(parents=True, exist_ok=True)
width = 0.8
for sweeps in SWEEPS:
    fig, axes = plt.subplots(1, len(LEVELS), figsize=(15, 4.2), dpi=200)
    table = []
    for j, level in enumerate(LEVELS):
        ax = axes[j]
        top = 0
        for g, (name, _) in enumerate(RUNS):
            stats = cell(data[name], level, sweeps)
            for k, (key, label, color, hatch) in enumerate(SERIES):
                m, q1, q3, n = stats[key]
                x = g * (len(SERIES) + 1) + k
                top = max(top, q3)
                ax.bar(x, m, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                if key != 'iso':
                    ax.errorbar(x, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black',
                                elinewidth=0.8, capsize=2, zorder=4)
                ax.annotate(fmt(m), (x, q3), xytext=(0, 2), textcoords='offset points',
                            ha='center', va='bottom', fontsize=6.5)
                table.append((level, sweeps, name, key, n, m, q1, q3))
        ax.set_ylim(0, top * 1.22)
        ax.set_xticks([2, 2 + len(SERIES) + 1], [f'workload {name}' for name, _ in RUNS])
        ax.tick_params(axis='x', length=0)
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        period = data['O0'][1][(level, sweeps, 0)]['tasks'][0]['period_ticks']
        ax.set_title(f'WS {level}% of L1 (T = {period} ms)', loc='left', fontsize=10)
        if j == 0:
            ax.set_ylabel('Time per load iteration (ns)')
        ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
    fig.suptitle(f'{sweeps} sweeps per job', x=0.01, ha='left', y=0.975, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    stem = f'cache-affinity-per-load-s{sweeps:02d}-o0-vs-o2'
    for ext in ('png', 'pdf'):
        fig.savefig(OUT / f'{stem}.{ext}', bbox_inches='tight')
    with open(OUT / f'{stem}.csv', 'w') as f:
        f.write('ws_level_pct,sweeps,workload,series,n,median_ns,q1_ns,q3_ns\n')
        for t in table:
            f.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)
