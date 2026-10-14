"""Thesis chapter 6 figures 6.1-6.12 (measured values, abbreviated placement names, no in-figure title).

Drawn at the final 16 cm text width like figures/thesis_ch4.py, from the saved result bundles and
thesis-ch6/kernel-inflation-tasks.csv (thesis_ch6_inflation.py). Placements: WFD (U-balanced), RA (release-aware),
CGB (CLS grouping with balancing), RA-CGB (release-aware CGB, CHASER's placement).
figure-6-1   experiment 27 (results/deadline-{small,big}): worst low-CLS-task job CPU / planned budget, median and
             interquartile range over the cases where all four deterministic Partitioned placements met every deadline
figure-6-2   the same cases: TET (ms)
figure-6-3   experiment 27, 32 KiB type: task sets meeting every deadline per load, period CV 0 and 0.2
figure-6-4   the same for the 768 KiB type
figure-6-5   the same cases as figure 6.1: TAT (ms)
figure-6-6   experiment 28 (results/deadline-ladder/ladder.json): task sets each Algorithm 1 variant can place per load
             (both period CV cells, 36 sets per load); CGB and RA-CGB place every set
figure-6-7   experiment 44 (results/confirm-*): AUC for CHASER's placement meeting every deadline, RF probability,
             D + M and D (per-type values are descriptive)
figure-6-8   experiment 44 (results/confirm-analysis/confirm.json): outcome of the accept or reject decision, RF, the
             D + M < 0.975 rule and always running CHASER's placement
figure-6-9   experiment 45 (results/real-kernels-analysis/confirm.json): the same per load
figure-6-10  experiments 44 and 45 (results/real-kernels-analysis/report.json, post hoc): share of sets where CHASER's
             placement met every deadline per bin of the RF probability
figure-6-11  experiments 44-46 (results/heldout-kernels-analysis/report.json): per-task L1 misses per microsecond of
             isolated execution as the pre-run check saw it (YARDA), 5th/25th/50th/75th/95th percentiles
figure-6-12  experiments 45 and 46, loads 0.625 and 0.70 (thesis-ch6/kernel-inflation-tasks.csv, post hoc): per task,
             worst job CPU / planned budget in CHASER's run
Usage: python3 thesis_ch6.py <output dir>   (run from scheduler-comparison-v1)
"""
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'policy-mix'))
import confirm_analysis as ca  # noqa: E402
import rf_devcheck as rd  # noqa: E402

R = HERE / 'results'
INFLATION = HERE / 'thesis-ch6/kernel-inflation-tasks.csv'
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
WIDTH = 16 / 2.54
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 8, 'axes.titlesize': 8.5,
                     'axes.labelsize': 8, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5,
                     'hatch.linewidth': 0.8, 'axes.linewidth': 0.8})
LABEL = 7  # bar and point value labels, printed size
# Okabe-Ito colour-blind-safe palette (Wong, Nature Methods 8:441, 2011), as in thesis_ch4.py.
BLUE, VERMILLION, GREEN, ORANGE, PURPLE, GREY = '#0072B2', '#D55E00', '#009E73', '#E69F00', '#CC79A7', '#BBBBBB'
PLACEMENTS = (('p', 'wfd', 'WFD', BLUE, ''), ('p_ra', 'ra', 'RA', GREEN, '/'),
              ('p_cgb', 'cgb', 'CGB', ORANGE, '\\'), ('p_racgb', 'ra-cgb', 'RA-CGB', PURPLE, 'x'))
TYPES = (('deadline-small', '32 KiB type', ('cv00-low50', 'cv20-low50')),
         ('deadline-big', '768 KiB type', ('cv00-big25', 'cv20-big25')))
CV = {'cv00': 'Period CV 0', 'cv20': 'Period CV 0.2'}
OUTCOMES = (('success', 'Accepted, met every deadline', BLUE, ''),
            ('false_accept', 'Accepted, missed a deadline (false accept)', VERMILLION, '/'),
            ('false_reject', 'Rejected, a candidate met every deadline (false reject)', ORANGE, '\\'),
            ('true_reject', 'Rejected, no candidate met every deadline', GREY, 'x'))
