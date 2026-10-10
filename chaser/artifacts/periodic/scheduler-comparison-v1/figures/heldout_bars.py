"""Paper-style figures for experiment 46 (the frozen pre-run check v1 on held-out kernels, policy-mix/heldout_analysis.py,
kernel_report.py).

Reads <analysis dir>/heldout.json and report.json, experiment 45's report (results/real-kernels-analysis) and the
CHASER (P) runs of real-kernels-v1 and heldout-kernels-v1, and writes into <analysis dir>/figures:
- heldout-outcomes-load: per load, sets accepted and met, accepted but missed, rejected although a configuration met
  and rejected with none meeting, for the frozen RF (v1), the static D + M rule and always using CHASER's placement
- heldout-inflation: per kernel, the worst job CPU time over the planned budget of each task in CHASER's runs at
  per-core loads 0.625 and 0.70 (median and 95th percentile over tasks), experiments 45 and 46
- heldout-rate: per kernel and synthetic task type, the median L1 misses per microsecond the pre-run check used
Usage: python3 heldout_bars.py <analysis dir> <.cache dir> <experiment 45 analysis dir>
       (PYTHONPATH: workspace, policy-mix, period-distribution)
"""
import json
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

import confirm_analysis as ca
import kernel_tasks as kt

D, CACHE, D45 = (Path(a).resolve() for a in sys.argv[1:4])
OUT = D / 'figures'
OUT.mkdir(exist_ok=True)
result = json.loads((D / 'heldout.json').read_text())
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
METHODS = (('rf', 'Random forest\n(CHASER pre-run\ncheck)'), ('static', 'Static rule\nD + M < 0.975'),
           ('always', 'Always CHASER\nplacement'))
OUTCOMES = (('success', 'Accepted and met every deadline', '#1b9e77', '//'),
            ('false_accept', 'Accepted but missed (false accept)', '#d95f02', 'xx'),
            ('false_reject', 'Rejected although a configuration met (false reject)', '#7570b3', '..'),
            ('true_reject', 'Rejected, no configuration met (true reject)', '#bbbbbb', '--'))
NAMES = {'gemm-u32': 'GEMM', 'polybench-atax-u32': 'ATAX', 'polybench-bicg-u32': 'BICG', 'polybench-mvt-u32': 'MVT',
         'polybench-gesummv-u32': 'GESUMMV', 'polybench-jacobi1d-u32': 'Jacobi-1D', 'polybench-jacobi2d-u32': 'Jacobi-2D',
         'polybench-2mm-u32': '2MM', 'polybench-syrk-u32': 'SYRK', 'polybench-trmm-u32': 'TRMM',
         'polybench-doitgen-u32': 'DOITGEN'}


def save(fig, name, header, table):
    fig.savefig(OUT / f'{name}.png', bbox_inches='tight')
    fig.savefig(OUT / f'{name}.pdf', bbox_inches='tight')
    with open(OUT / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', name)


loads = list(result['loads'].items())
fig, axes = plt.subplots(1, len(loads), figsize=(17, 5.4), dpi=200, sharey=True)
table = []
for ax, (load, t) in zip(axes, loads):
    for m, (method, _) in enumerate(METHODS):
        bottom = 0
        for key, _, color, hatch in OUTCOMES:
            v = t[method][key]
            ax.bar(m, v, 0.7, bottom=bottom, color=color, edgecolor='black', linewidth=0.6, hatch=hatch, zorder=3)
            if v:
                ax.text(m, bottom + v / 2, f'{v}', ha='center', va='center', fontsize=7.5,
                        bbox=dict(facecolor='white', edgecolor='none', pad=0.6, alpha=0.85))
            bottom += v
            table.append((load, method, key, v))
    ax.set_title(f"Per-core load {load}\n({t['sets']} sets)", fontsize=9)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels([label for _, label in METHODS], fontsize=7.5)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
axes[0].set_ylabel('Task sets')
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in OUTCOMES],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.97), fontsize=8.5)
fig.suptitle('Pre-run decisions per load on held-out kernels (2MM, SYRK, TRMM, DOITGEN; experiment 46, decided before the runs)',
             x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.86))
save(fig, 'heldout-outcomes-load', 'load,method,outcome,sets', table)


def inflation(name: str) -> dict:
    """Kernel -> worst job CPU / planned budget of every task in CHASER's runs at loads >= 0.625."""
    out = {}
    records, _ = ca.sets(CACHE, (name,))
    for r in records:
        if r['load'] < 0.6:
            continue
        case = CACHE / name / r['label']
        planned = json.loads((case / 'design.json').read_text())['tasks']
        plan = json.loads((case / 'ra-cgb/prepared/p/plan.json').read_text())
        run = json.loads((case / 'ra-cgb/p/measurements.jsonl').read_text().splitlines()[0])
        for i, (t, p) in enumerate(zip(plan['tasks'], planned)):
            cpu = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in run['jobs'] if j['task'] == i and j.get('kind') == 'job']
            out.setdefault(p['kernel'], []).append(max(cpu) / (p['u'] * t['period_ticks'] * 1e6))
    return out


