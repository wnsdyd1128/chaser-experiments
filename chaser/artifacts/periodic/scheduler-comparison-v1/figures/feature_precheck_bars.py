"""Paper-style bars of the measured TAT of the option each method chose in the feature pre-check.

Bars: mean over the task sets of a panel of the chosen option's measured TAT (each set first
averaged over the five RF seeds); RF bars use the plain classifier. A label above a bar counts
choices of an option that missed a deadline (their TAT is left out of the mean).
Files in <run dir>/figures:
  precheck-placement-condition-{exp5,exp6-exp7,exp8}  each condition held out of training
  precheck-placement-set                              unseen task sets, one panel per study
  precheck-hl-{policy,family}-condition-{light,heavy} experiment 9, each cell held out
Usage: python3 feature_precheck_bars.py <pre-check output dir>
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
samples = [json.loads(l) for l in open(O / 'samples.jsonl')]
predictions = {(r['decision'], r['scheme'], r['method']): np.array(r['choices'])
               for r in map(json.loads, open(O / 'predictions.jsonl'))}
ALWAYS = {'placement': (('always mixed', 'Always mixed'), ('always grouped', 'Always grouped')),
          'hl-policy': (('always WFD', 'Always WFD'), ('always informed', 'Always informed')),
          'hl-family': (('always Partitioned', 'Always Partitioned'), ('always Clustered', 'Always Clustered'),
                        ('always Global', 'Always Global'))}
ALWAYS_STYLE = (('#9e9e9e', '//'), ('#cfcfcf', '..'), ('#ececec', 'oo'))
RF_SERIES = (('R0 / classifier', 'RF: CLS + U (plan R0)', '#7fb2e5', ''),
             ('R0-CLP / classifier', 'RF: CLP + U (plan)', '#2a78d6', '\\\\'),
             ('R1 / classifier', 'RF: R0 + period (R1)', '#eb6834', 'xx'),
             ('R2 / classifier', 'RF: R1 + traffic, footprint, structure (R2)', '#4a3aa7', '--'),
             ('R3 / classifier', 'RF: R1 + bag of task types (R3)', '#1baf7a', '++'),
             ('R4 / classifier', 'RF: R2 + bag of task types (R4)', '#e0b83a', '||'))
TITLES = {
    'exp5': lambda c: (f"Traffic {c.split()[0]}, {round(16 * float(c.split('=')[1]))} of 16 low-CLS"),
    'exp6': lambda c: c.replace('period', 'Period'),
    'exp7': lambda c: c.replace('U CV', 'Task-U CV'),
    'exp8': lambda c: {'SL': '4 special: 32 KiB, low CLS', 'BL': '4 special: 768 KiB, low CLS',
                       'SH': '4 special: 32 KiB, high CLS', 'BH': '4 special: 768 KiB, high CLS'}[c],
    'exp9': lambda c: (f"{'Small tasks only' if c.startswith('light') else 'With 2 big tasks'}, "
                       f"U per core {c.split()[-1]}"),
}
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)


def series(decision):
    """(method, legend label, color, hatch) in bar order."""
    always = tuple((m, label, *style) for (m, label), style in zip(ALWAYS[decision], ALWAYS_STYLE))
    return (('oracle', 'Best option (measured)', '#2b2b2b', ''),) + always + RF_SERIES


def chosen(decision, scheme, method, members):
    """Per set: TAT of the chosen option averaged over seeds (NaN if infeasible); infeasible count."""
    runs = predictions[(decision, scheme, method)][:, members]
    # seeds x sets; inf marks an infeasible option
    tat = np.array([[samples_by[decision][i]['tat_ns'][k] for i, k in zip(members, row)] for row in runs],
                   dtype=float)
    infeasible = np.isinf(tat).sum(axis=1).mean()
    feasible = np.isfinite(tat)
    seeds = feasible.sum(axis=0)  # a set every seed sent to an infeasible option has no TAT
    per_set = np.where(feasible, tat, 0).sum(axis=0)[seeds > 0] / seeds[seeds > 0]
    return (per_set.mean() / 1e6 if len(per_set) else float('nan')), infeasible


samples_by = {}
for s in samples:
    samples_by.setdefault(s['decision'], {})[s['index']] = s


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def figure(decision, scheme, panels, stem, title):
    """panels: [(panel title, sample indices)]"""
    names = series(decision)
    fig, axes = plt.subplots(1, len(panels), figsize=(3.9 * len(panels) + 1.2, 5.2), dpi=200, squeeze=False)
    table = []
    for ax, (name, members) in zip(axes[0], panels):
        heights = []
        for k, (method, _, color, hatch) in enumerate(names):
            value, infeasible = chosen(decision, scheme, method, members)
            heights.append(value)
            ax.bar(k, value, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            label = fmt(value) + (f'\n{infeasible:.0f} miss' if infeasible >= 0.5 else '')
            ax.annotate(label, (k, value), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=6.3, rotation=90)
            table.append((name, method, len(members), value, infeasible))
        # Conditions differ in TAT scale, so each panel gets its own axis.
        ax.set_ylim(0, np.nanmax(heights) * 1.32)
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
        ax.set_title(name, loc='left', fontsize=9.5)
        ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    axes[0][0].set_ylabel('Measured TAT of the chosen option (ms)')
    handles = [Patch(facecolor=color, edgecolor='black', hatch=hatch, label=label) for _, label, color, hatch in names]
    fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.55, 0.955), fontsize=9)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('panel,method,sets,mean_tat_ms,infeasible_choices\n')
        for t in table:
            f.write(','.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


def members(decision, keep):
    return [s['index'] for s in samples if s['decision'] == decision and keep(s)]


def condition_panels(decision, study, order=None, keep=lambda c: True):
    conditions = sorted({s['condition'] for s in samples
                         if s['decision'] == decision and s['study'] == study and keep(s['condition'])}, key=order)
    return [(TITLES[study](c), members(decision, lambda s, c=c: s['study'] == study and s['condition'] == c))
            for c in conditions]


heavy_load = lambda c: float(c.split()[-1])
placement_title = 'Partitioned grouped vs mixed: choice by RF trained without this condition, workload O2'
figure('placement', 'condition', condition_panels('placement', 'exp5'), 'precheck-placement-condition-exp5', placement_title)
figure('placement', 'condition', condition_panels('placement', 'exp6', lambda c: -float(c.split()[1]))
       + condition_panels('placement', 'exp7'), 'precheck-placement-condition-exp6-exp7', placement_title)
figure('placement', 'condition', condition_panels('placement', 'exp8', lambda c: 'SLBLSHBH'.index(c)),
       'precheck-placement-condition-exp8', placement_title)
study_panels = [('Traffic as-is (exp. 5)', members('placement', lambda s: s['study'] == 'exp5' and s['condition'].startswith('as-is'))),
                ('Traffic matched (exp. 5)', members('placement', lambda s: s['study'] == 'exp5' and s['condition'].startswith('matched'))),
                ('Load level (exp. 6)', members('placement', lambda s: s['study'] == 'exp6')),
                ('Task-U imbalance (exp. 7)', members('placement', lambda s: s['study'] == 'exp7')),
                ('Working set (exp. 8)', members('placement', lambda s: s['study'] == 'exp8'))]
figure('placement', 'set', study_panels, 'precheck-placement-set',
       'Partitioned grouped vs mixed: choice by RF on unseen task sets, workload O2')
for decision, what in (('hl-policy', 'Partitioned informed vs WFD'),
                       ('hl-family', 'best Partitioned vs best Clustered vs Global')):
    for heaviness in ('light', 'heavy'):
        panels = condition_panels(decision, 'exp9', heavy_load, lambda c, h=heaviness: c.startswith(h))
        figure(decision, 'condition', panels, f'precheck-{decision}-condition-{heaviness}',
               f'{what}: choice by RF trained without this cell, 16 L1-resident tasks, workload O0')
