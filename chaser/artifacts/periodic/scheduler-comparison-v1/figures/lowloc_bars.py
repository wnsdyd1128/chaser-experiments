"""Thesis-style figures for experiments 47 and 48 (real low-locality kernels: naive transpose, planar complex corner
turn; 48 caps every task's data).

Measured values, abbreviated placement names (WFD, RA, CGB, RA-CGB), no in-figure title; 16 cm text width.
Each figure has one panel per period CV (0 and 0.2) and a bar group per per-core load:
  lowloc-met         task sets meeting every deadline (a bar reads met above /measured when a run failed to start)
  lowloc-violated    violated jobs (missed / released over the measured window) of all measured runs, in %
  lowloc-inflation   worst low-CLS job CPU / planned budget (V3), median over the sets where all four met, whiskers IQR
  lowloc-tet         TET (V6, CPU time of every measured job), the same sets
                     (these two are drawn only when some set met every deadline under all four placements: none in 47)
  lowloc-corun-low   post hoc: low-CLS tasks of all measured runs; per task, the median CPU time of its completed jobs
                     (warm-up included) over its planned budget; bars are the median over the tasks, whiskers IQR
  lowloc-corun-high  the same for the high-CLS tasks
Usage: python3 lowloc_bars.py <lowloc-kernels output> <dest dir>
Run with PYTHONPATH=<c3 code copy>:policy-mix:period-distribution (as lowloc_analysis.py).
"""
import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

import deadline_analysis as da
import lowloc_analysis as la

SOURCE = Path(sys.argv[1]).resolve()
cases = la.load(SOURCE)
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
WIDTH = 16 / 2.54
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 8, 'axes.titlesize': 8.5,
                     'axes.labelsize': 8, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5,
                     'hatch.linewidth': 0.8, 'axes.linewidth': 0.8})
LABEL = 7
BLUE, GREEN, ORANGE, PURPLE = '#0072B2', '#009E73', '#E69F00', '#CC79A7'  # Okabe-Ito, as thesis_ch4.py
PLACEMENTS = (('wfd', 'WFD', BLUE, ''), ('ra', 'RA', GREEN, '/'), ('cgb', 'CGB', ORANGE, '\\'),
              ('ra-cgb', 'RA-CGB', PURPLE, 'x'))
CELLS = (('cv00-lowloc50', 'Period CV 0'), ('cv20-lowloc50', 'Period CV 0.2'))
LOADS = sorted({c['load'] for c in cases})
BAR = 0.2


def bar(ax, x, value, color, hatch, text):
    ax.bar(x, value, BAR * 0.92, color=color, edgecolor='black', linewidth=0, hatch=hatch, zorder=3)
    ax.bar(x, value, BAR * 0.92, fill=False, edgecolor='black', linewidth=0.5, zorder=4)
    ax.annotate(text, (x, value), xytext=(0, 1.5), textcoords='offset points', ha='center', va='bottom', fontsize=LABEL)


def figure(name, ylabel, draw, header):
    """draw(ax, cell, load, i) -> table rows; one panel per period CV, one bar group per load."""
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 5.6), sharey=True)
    table = []
    for ax, (cell, title) in zip(axes, CELLS):
        ticks = []
        for i, load in enumerate(LOADS):
            group = [c for c in cases if c['heaviness'] == cell and c['load'] == load]
            rows, tick = draw(ax, group, i)
            table += [(cell, load) + r for r in rows]
            ticks.append(f'Per-core load {load:g}\n({tick})')
        ax.set_xticks(range(len(LOADS)))
        ax.set_xticklabels(ticks)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis='y', color='#eeeeee', linewidth=0.5, zorder=0)
    axes[0].set_ylim(0, axes[0].get_ylim()[1] * 1.1)
    handles = [(Patch(facecolor=c, edgecolor='black', linewidth=0, hatch=h), Patch(fill=False, edgecolor='black', linewidth=0.5))
               for _, _, c, h in PLACEMENTS]
    fig.legend(handles, [l for _, l, _, _ in PLACEMENTS], loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout()
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight', dpi=300)
    with open(OUT / f'{name}.csv', 'w') as f:
        f.write(header + '\n')
        f.writelines(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in row) + '\n' for row in table)
    plt.close(fig)
    print('wrote', name)