METHODS = (('rf', 'RF'), ('static', 'D+M'), ('always', 'Always'))  # Always: run CHASER's placement on every set
KERNELS = (('gemm-u32', 'GEMM'), ('polybench-atax-u32', 'ATAX'), ('polybench-bicg-u32', 'BICG'),
           ('polybench-mvt-u32', 'MVT'), ('polybench-gesummv-u32', 'GESUMMV'), ('polybench-jacobi1d-u32', 'Jacobi-1D'),
           ('polybench-jacobi2d-u32', 'Jacobi-2D'))
HELD_OUT = (('polybench-2mm-u32', '2MM'), ('polybench-syrk-u32', 'SYRK'), ('polybench-trmm-u32', 'TRMM'),
            ('polybench-doitgen-u32', 'DOITGEN'))
GROUP_STYLE = {'synthetic': ('Synthetic task types (RF evaluation)', GREEN, ''),
               'seven': ('Seven unseen kernels', BLUE, '/'),
               'four': ('Four additional kernels', VERMILLION, '\\')}


def save(fig, name, header, table):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight', dpi=300)
    with open(OUT / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        for row in table:
            f.write(','.join(str(v) for v in row) + '\n')
    plt.close(fig)
    print('wrote', name)


def bar(ax, x, value, width, color, hatch, text=None, bottom=0.0, inside=False):
    # Hatch lines take the edge colour, so the black outline is a second bar (as in thesis_ch4.py).
    ax.bar(x, value, width, bottom=bottom, color=color, edgecolor='black', linewidth=0, hatch=hatch, zorder=3)
    ax.bar(x, value, width, bottom=bottom, fill=False, edgecolor='black', linewidth=0.5, zorder=4)
    if inside:
        if value:
            ax.annotate(text if text is not None else f'{value}', (x, bottom + value / 2), ha='center', va='center',
                        fontsize=LABEL, zorder=5, bbox=dict(facecolor='white', edgecolor='none', pad=0.5, alpha=0.9))
    elif text is not False:
        ax.annotate(text if text is not None else f'{value}', (x, bottom + value), xytext=(0, 1.5),
                    textcoords='offset points', ha='center', va='bottom', fontsize=LABEL)


def swatch(color, hatch):
    return (Patch(facecolor=color, edgecolor='black', linewidth=0, hatch=hatch),
            Patch(fill=False, edgecolor='black', linewidth=0.5))


def grid(ax):
    ax.grid(axis='y', color='#eeeeee', linewidth=0.5, zorder=0)


def legend(fig, items, ncol, extra=()):
    fig.legend([swatch(c, h) for _, c, h in items] + [h for h, _ in extra], [l for l, _, _ in items] + [l for _, l in extra],
               loc='lower center', ncol=ncol, frameon=False, bbox_to_anchor=(0.5, 1.0))


def label(r):
    return f"{r['heaviness']}/u{round(r['load'] * 100):03d}/s{r['set_id']:02d}"


# Experiment 27 rows: results.jsonl (states, TET, TAT) and rt-metrics.json (worst low-CLS-task inflation)
runs = {d: [json.loads(l) for l in (R / d / 'results.jsonl').open()] for d, _, _ in TYPES}
rt = {d: json.loads((R / d / 'rt-metrics.json').read_text())['cases'] for d, _, _ in TYPES}

# Figures 6.1, 6.2 and 6.5: inflation, TET and TAT over the common cases (numbered in the order the text cites them)
for name, ylabel, value, fmt in (
        ('figure-6-1', 'Worst low-CLS-task job CPU time /\nplanned budget',
         lambda d, r, key, build: rt[d][label(r)][build]['worst_memory_inflation'], '{:.2f}'),
        ('figure-6-2', 'TET (ms)', lambda d, r, key, build: r[key]['tet_ns'] / 1e6, '{:.0f}'),
        ('figure-6-5', 'TAT (ms)', lambda d, r, key, build: r[key]['tat_ns'] / 1e6, '{:.0f}')):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.9))
    table, width = [], 0.2
    for ax, (d, title, cells) in zip(axes, TYPES):
        top, ticks = 0.0, []
        for i, cell in enumerate(cells):
            members = [r for r in runs[d] if r['heaviness'] == cell and all(r[k]['state'] == 'ok' for k, *_ in PLACEMENTS)]
            ticks.append(f"{CV[cell[:4]]}\n({len(members)} cases)")
            for j, (key, build, abbr, color, hatch) in enumerate(PLACEMENTS):
                v = np.array([value(d, r, key, build) for r in members])
                q1, m, q3 = np.percentile(v, [25, 50, 75])
                x = i + (j - 1.5) * width
                bar(ax, x, m, width * 0.92, color, hatch, text=False)
                ax.errorbar(x, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.6, capsize=1.5, zorder=5)
                ax.annotate(fmt.format(m), (x, q3), xytext=(0, 1.5), textcoords='offset points', ha='center',
                            va='bottom', fontsize=LABEL if name == 'figure-6-1' else LABEL - 1)
                top = max(top, q3)
                table.append((d.split('-')[1], cell, abbr, len(v), f'{m:.4f}', f'{q1:.4f}', f'{q3:.4f}'))
        ax.set_xticks(range(len(cells)))
        ax.set_xticklabels(ticks)
        ax.set_ylim(0, top * 1.15)
        ax.set_title(title)
        grid(ax)
    axes[0].set_ylabel(ylabel)
    legend(fig, [(abbr, c, h) for _, _, abbr, c, h in PLACEMENTS], 4)
    fig.tight_layout()
    save(fig, name, 'type,cell,placement,cases,median,q1,q3', table)

