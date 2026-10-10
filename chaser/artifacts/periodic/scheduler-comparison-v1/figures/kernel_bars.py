"""Paper-style figures for experiment 45 (real-kernel task sets, policy-mix/confirm_analysis.py and kernel_report.py).

Reads <analysis dir>/confirm.json and report.json, the real-kernels-v1 output and experiment 44's outputs, and writes
into <analysis dir>/figures:
- kernel-outcomes-load: per load, sets accepted and met, accepted but missed, rejected although a configuration met and
  rejected with none meeting, for the frozen RF, the static D + M rule and always using CHASER's placement
- kernel-outcomes-all: the same over all loads
- kernel-auc: AUC for CHASER meeting every deadline, for the RF's probability, D + M and D
- kernel-calibration: per bin of the RF probability, the share of sets where CHASER met every deadline (experiments 44, 45)
- kernel-cls, kernel-pmem: per-task CLS and p_mem of each real kernel and of experiment 44's synthetic task types
Usage: python3 kernel_bars.py <analysis dir> <.cache dir>   (PYTHONPATH: workspace, policy-mix, period-distribution)
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

import confirm_analysis as ca
import kernel_report as kr
import rf_devcheck as rd

D, CACHE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
OUT = D / 'figures'
OUT.mkdir(exist_ok=True)
NAME = 'real-kernels-v1'
result = json.loads((D / 'confirm.json').read_text())
report = json.loads((D / 'report.json').read_text())
records, _ = ca.sets(CACHE, (NAME,))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
METHODS = (('rf', 'Random forest (CHASER pre-run check)'), ('static', 'Static rule D + M < 0.975'),
           ('always', 'Always CHASER placement'))
OUTCOMES = (('success', 'Accepted and met every deadline', '#1b9e77', '//'),
            ('false_accept', 'Accepted but missed (false accept)', '#d95f02', 'xx'),
            ('false_reject', 'Rejected although a configuration met (false reject)', '#7570b3', '..'),
            ('true_reject', 'Rejected, no configuration met (true reject)', '#bbbbbb', '--'))
KERNELS = {'gemm-u32': 'GEMM', 'polybench-atax-u32': 'ATAX', 'polybench-bicg-u32': 'BICG', 'polybench-mvt-u32': 'MVT',
           'polybench-gesummv-u32': 'GESUMMV', 'polybench-jacobi1d-u32': 'Jacobi-1D', 'polybench-jacobi2d-u32': 'Jacobi-2D'}
SYNTHETIC = {'confirm-small-v1': 'Synthetic sets,\n32 KiB type', 'confirm-big-v1': 'Synthetic sets,\n768 KiB type',
             'confirm-mem-v1': 'Synthetic sets,\nmemory-bound type'}
SUBTITLE = 'real-kernel task sets (experiment 45, pre-registered)'


def save(fig, name, header, table):
    for ext in ('png', 'pdf'):
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight')
    with open(OUT / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', name)


def outcome_panel(ax, t, title, table, group):
    for m, (method, _) in enumerate(METHODS):
        bottom = 0
        for key, _, color, hatch in OUTCOMES:
            v = t[method][key]
            ax.bar(m, v, 0.7, bottom=bottom, color=color, edgecolor='black', linewidth=0.6, hatch=hatch, zorder=3)
            if v:
                ax.text(m, bottom + v / 2, f'{v}', ha='center', va='center', fontsize=7.5,
                        bbox=dict(facecolor='white', edgecolor='none', pad=0.6, alpha=0.85))
            bottom += v
            table.append((group, method, key, v))
    ax.set_title(f"{title}\n({t['sets']} sets)", fontsize=9)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels(['Random\nforest', 'Static\nD + M', 'Always\nCHASER'], fontsize=8.5)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)


def outcome_legend(fig, y):
    fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in OUTCOMES],
               loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, y), fontsize=8.5)


loads = sorted(k for k in result['groups'] if k != NAME)
fig, axes = plt.subplots(1, len(loads), figsize=(16, 5.2), dpi=200, sharey=True)
table = []
for ax, key in zip(axes, loads):
    load = float(key.split()[-1])
    outcome_panel(ax, result['groups'][key], f'Per-core load {load:g}', table, load)
axes[0].set_ylabel('Task sets')
outcome_legend(fig, 0.97)
fig.suptitle(f'Pre-run decisions per load: outcome of the accepted or rejected configuration, {SUBTITLE}', x=0.01, ha='left', y=0.995, fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.87))
save(fig, 'kernel-outcomes-load', 'load,method,outcome,sets', table)

fig, ax = plt.subplots(figsize=(6.2, 5.4), dpi=200)
table = []
outcome_panel(ax, result['overall'], 'All loads', table, 'all')
ax.set_ylabel('Task sets')
outcome_legend(fig, 0.93)
fig.suptitle(f'Pre-run decisions, {SUBTITLE}', x=0.01, ha='left', y=0.995, fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.78))
save(fig, 'kernel-outcomes-all', 'group,method,outcome,sets', table)

SCORES = (('p_chaser', 'Random forest probability', '#c51b7d', '++'), ('occupancy', 'Static D + M (L2 and memory)', '#7570b3', '..'),
          ('cache_demand', 'Cache demand D (earlier static rule)', '#8c6d31', '--'))
fig, ax = plt.subplots(figsize=(6.5, 4.6), dpi=200)
rs = [r for r in records if r['p_chaser'] is not None]
y = [int(r['met']['ra-cgb']) for r in rs]
table = []
for i, (key, label, color, hatch) in enumerate(SCORES):
    v = rd.auc(y, [r[key] if key == 'p_chaser' else -r[key] for r in rs])
    ax.bar(i, v, 0.65, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
    ax.annotate(f'{v:.3f}', (i, v), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=8.5)
    table.append((key, f'{v:.4f}'))
ax.axhline(0.5, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
ax.set_xticks(range(len(SCORES)))
ax.set_xticklabels([s[1].replace(' (', '\n(') for s in SCORES], fontsize=8)
ax.set_ylim(0, 1.12)
ax.set_ylabel('AUC, CHASER placement meets every deadline')
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
ax.text(0.01, 0.97, f'{len(rs)} sets; higher is better ↑ (dotted line: chance)', transform=ax.transAxes, fontsize=8, va='top')
fig.suptitle(f'Predicting whether CHASER\'s placement meets every deadline,\n{SUBTITLE}', x=0.01, ha='left', y=0.995, fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.9))
save(fig, 'kernel-auc', 'score,auc', table)

EXPERIMENTS = (('experiment 44', 'Synthetic task sets (experiment 44)', '#7570b3', '..'),
               ('experiment 45', 'Real-kernel task sets (experiment 45)', '#d95f02', '//'))
bins = [(b['low'], b['high']) for b in report['calibration']['experiment 44']]
fig, ax = plt.subplots(figsize=(10, 4.8), dpi=200)
width, table = 0.38, []
for j, (exp, label, color, hatch) in enumerate(EXPERIMENTS):
    for i, b in enumerate(report['calibration'][exp]):
        x = i + (j - 0.5) * width
        if not b['sets']:
            ax.text(x, 0.01, 'no sets', ha='center', va='bottom', fontsize=6.5, rotation=90, color='#555555')
            continue
        v = b['met'] / b['sets']
        ax.bar(x, v, width * 0.92, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.annotate(f"{b['met']}/{b['sets']}", (x, v), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7.5)
        table.append((exp, b['low'], b['high'], b['sets'], b['met'], f'{v:.4f}'))
ax.axvline(1.5, color='#555555', linewidth=0.9, linestyle='--', zorder=2)
ax.text(1.52, 1.07, 'decision threshold 0.8', fontsize=8, va='center')
ax.set_xticks(range(len(bins)))
ax.set_xticklabels([f'{lo:.2f}–{hi:.2f}' for lo, hi in bins], fontsize=8.5)
ax.set_xlabel('Random forest probability that CHASER\'s placement meets every deadline')
ax.set_ylabel('Share of sets where CHASER met every deadline')
ax.set_ylim(0, 1.15)
ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
fig.legend(handles=[Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in EXPERIMENTS],
           loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
fig.suptitle('Observed outcome per probability bin of the frozen random forest (labels: sets met / sets in the bin)',
             x=0.01, ha='left', y=0.995, fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.88))
save(fig, 'kernel-calibration', 'experiment,low,high,sets,met,share', table)

real = kr.real_values(CACHE / NAME)
synthetic = kr.synthetic_values(CACHE, ca.sets(CACHE)[0])
groups = [(KERNELS[k], real[k]) for k in KERNELS] + [(SYNTHETIC[k], synthetic[k]) for k in SYNTHETIC]
for key, label, name in (('cls', 'Cache Locality Score (CLS) per task', 'kernel-cls'),
                         ('p_mem', 'Share of accesses reaching memory (p_mem) per task', 'kernel-pmem')):
    fig, ax = plt.subplots(figsize=(12, 4.8), dpi=200)
    data = [[v[key] for v in values] for _, values in groups]
    box = ax.boxplot(data, widths=0.6, patch_artist=True, showfliers=True,
                     flierprops=dict(marker='.', markersize=2.5, markerfacecolor='#555555', markeredgecolor='none'),
                     medianprops=dict(color='black', linewidth=1.2))
    for i, patch in enumerate(box['boxes']):
        patch.set_facecolor('#fdb863' if i < len(KERNELS) else '#b2abd2')
        patch.set_edgecolor('black')
    ax.set_xticks(range(1, len(groups) + 1))
    ax.set_xticklabels([f'{g}\n({len(v)} tasks)' for g, v in groups], fontsize=7.5)
    ax.set_ylabel(label)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    if key == 'cls':
        ax.axhline(0.5, color='#555555', linewidth=0.8, linestyle=':', zorder=2)
        ax.text(0.5, 0.52, 'grouping threshold CLS 0.5', fontsize=8, va='bottom')
    fig.legend(handles=[Patch(facecolor='#fdb863', edgecolor='black', label='Real kernels (experiment 45)'),
                        Patch(facecolor='#b2abd2', edgecolor='black', label='Synthetic task sets (experiment 44)')],
               loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
    fig.suptitle(f'{label}: real kernels against the synthetic task sets', x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, name, 'group,tasks,median', [(g.replace('\n', ' '), len(v), sorted(x[key] for x in v)[len(v) // 2]) for g, v in groups])