def met_bars(ax, group, i):
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    rows = []
    for j, (build, _, color, hatch) in enumerate(PLACEMENTS):
        runs = [c['runs'][build] for c in group]
        met, measured = sum(da.met(r) for r in runs), sum(da.measured(r) for r in runs)
        bar(ax, i + (j - 1.5) * BAR, met, color, hatch, f'{met}' if measured == len(runs) else f'{met}\n/{measured}')
        rows.append((build, met, measured, len(runs)))
    return rows, f'{len(group)} sets'


def violated_bars(ax, group, i):
    rows = []
    for j, (build, _, color, hatch) in enumerate(PLACEMENTS):
        runs = [c['runs'][build] for c in group if da.measured(c['runs'][build])]
        missed, expected = sum(r['missed_jobs'] for r in runs), sum(r['expected_jobs'] for r in runs)
        share = 100 * missed / expected
        bar(ax, i + (j - 1.5) * BAR, share, color, hatch, f'{share:.0f}')
        rows.append((build, missed, expected, share))
    return rows, f'{len(group)} sets'


def median_bars(field, scale, fmt):
    def draw(ax, group, i):
        both = [c for c in group if all(da.met(c['runs'][b]) for b, *_ in PLACEMENTS)]
        rows = []
        for j, (build, _, color, hatch) in enumerate(PLACEMENTS):
            if not both:
                continue
            q1, m, q3 = np.percentile([c['runs'][build][field] * scale for c in both], [25, 50, 75])
            x = i + (j - 1.5) * BAR
            bar(ax, x, m, color, hatch, '')
            ax.errorbar(x, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.6, capsize=1.5, zorder=5)
            ax.annotate(format(m, fmt), (x, q3), xytext=(0, 1.5), textcoords='offset points', ha='center', va='bottom',
                        fontsize=LABEL)
            rows.append((build, len(both), m, q1, q3))
        return rows, f'{len(both)} sets, all met'
    return draw


def corun(case, build, role) -> list[float]:
    """Per task of the role: median completed-job CPU / planned budget in this run."""
    path = SOURCE / da.label(case['heaviness'], case['load'], case['set_id']) / build
    tasks = json.loads((path / 'configuration.json').read_text())['tasks']
    jobs = json.loads((path / 'p/measurements.jsonl').read_text().splitlines()[0])['jobs']
    ratios = {}
    for j in jobs:
        t = tasks[j['task']]
        if t['role'] == role and j.get('completion_ns') is not None:
            ratios.setdefault(j['task'], []).append((j['cpu_after_ns'] - j['cpu_before_ns']) / (t['u_planned'] * t['period_ticks'] * 1e6))
    return [float(np.median(v)) for v in ratios.values()]


def corun_bars(role):
    def draw(ax, group, i):
        rows = []
        for j, (build, _, color, hatch) in enumerate(PLACEMENTS):
            values = [v for c in group if da.measured(c['runs'][build]) for v in corun(c, build, role)]
            q1, m, q3 = np.percentile(values, [25, 50, 75])
            x = i + (j - 1.5) * BAR
            bar(ax, x, m, color, hatch, '')
            ax.errorbar(x, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.6, capsize=1.5, zorder=5)
            ax.annotate(f'{m:.1f}', (x, q3), xytext=(0, 1.5), textcoords='offset points', ha='center', va='bottom',
                        fontsize=LABEL)
            rows.append((build, len(values), m, q1, q3))
        return rows, f'{len(group)} sets'
    return draw


figure('lowloc-met', 'Task sets meeting\nevery deadline', met_bars, 'cell,load,placement,sets_met,measured,sets')
figure('lowloc-violated', 'Violated jobs (%)', violated_bars, 'cell,load,placement,missed_jobs,expected_jobs,percent')
if any(all(da.met(c['runs'][b]) for b, *_ in PLACEMENTS) for c in cases):
    figure('lowloc-inflation', 'Worst low-CLS job CPU\n/ planned budget', median_bars('worst_memory_inflation', 1, '.2f'),
           'cell,load,placement,sets,median,q1,q3')
    figure('lowloc-tet', 'TET (s)', median_bars('tet_ns', 1e-9, '.2f'), 'cell,load,placement,sets,median_s,q1_s,q3_s')
for role, name in (('low', 'Low-CLS'), ('high', 'High-CLS')):
    figure(f'lowloc-corun-{role}', f'{name} job CPU\n/ planned budget', corun_bars(role),
           'cell,load,placement,tasks,median,q1,q3')