# Figures 6.3-6.4: task sets meeting every deadline per load (a run that failed to start counts as not meeting)
startup = []
for name, (d, title, cells) in zip(('figure-6-3', 'figure-6-4'), TYPES):
    loads = sorted({r['load'] for r in runs[d]})
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 4.6), sharey=True)
    table, width = [], 0.2
    for ax, cell in zip(axes, cells):
        for i, load in enumerate(loads):
            rs = [r for r in runs[d] if r['heaviness'] == cell and r['load'] == load]
            for j, (key, build, abbr, color, hatch) in enumerate(PLACEMENTS):
                met = sum(r[key]['state'] == 'ok' for r in rs)
                startup += [(d, cell, load, abbr) for r in rs if r[key]['state'] not in ('ok', 'deadline')]
                bar(ax, i + (j - 1.5) * width, met, width * 0.92, color, hatch)
                table.append((cell, load, abbr, met, len(rs)))
        ax.set_xticks(range(len(loads)))
        ax.set_xticklabels([f'{l:g}' for l in loads])
        ax.set_ylim(0, 21)
        ax.set_ylabel('Task sets meeting\nevery deadline (of 18)')
        ax.set_title(CV[cell[:4]])
        grid(ax)
    axes[-1].set_xlabel('Per-core load')
    legend(fig, [(abbr, c, h) for _, _, abbr, c, h in PLACEMENTS], 4)
    fig.tight_layout()
    save(fig, name, 'cell,load,placement,sets_met,sets', table)
print('Partitioned runs that failed to start (counted as not meeting):', startup)

# Figure 6.6: Algorithm 1 placeability per load (both period CV cells pooled)
ladder = json.loads((R / 'deadline-ladder/ladder.json').read_text())['summary']
variants = (('caas', 'CAAS (CA-CSRD + Algorithm 1)', BLUE, ''), ('cls-a1', 'CLS-A1 (CLS + Algorithm 1)', GREEN, '/'),
            ('cls-a1-cal', 'CLS-A1 with the calibrated CLS threshold', ORANGE, '\\'))
fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 4.6))
table, width = [], 0.27
for ax, kind, title in zip(axes, ('small', 'big'), ('32 KiB type', '768 KiB type')):
    by_load = {}
    for key, cell in ladder[kind].items():
        load = int(key.split('/u')[1]) / 1000
        for v, *_ in variants:
            by_load.setdefault(load, {}).setdefault(v, [0, 0])
            by_load[load][v][0] += cell[v]['placeable']
            by_load[load][v][1] += cell[v]['runs']
    loads = sorted(by_load)
    for i, load in enumerate(loads):
        for j, (v, _, color, hatch) in enumerate(variants):
            placed, total = by_load[load][v]
            bar(ax, i + (j - 1) * width, placed, width * 0.92, color, hatch)
            table.append((kind, load, v, placed, total))
    ax.axhline(36, color='#888888', linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)
    ax.set_xticks(range(len(loads)))
    ax.set_xticklabels([f'{l:g}' for l in loads])
    ax.set_ylim(0, 42)
    ax.set_ylabel('Placeable task sets (of 36)')
    ax.set_title(title)
    grid(ax)
axes[-1].set_xlabel('Per-core load')
legend(fig, [(l, c, h) for _, l, c, h in variants], 2,
       extra=[(Line2D([], [], color='#888888', linewidth=0.8, linestyle=(0, (3, 3))), 'CGB and RA-CGB: all 36 sets placeable')])
fig.tight_layout()
save(fig, 'figure-6-6', 'type,load,variant,placeable,runs', table)

# Figure 6.7: AUC for CHASER's placement meeting every deadline (experiment 44)
CONFIRM = ('confirm-small', 'confirm-big', 'confirm-mem')
records, _ = ca.sets(R, CONFIRM)
groups = (('all', 'All types'), ('confirm-small', '32 KiB type'), ('confirm-big', '768 KiB type'),
          ('confirm-mem', 'Memory-bound type'))
scores = (('p_chaser', 'RF probability', BLUE, ''), ('occupancy', 'D + M', GREEN, '/'), ('cache_demand', 'D', ORANGE, '\\'))
fig, ax = plt.subplots(figsize=(WIDTH, 2.8))
table, width, ticks = [], 0.26, []
for g, (group, title) in enumerate(groups):
    rs = [r for r in records if r['p_chaser'] is not None and group in ('all', r['design'])]
    y = [int(r['met']['ra-cgb']) for r in rs]
    ticks.append(f'{title}\n({len(rs)} sets)')
    for i, (key, _, color, hatch) in enumerate(scores):
        v = rd.auc(y, [r[key] if key == 'p_chaser' else -r[key] for r in rs])
        bar(ax, g + (i - 1) * width, v, width * 0.92, color, hatch, text=f'{v:.3f}')
        table.append((group, key, len(rs), f'{v:.4f}'))
ax.axhline(0.5, color='#888888', linewidth=0.8, linestyle=(0, (1, 2)), zorder=1)
ax.set_xticks(range(len(groups)))
ax.set_xticklabels(ticks)
ax.set_ylim(0, 1.1)
ax.set_ylabel('AUC, CHASER placement\nmeets every deadline')
grid(ax)
legend(fig, [(l, c, h) for _, l, c, h in scores], 3)
fig.tight_layout()
save(fig, 'figure-6-7', 'group,score,sets,auc', table)


def outcome_panels(name, panels, figsize, sharey):
    fig, axes = plt.subplots(1, len(panels), figsize=figsize, sharey=sharey)
    table = []
    for ax, (title, tally) in zip(axes, panels):
        top = 0
        for m, (method, _) in enumerate(METHODS):
            bottom = 0
            for key, _, color, hatch in OUTCOMES:
                v = tally[method][key]
                bar(ax, m, v, 0.7, color, hatch, bottom=bottom, inside=True)
                bottom += v
                table.append((title.replace('\n', ' '), method, key, v))
            top = max(top, bottom)
        ax.set_xticks(range(len(METHODS)))
        ax.set_xticklabels([l for _, l in METHODS], fontsize=6.5)
        ax.set_title(title)
        grid(ax)
    axes[0].set_ylabel('Task sets')
    legend(fig, [(l, c, h) for _, l, c, h in OUTCOMES], 2)
    fig.tight_layout()
    save(fig, name, 'panel,method,outcome,sets', table)


# Figure 6.8: experiment 44 decision outcomes
confirm = json.loads((R / 'confirm-analysis/confirm.json').read_text())
outcome_panels('figure-6-8', [(f"All types\n({confirm['overall']['sets']} sets)", confirm['overall'])] +
               [(f"{t}\n({confirm['groups'][g + '-v1']['sets']} sets)", confirm['groups'][g + '-v1']) for g, t in groups[1:]],
               (WIDTH, 3.3), sharey=False)

