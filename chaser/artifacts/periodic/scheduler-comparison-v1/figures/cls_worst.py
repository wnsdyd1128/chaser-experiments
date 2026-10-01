"""Worst-case CPU slowdown of co-run jobs relative to isolated execution (CLS run).

Baseline per task: the isolated U measured for its (hot repeats, sweeps) level
during calibration, times the period. Per task set:
  worst task = max over tasks of (mean measured-job CPU / isolated CPU) - 1
  worst job  = max over measured jobs of (job CPU / its task's isolated CPU) - 1
Bars: median over task sets per cell (CV = 0: one set); whiskers: IQR.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path(__file__).resolve().parents[4] / '.cache/cls-distribution-v1'
calibration = json.load(open(O / 'calibration/calibration.json'))
ISOLATED_U = {(int(p), r['hot_repeats'], r['sweeps']): r['u']
              for p, rows in calibration['tables'].items() for r in rows}
PERIODS, MEANS, CVS = (20, 100), (0.3, 0.5, 0.7), (0.0, 0.1, 0.2, 0.3)
SERIES = (('zigzag', 'g', 'Global', '#2a78d6', ''), ('zigzag', 'c', 'Clustered (1+3)', '#eb6834', '//'),
          ('zigzag', 'c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('zigzag', 'p', 'Partitioned (CLS zigzag)', '#1baf7a', '\\\\'),
          ('grouped', 'p', 'Partitioned (CLS grouped)', '#e87ba4', 'oo'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})


def slowdowns(case_dir, placement, arch):
    config = json.loads((case_dir / placement / 'configuration.json').read_text())
    record = json.loads((case_dir / placement / arch / 'measurements.jsonl').read_text().splitlines()[0])
    if record['execution_status'] != 'ok':
        raise ValueError(f'{case_dir}/{placement}/{arch} failed')
    base = [ISOLATED_U[(t['period_ticks'], t['hot_repeats'], t['sweeps'])] * t['period_ticks'] * 1e6
            for t in config['tasks']]
    per_task = {i: [] for i in range(len(base))}
    for job in record['jobs']:
        if job['job'] >= config['warmup_ticks'] // config['tasks'][job['task']]['period_ticks']:
            per_task[job['task']].append((job['cpu_after_ns'] - job['cpu_before_ns']) / base[job['task']])
    worst_task = max(np.mean(v) for v in per_task.values()) - 1
    worst_job = max(max(v) for v in per_task.values()) - 1
    return 100 * worst_task, 100 * worst_job


data = {}
for period in PERIODS:
    for mean in MEANS:
        for cv in CVS:
            cells = sorted(O.glob(f'p{period:03d}/m{round(mean * 100):02d}/cv{round(cv * 100):02d}/s*'))
            for placement, arch, *_ in SERIES:
                data[(period, mean, cv, placement, arch)] = np.array(
                    [slowdowns(c, placement, arch) for c in cells])

table = []
width, x = 0.16, np.arange(len(CVS))
for index, name, stem in ((0, 'Worst task', 'cls-worst-task'), (1, 'Worst job', 'cls-worst-job')):
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.6), dpi=200, sharey=True)
    rows = []
    for i, period in enumerate(PERIODS):
        for j, mean in enumerate(MEANS):
            ax = axes[i, j]
            for k, (placement, arch, label, color, hatch) in enumerate(SERIES):
                values = [data[(period, mean, cv, placement, arch)][:, index] for cv in CVS]
                med = [np.median(v) for v in values]
                q1 = [np.percentile(v, 25) for v in values]
                q3 = [np.percentile(v, 75) for v in values]
                pos = x + (k - 2) * width
                ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                ax.errorbar(pos, med, yerr=[np.subtract(med, q1), np.subtract(q3, med)], fmt='none',
                            ecolor='black', elinewidth=0.7, capsize=1.6, zorder=4)
                for p, m, hi in zip(pos, med, q3):
                    ax.annotate(f'{m:.0f}', (p, hi), xytext=(0, 2), textcoords='offset points',
                                ha='center', va='bottom', rotation=90, fontsize=6.5)
                for cv, v in zip(CVS, values):
                    rows.append((name, period, mean, cv, f'{placement}/{arch}', len(v), float(np.median(v)),
                                 float(np.percentile(v, 25)), float(np.percentile(v, 75)), float(v.max())))
            ax.set_xticks(x, [f'{cv:g}' for cv in CVS], fontsize=9)
            ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
            ax.set_title(f'T = {period} ms, mean CLS = {mean}', loc='left', fontsize=10)
            if j == 0:
                ax.set_ylabel(f'{name} CPU increase\nvs. isolated run (%)')
            if i == 1:
                ax.set_xlabel('CLS coefficient of variation (σ/μ)')
            ax.text(0.02, 0.95, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0, 0].set_ylim(0, max(r[8] for r in rows) * 1.25)
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for *_, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('metric,period_ms,mean_cls,cv,series,n,median_pct,q1_pct,q3_pct,max_pct\n')
        for t in rows:
            f.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in t) + '\n')
    table += rows
for t in table:
    if t[3] == 0.3 and t[2] == 0.7:
        print(t[0], t[1], t[4], f'median {t[6]:.1f}% max {t[9]:.1f}%')