infl = {**inflation('real-kernels-v1'), **inflation('heldout-kernels-v1')}
kernels = list(kt.KERNELS) + list(kt.HELD_OUT)
fig, ax = plt.subplots(figsize=(13, 4.8), dpi=200)
table, width = [], 0.38
for i, k in enumerate(kernels):
    held = k in kt.HELD_OUT
    for j, (stat, value, hatch) in enumerate((('median', np.median(infl[k]), '//'), ('p95', np.percentile(infl[k], 95), '..'))):
        x = i + (j - 0.5) * width
        ax.bar(x, value, width * 0.92, color='#d95f02' if held else '#7570b3', alpha=1.0 if j == 0 else 0.55,
               edgecolor='black', linewidth=0.6, hatch=hatch, zorder=3)
        ax.annotate(f'{value:.2f}', (x, value), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7)
        table.append((k, 'experiment 46' if held else 'experiment 45', stat, f'{value:.4f}', len(infl[k])))
ax.axhline(1.0, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
ax.set_xticks(range(len(kernels)))
ax.set_xticklabels([f"{NAMES[k]}\n({len(infl[k])} tasks)" for k in kernels], fontsize=8)
ax.set_ylabel('Worst job CPU time / planned budget')
ax.set_ylim(0, max(np.percentile(v, 95) for v in infl.values()) * 1.15)
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
ax.text(0.005, 0.97, 'Dotted line: the job takes its planned (isolated) time', transform=ax.transAxes, fontsize=8, va='top')
fig.legend(handles=[Patch(facecolor='#7570b3', edgecolor='black', hatch='//', label='Experiment 45 kernels, median over tasks'),
                    Patch(facecolor='#7570b3', alpha=0.55, edgecolor='black', hatch='..', label='Experiment 45 kernels, 95th percentile'),
                    Patch(facecolor='#d95f02', edgecolor='black', hatch='//', label='Experiment 46 kernels, median over tasks'),
                    Patch(facecolor='#d95f02', alpha=0.55, edgecolor='black', hatch='..', label='Experiment 46 kernels, 95th percentile')],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.99), fontsize=8.5)
fig.suptitle("Job time in CHASER's placement at per-core loads 0.625 and 0.70, relative to the isolated time",
             x=0.01, ha='left', y=1.06, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.86))
save(fig, 'heldout-inflation', 'kernel,experiment,statistic,ratio,tasks', table)

r45, r46 = json.loads((D45 / 'report.json').read_text()), json.loads((D / 'report.json').read_text())
bars = [(NAMES[k], s['rate']['p50'], '#7570b3', '//') for k, s in r45['task_values']['real_by_kernel'].items()] + \
       [(NAMES[k], s['rate']['p50'], '#d95f02', '//') for k, s in r46['task_values']['real_by_kernel'].items()] + \
       [({'confirm-small-v1': '32 KiB\n(synthetic)', 'confirm-big-v1': '768 KiB\n(synthetic)',
          'confirm-mem-v1': 'Memory-bound\n(synthetic)'}[k], s['rate']['p50'], '#1b9e77', '..')
        for k, s in r46['task_values']['synthetic'].items()]
fig, ax = plt.subplots(figsize=(13, 4.6), dpi=200)
table = []
for i, (label, value, color, hatch) in enumerate(bars):
    ax.bar(i, value, 0.7, color=color, edgecolor='black', linewidth=0.6, hatch=hatch, zorder=3)
    ax.annotate(f'{value:.2f}', (i, value), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
    table.append((label.replace('\n', ' '), f'{value:.4f}'))
ax.set_xticks(range(len(bars)))
ax.set_xticklabels([b[0] for b in bars], fontsize=8)
ax.set_ylabel('L1 misses per µs of execution (median task)')
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
fig.legend(handles=[Patch(facecolor='#7570b3', edgecolor='black', hatch='//', label='Experiment 45 kernels'),
                    Patch(facecolor='#d95f02', edgecolor='black', hatch='//', label='Experiment 46 kernels (held out)'),
                    Patch(facecolor='#1b9e77', edgecolor='black', hatch='..', label='Experiment 44 synthetic task types')],
           loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.98), fontsize=8.5)
fig.suptitle('Shared-L2 request rate of the tasks, as the pre-run check saw it (YARDA)', x=0.01, ha='left', y=1.03, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.9))
save(fig, 'heldout-rate', 'source,l1_misses_per_us', table)
