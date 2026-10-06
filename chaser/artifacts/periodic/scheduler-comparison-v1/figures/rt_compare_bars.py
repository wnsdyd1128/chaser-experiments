"""Paper-style bars for rt_compare.py: deadlines and worst execution inflation per placement, per study.

Files in <rt-compare dir>/figures, one per study (rt-compare-<study number>):
  left   runs meeting every deadline, % of runs that met or missed (each random draw is a run)
  middle deadline-violating jobs (late or lost to postponed releases), % of released jobs over those runs
  right  median worst memory-task job CPU / planned budget over the cases where every placement
         and random draw met every deadline
Usage: python3 rt_compare_bars.py <rt-compare dir>
"""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path(sys.argv[1]).resolve()
result = json.loads((O / 'rt-compare.json').read_text())
STYLE = dict(
    wfd=('Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
    ra=('Partitioned (release-aware)', '#1baf7a', '\\\\'),
    tg=('Partitioned (traffic grouping, packed)', '#b2df8a', 'xx'),
    **{'ra-tg': ('Partitioned (release-aware within traffic grouping)', '#33a02c', '//')},
    cg=('Partitioned (CLS grouping, packed)', '#cab2d6', 'oo'),
    **{'ra-cg': ('Partitioned (release-aware within packed CLS grouping)', '#6a3d9a', '++')},
    cgb=('Partitioned (balanced CLS grouping)', '#9e9ac8', 'oo'),
    **{'ra-cgb': ('Partitioned (release-aware within balanced CLS grouping)', '#c51b7d', '++')},
    cgr=('Partitioned (balanced CLS grouping, lower-CLS half)', '#fdb863', 'xx'),
    **{'ra-cgr': ('Partitioned (release-aware within lower-CLS-half grouping)', '#e66101', '//')},
    random=('Partitioned (random, 3 draws per set)', '#bdbdbd', '..'))
ORDER = ('wfd', 'ra', 'tg', 'ra-tg', 'cg', 'ra-cg', 'cgb', 'ra-cgb', 'cgr', 'ra-cgr', 'random')
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)

for name, study in result.items():
    rows = study['placements']
    keys = [k for k in ORDER if k in rows]
    fig, (left, middle, right) = plt.subplots(1, 3, figsize=(6.0 + 0.55 * len(keys) * 3, 5.0), dpi=200)
    table = []
    for k, key in enumerate(keys):
        label, color, hatch = STYLE[key]
        r = rows[key]
        share = 100 * r['met'] / r['runs'] if r['runs'] else 0
        left.bar(k, share, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        left.annotate(f"{share:.0f}%\n{r['met']}/{r['runs']}", (k, share), xytext=(0, 2), textcoords='offset points',
                      ha='center', va='bottom', fontsize=7)
        violated = 100 * r['missed_jobs'] / r['expected_jobs'] if r['expected_jobs'] else 0
        middle.bar(k, violated, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
        middle.annotate(f'{violated:.2f}%', (k, violated), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize=7)
        if r['inflation'] is not None:
            right.bar(k, r['inflation'], 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
            right.annotate(f"{r['inflation']:.2f}x", (k, r['inflation']), xytext=(0, 2), textcoords='offset points',
                           ha='center', va='bottom', fontsize=7)
        table.append((key, r['runs'], r['met'], r['missed_jobs'], r['expected_jobs'], r['inflation'], r['response']))
    left.set_ylim(0, 125)
    left.set_ylabel('Runs meeting every deadline (%)')
    left.set_title(f"Deadlines ({study['cases']} sets)", loc='left', fontsize=9.5)
    left.text(0.02, 0.97, 'Higher is better ↑', transform=left.transAxes, fontsize=8, va='top')
    worst = max(100 * rows[k]['missed_jobs'] / rows[k]['expected_jobs'] for k in keys if rows[k]['expected_jobs'])
    middle.set_ylim(0, max(worst * 1.3, 1))
    middle.set_ylabel('Deadline-violating jobs (% of released)')
    middle.set_title('Violated jobs (late or lost)', loc='left', fontsize=9.5)
    middle.text(0.02, 0.97, 'Lower is better ↓', transform=middle.transAxes, fontsize=8, va='top')
    top = max((rows[k]['inflation'] or 0) for k in keys)
    right.set_ylim(0, top * 1.25 if top else 1)
    right.set_ylabel('Worst memory-task job CPU / isolated budget')
    right.set_title(f"Worst execution ({study['common_cases']} sets where every run met every deadline)", loc='left',
                    fontsize=9.5)
    right.text(0.02, 0.97, 'Lower is better ↓', transform=right.transAxes, fontsize=8, va='top')
    for ax in (left, middle, right):
        ax.set_xticks([])
        ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    handles = [Patch(facecolor=STYLE[k][1], edgecolor='black', hatch=STYLE[k][2], label=STYLE[k][0]) for k in keys]
    rows_of_legend = -(-len(keys) // 2)
    fig.legend(handles=handles, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.95), fontsize=8.5)
    fig.suptitle(f'Experiment {name}', x=0.01, ha='left', y=0.995, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93 - 0.055 * rows_of_legend))
    stem = f"rt-compare-{name.split()[0]}"
    for ext in ('png', 'pdf'):
        fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
    with open(O / f'figures/{stem}.csv', 'w') as f:
        f.write('placement,runs,met_every_deadline,violated_jobs,released_jobs,median_worst_memory_inflation,'
                'median_worst_response_ratio\n')
        for t in table:
            f.write(','.join('' if v is None else f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
    plt.close(fig)
    print('wrote', stem)
