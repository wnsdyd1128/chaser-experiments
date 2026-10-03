"""Paper-style bars of measured values for the policy-mix run (multi-factor placement comparison).

Files in <run dir>/figures:
  policy-mix-tat          panels = per-core load; bars = the six configurations; median TAT
                          over the sets that met every deadline in that configuration, whiskers
                          IQR, label = sets with a deadline miss
  policy-mix-schedulable  panels = load; sets meeting every deadline per configuration
  policy-mix-tat-by-<factor>  panels = the factor's levels (both loads pooled); bars = the
                          four Partitioned placements; median TAT over the sets where all four
                          met every deadline, whiskers IQR
  policy-mix-selector     panels = cross-validation scheme; bars = mean measured TAT of the
                          placement each method chose (pm_analysis selector), label = choices
                          that missed a deadline
Usage: python3 policy_mix_bars.py <run output dir>
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
factors = json.loads((O / 'protocol.json').read_text())['set_factors']
analysis = json.loads((O / 'analysis.json').read_text())
CONFIGS = (('g', 'Global', '#2a78d6', ''), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
           ('p', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
           ('p_tg', 'Partitioned (traffic-grouped + U-balanced)', '#e0b83a', 'xx'),
           ('p_ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
           ('p_ratg', 'Partitioned (release-aware within traffic grouping)', '#d95f02', '++'))
PLACEMENTS = CONFIGS[2:]
FACTOR_TITLES = dict(periods='Periods', low='Low-CLS 32 KiB tasks', traffic='Their traffic',
                     big='768 KiB tasks', alpha='Task-U Dirichlet alpha', heavy='Heavy task (U 0.5-0.6)')
LOADS = sorted({r['load'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def ok(r, key):
    return r[key].get('state') == 'ok'


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def bars(ax, series, values, table, panel, note=None):
    """values[i]: array of measured values for series i; note[i]: text under the value label."""
    top = 0
    for k, ((key, _, color, hatch), v) in enumerate(zip(series, values)):
        v = np.asarray(v, dtype=float)
        if not len(v):
            continue
        q1, m, q3 = np.percentile(v, [25, 50, 75])
        top = max(top, q3)
        ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2,
                    zorder=4)
        label = fmt(m) + (f'\n{note[k]}' if note and note[k] else '')
        ax.annotate(label, (k, q3), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                    fontsize=7)
        table.append((panel, key, len(v), m, q1, q3))
    ax.set_ylim(0, top * 1.3 if top else 1)
    ax.set_xticks([])
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)


def finish(fig, series, title, stem, table, header, ncol=3):
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in series]
    fig.legend(handles=handles, loc='upper center', ncol=ncol, frameon=False, bbox_to_anchor=(0.55, 0.96),
               fontsize=9)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write(header + '\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


SUBTITLE = '80 task sets x 2 loads, six factors drawn per set, workload O2'

fig, axes = plt.subplots(1, len(LOADS), figsize=(5.2 * len(LOADS) + 1, 5.0), dpi=200)
table = []
for ax, load in zip(axes, LOADS):
    members = [r for r in rows if r['load'] == load]
    values = [[r[k]['tat_ns'] / 1e6 for r in members if ok(r, k)] for k, *_ in CONFIGS]
    misses = [sum(not ok(r, k) for r in members) for k, *_ in CONFIGS]
    bars(ax, CONFIGS, values, table, load, [f'{m} miss' if m else '' for m in misses])
    ax.set_title(f'Per-core U {load}', loc='left', fontsize=9.5)
    ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
axes[0].set_ylabel('Measured TAT (ms)')
finish(fig, CONFIGS, f'Measured TAT per configuration: {SUBTITLE}', 'policy-mix-tat', table,
       'load,configuration,n,median_ms,q1_ms,q3_ms')

fig, axes = plt.subplots(1, len(LOADS), figsize=(5.2 * len(LOADS) + 1, 5.0), dpi=200)
table = []
for ax, load in zip(axes, LOADS):
    members = [r for r in rows if r['load'] == load]
    for k, (key, _, color, hatch) in enumerate(CONFIGS):
        count = sum(ok(r, key) for r in members)
        ax.bar(k, count, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        ax.annotate(str(count), (k, count), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                    fontsize=8)
        table.append((load, key, len(members), count))
    ax.set_ylim(0, len(members) * 1.18)
    ax.set_xticks([])
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_title(f'Per-core U {load} ({len(members)} sets)', loc='left', fontsize=9.5)
    ax.text(0.02, 0.97, 'Higher is better ↑', transform=ax.transAxes, fontsize=8, va='top')
axes[0].set_ylabel('Task sets meeting every deadline')
finish(fig, CONFIGS, f'Schedulable task sets per configuration: {SUBTITLE}', 'policy-mix-schedulable', table,
       'load,configuration,sets,schedulable')

common = [r for r in rows if all(ok(r, k) for k, *_ in PLACEMENTS)]
for factor, title in FACTOR_TITLES.items():
    levels = sorted({factors[r['set_id']][factor] for r in rows}, key=str)
    fig, axes = plt.subplots(1, len(levels), figsize=(4.2 * len(levels) + 1, 5.0), dpi=200, squeeze=False)
    table = []
    for ax, level in zip(axes[0], levels):
        members = [r for r in common if factors[r['set_id']][factor] == level]
        bars(ax, PLACEMENTS, [[r[k]['tat_ns'] / 1e6 for r in members] for k, *_ in PLACEMENTS], table, level)
        ax.set_title(f'{title}: {level} ({len(members)} cases)', loc='left', fontsize=9.5)
        ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0][0].set_ylabel('Measured TAT (ms)')
    finish(fig, PLACEMENTS, f'Partitioned placements by {title.lower()}: cases where all four met every deadline, '
           'both loads', f'policy-mix-tat-by-{factor}', table, f'{factor},placement,n,median_ms,q1_ms,q3_ms', ncol=2)

METHODS = (('oracle', 'Best placement (measured)', '#2b2b2b', ''),
           ('always wfd', 'Always U-balanced (WFD)', '#8c6d31', '--'),
           ('always tg', 'Always traffic-grouped', '#e0b83a', 'xx'),
           ('always ra', 'Always release-aware', '#1baf7a', '\\\\'),
           ('always ra-tg', 'Always release-aware within traffic grouping', '#d95f02', '++'),
           ('R0 / regressor', 'RF regression: CLS + U (plan R0)', '#7fb2e5', ''),
           ('R2 / regressor', 'RF regression: R1 + traffic, footprint, structure (R2)', '#4a3aa7', '--'),
           ('R4 / regressor', 'RF regression: R2 + bag of task types (R4)', '#9e9e9e', '||'))
results = analysis['selector']['results']
fig, axes = plt.subplots(1, len(results), figsize=(5.4 * len(results) + 1, 5.2), dpi=200)
table = []
for ax, (scheme, methods) in zip(axes, results.items()):
    top = 0
    for k, (method, _, color, hatch) in enumerate(METHODS):
        m = methods[method]
        ax.bar(k, m['mean_tat_ms'], 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        label = fmt(m['mean_tat_ms']) + (f"\n{m['infeasible']:.1f} miss" if m['infeasible'] >= 0.05 else '')
        ax.annotate(label, (k, m['mean_tat_ms']), xytext=(0, 2), textcoords='offset points', ha='center',
                    va='bottom', fontsize=7)
        top = max(top, m['mean_tat_ms'])
        table.append((scheme, method, m['mean_tat_ms'], m['infeasible']))
    ax.set_ylim(0, top * 1.3)
    ax.set_xticks([])
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_title({'set': 'Unseen task sets', 'condition': 'Unseen mechanism mix (low-CLS x traffic x 768 KiB)'}
                 .get(scheme, scheme), loc='left', fontsize=9.5)
    ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
axes[0].set_ylabel('Mean measured TAT of the chosen placement (ms)')
finish(fig, METHODS, 'Placement chosen per task set: oracle, fixed rules and RF selectors, both loads',
       'policy-mix-selector', table, 'scheme,method,mean_tat_ms,infeasible_choices', ncol=2)
