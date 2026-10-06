"""Paper-style bars for the small-memory run: measured TAT / TET per configuration.

Files in <run dir>/figures:
  small-memory-{tat,tet}-low{00,25,50}   panels = period CV; bars = G, C2 (1+1+2) and the
        four Partitioned placements; median over the sets where that configuration ran
        without a deadline miss, whiskers IQR; labels count deadline misses and startup
        failures (excluded)
  small-memory-{tat,tet}-low{25,50}-tasks-cv{00,pos}   the same bars with panels = task-count
        group (12-14, 15-17, 18-20), period CV 0 or CV 0.1-0.3 pooled
Usage: python3 small_memory_bars.py <run output dir>
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
for r in rows:
    r.update(protocol['cells'][r['heaviness']], tasks=protocol['task_counts'][r['set_id']])
SERIES = (('g', 'Global', '#2a78d6', ''), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('p', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
          ('p_cgb', 'Partitioned (balanced CLS grouping)', '#9e9ac8', 'oo'),
          ('p_ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
          ('p_racgb', 'Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', '++'))
GROUPS = (('12-14 tasks', range(12, 15)), ('15-17 tasks', range(15, 18)), ('18-20 tasks', range(18, 21)))
CVS = sorted({r['period_cv'] for r in rows})
SHARES = sorted({r['low_share'] for r in rows})
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)
state = lambda r, k: r[k].get('state')


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


def panel(ax, members, metric, title):
    table, top = [], 0
    for k, (key, _, color, hatch) in enumerate(SERIES):
        v = np.array([r[key][metric] / 1e6 for r in members if state(r, key) == 'ok'])
        misses = sum(state(r, key) == 'deadline' for r in members)
        excluded = sum(state(r, key) in ('startup', 'other') for r in members)
        note = ''.join(f'\n{n} {word}' for n, word in ((misses, 'miss'), (excluded, 'excl.')) if n)
        if len(v):
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            top = max(top, q3)
            ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8, capsize=2, zorder=4)
            ax.annotate(fmt(m) + note, (k, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize=7)
            table.append((title, key, len(v), m, q1, q3, misses, excluded))
        else:
            table.append((title, key, 0, float('nan'), float('nan'), float('nan'), misses, excluded))
    ax.set_ylim(0, top * 1.25 if top else 1)
    ax.set_xticks([])
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_title(f'{title} ({len(members)} sets)', loc='left', fontsize=9.5)
    ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
    return table


def figure(panels, metric, label, title, stem):
    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels) + 1, 5.0), dpi=200)
    table = [t for ax, (name, members) in zip(axes, panels) for t in panel(ax, members, metric, name)]
    axes[0].set_ylabel(f'Measured {label} (ms)')
    handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
    fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.55, 0.96), fontsize=9)
    fig.suptitle(title, x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('panel,configuration,n,median_ms,q1_ms,q3_ms,deadline_misses,excluded\n')
        for t in table:
            f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)


for metric, label in (('tat_ns', 'TAT'), ('tet_ns', 'TET')):
    for share in SHARES:
        members = [r for r in rows if r['low_share'] == share]
        what = f'32 KiB low-CLS tasks hold {share:.0%} of U' if share else 'no low-CLS tasks'
        figure([(f'Period CV {cv}', [r for r in members if r['period_cv'] == cv]) for cv in CVS], metric, label,
               f'{label}: {what}, 12-20 tasks, per-core U 0.4, periods around 40 ms, workload O2',
               f'small-memory-{label.lower()}-low{round(share * 100):02d}')
        if not share:
            continue
        for scope, stem, keep in (('period CV 0', 'cv00', lambda r: r['period_cv'] == 0),
                                  ('period CV 0.1-0.3 pooled', 'cvpos', lambda r: r['period_cv'] > 0)):
            figure([(group, [r for r in members if keep(r) and r['tasks'] in values]) for group, values in GROUPS],
                   metric, label, f'{label}: {what}, {scope}, per-core U 0.4, workload O2',
                   f'small-memory-{label.lower()}-low{round(share * 100):02d}-tasks-{stem}')