# Figure 6.9: experiment 45 decision outcomes per load
real = json.loads((R / 'real-kernels-analysis/confirm.json').read_text())
loads = sorted({float(k.split()[1]) for k in real['groups'] if ' ' in k})
outcome_panels('figure-6-9', [(f"Load {l:g}\n({real['groups'][f'real-kernels-v1 {l:g}']['sets']} sets)",
                               real['groups'][f'real-kernels-v1 {l:g}']) for l in loads], (WIDTH, 3.3), sharey=True)

# Figure 6.10: share met per bin of the RF probability (post hoc), experiments 44 and 45
calibration = json.loads((R / 'real-kernels-analysis/report.json').read_text())['calibration']
bins = sorted({(b['low'], b['high']) for rows in calibration.values() for b in rows})
series = (('experiment 44', 'Synthetic task sets (RF evaluation)', BLUE, ''),
          ('experiment 45', 'Seven unseen kernels', VERMILLION, '/'))
fig, ax = plt.subplots(figsize=(WIDTH, 2.9))
table, width = [], 0.38
for j, (key, _, color, hatch) in enumerate(series):
    found = {(b['low'], b['high']): b for b in calibration[key] if b['sets']}
    for i, edges in enumerate(bins):
        x = i + (j - 0.5) * width
        if edges not in found:
            ax.annotate('no sets', (x, 0), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=LABEL - 0.5, color='#666666', rotation=90)
            continue
        b = found[edges]
        bar(ax, x, b['met'] / b['sets'], width * 0.92, color, hatch, text=f"{b['met']}/{b['sets']}")
        table.append((key, edges[0], edges[1], b['sets'], b['met'], f"{b['mean_probability']:.4f}"))
cut = next(i for i, e in enumerate(bins) if e[0] == 0.8) - 0.5
ax.axvline(cut, color='#555555', linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)
ax.annotate('τ = 0.8', (cut, 1.12), xytext=(3, 0), textcoords='offset points', fontsize=LABEL, va='center')
ax.set_xticks(range(len(bins)))
ax.set_xticklabels([f'{lo:.2f}–{hi:.2f}' for lo, hi in bins])
ax.set_xlabel('RF probability that the CHASER placement meets every deadline')
ax.set_ylabel('Share of sets where the\nCHASER placement met')
ax.set_ylim(0, 1.2)
grid(ax)
legend(fig, [(l, c, h) for _, l, c, h in series], 2)
fig.tight_layout()
save(fig, 'figure-6-10', 'experiment,low,high,sets,met,mean_probability', table)

# Figure 6.11: per-task L1 misses per microsecond (pre-run check inputs), percentile boxes on a log axis
values = json.loads((R / 'heldout-kernels-analysis/report.json').read_text())['task_values']
values45 = json.loads((R / 'real-kernels-analysis/report.json').read_text())['task_values']
sources = [('synthetic', s, values['synthetic'][k]) for k, s in (('confirm-small-v1', '32 KiB'), ('confirm-big-v1', '768 KiB'),
                                                                   ('confirm-mem-v1', 'Memory-bound'))] + \
          [('seven', s, values45['real_by_kernel'][k]) for k, s in KERNELS] + \
          [('four', s, values['real_by_kernel'][k]) for k, s in HELD_OUT]
fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
table = []
for i, (group, name, stats) in enumerate(sources):
    _, color, hatch = GROUP_STYLE[group]
    q = stats['rate']
    ax.add_patch(Rectangle((i - 0.3, q['p25']), 0.6, q['p75'] - q['p25'], facecolor=color, edgecolor='black',
                           linewidth=0, hatch=hatch, zorder=3))
    ax.add_patch(Rectangle((i - 0.3, q['p25']), 0.6, q['p75'] - q['p25'], fill=False, edgecolor='black', linewidth=0.5, zorder=4))
    ax.plot([i, i], [q['p5'], q['p25']], color='black', linewidth=0.6, zorder=2)
    ax.plot([i, i], [q['p75'], q['p95']], color='black', linewidth=0.6, zorder=2)
    for y in (q['p5'], q['p95']):
        ax.plot([i - 0.12, i + 0.12], [y, y], color='black', linewidth=0.6, zorder=2)
    ax.plot([i - 0.3, i + 0.3], [q['p50'], q['p50']], color='black', linewidth=1.2, zorder=5)
    ax.annotate(f"{q['p50']:.2f}", (i, q['p95']), xytext=(0, 1.5), textcoords='offset points', ha='center', va='bottom',
                fontsize=LABEL - 0.5)
    table.append((group, name.replace('\n', ' '), stats['tasks'], *(f"{q[k]:.4f}" for k in ('p5', 'p25', 'p50', 'p75', 'p95'))))
ax.set_yscale('log')
ax.set_xlim(-0.6, len(sources) - 0.4)
ax.set_ylim(min(s[2]['rate']['p5'] for s in sources) / 2, max(s[2]['rate']['p95'] for s in sources) * 2.5)
ax.set_xticks(range(len(sources)))
ax.set_xticklabels([s[1] for s in sources], rotation=35, ha='right', rotation_mode='anchor')
ax.set_ylabel('L1 misses per µs of\nisolated execution (log)')
grid(ax)
legend(fig, [GROUP_STYLE[g] for g in ('synthetic', 'seven', 'four')], 3)
fig.tight_layout()
save(fig, 'figure-6-11', 'group,source,tasks,p5,p25,p50,p75,p95', table)

# Figure 6.12: per-task worst job CPU / planned budget in CHASER's runs at loads 0.625 and 0.70 (post hoc)
per = {}
for r in csv.DictReader(INFLATION.open()):
    per.setdefault(r['kernel'], []).append(float(r['worst_over_planned']))
order = [('seven', k, s) for k, s in KERNELS] + [('four', k, s) for k, s in HELD_OUT]
fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
table = []
for i, (group, kernel, name) in enumerate(order):
    _, color, hatch = GROUP_STYLE[group]
    v = np.array(per[kernel])
    p5, p25, p50, p75, p95 = np.percentile(v, [5, 25, 50, 75, 95])
    ax.add_patch(Rectangle((i - 0.3, p25), 0.6, p75 - p25, facecolor=color, edgecolor='black', linewidth=0, hatch=hatch, zorder=3))
    ax.add_patch(Rectangle((i - 0.3, p25), 0.6, p75 - p25, fill=False, edgecolor='black', linewidth=0.5, zorder=4))
    ax.plot([i, i], [p5, p25], color='black', linewidth=0.6, zorder=2)
    ax.plot([i, i], [p75, p95], color='black', linewidth=0.6, zorder=2)
    for y in (p5, p95):
        ax.plot([i - 0.12, i + 0.12], [y, y], color='black', linewidth=0.6, zorder=2)
    ax.plot([i - 0.3, i + 0.3], [p50, p50], color='black', linewidth=1.2, zorder=5)
    ax.annotate(f'{p50:.2f}', (i, p95), xytext=(0, 1.5), textcoords='offset points', ha='center', va='bottom', fontsize=LABEL - 0.5)
    table.append((group, name, len(v), *(f'{x:.4f}' for x in (p5, p25, p50, p75, p95))))
ax.axhline(1.0, color='#888888', linewidth=0.8, linestyle=(0, (1, 2)), zorder=1)
ax.set_xlim(-0.6, len(order) - 0.4)
ax.set_ylim(0.9, max(np.percentile(per[k], 95) for _, k, _ in order) * 1.1)
ax.set_xticks(range(len(order)))
ax.set_xticklabels([f'{s} ({len(per[k])})' for _, k, s in order], rotation=35, ha='right', rotation_mode='anchor')
ax.set_ylabel('Worst job CPU time /\nplanned budget')
grid(ax)
legend(fig, [GROUP_STYLE[g] for g in ('seven', 'four')], 2)
fig.tight_layout()
save(fig, 'figure-6-12', 'group,kernel,tasks,p5,p25,p50,p75,p95', table)
