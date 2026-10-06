"""Paper-style bars for the CLS spread run: measured TAT / TET per configuration.

Files in <run dir>/figures: cls-spread-{tat,tet}-cls{30,60,90}-cv{00,20}; panels = CLS SD
(0, 0.1, 0.2); bars = G, C2 (1+1+2) and the six Partitioned placements; median over the sets
where that configuration ran without a deadline miss, whiskers IQR; labels count deadline
misses and startup failures (excluded).
Usage: python3 cls_spread_bars.py <run output dir>
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
    r.update(protocol['cells'][r['heaviness']])
SERIES = (('g', 'Global', '#2a78d6', ''), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'),
          ('p', 'Partitioned (U-balanced, WFD)', '#8c6d31', '--'),
          ('p_ra', 'Partitioned (release-aware)', '#1baf7a', '\\\\'),
          ('p_cgb', 'Partitioned (balanced CLS grouping, CLS <= 0.5)', '#9e9ac8', 'oo'),
          ('p_racgb', 'Partitioned (release-aware within CLS <= 0.5 grouping)', '#c51b7d', '++'),
          ('p_cgr', 'Partitioned (balanced CLS grouping, lower-CLS half)', '#fdb863', 'xx'),
          ('p_racgr', 'Partitioned (release-aware within lower-CLS-half grouping)', '#e66101', '//'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 10,
                     'hatch.linewidth': 0.7, 'axes.linewidth': 1.0})
(O / 'figures').mkdir(exist_ok=True)
state = lambda r, k: r[k].get('state')


def fmt(v):
    return f'{v:.1f}' if v < 1000 else f'{v:.0f}'


for metric, label in (('tat_ns', 'TAT'), ('tet_ns', 'TET')):
    for mean in sorted({r['cls_mean'] for r in rows}):
        for cv in sorted({r['period_cv'] for r in rows}):
            sds = sorted({r['cls_sd'] for r in rows})
            fig, axes = plt.subplots(1, len(sds), figsize=(5.2 * len(sds) + 1, 5.0), dpi=200)
            table = []
            for ax, sd in zip(axes, sds):
                members = [r for r in rows if (r['cls_mean'], r['cls_sd'], r['period_cv']) == (mean, sd, cv)]
                top = 0
                for k, (key, _, color, hatch) in enumerate(SERIES):
                    v = np.array([r[key][metric] / 1e6 for r in members if state(r, key) == 'ok'])
                    misses = sum(state(r, key) == 'deadline' for r in members)
                    excluded = sum(state(r, key) in ('startup', 'other') for r in members)
                    note = ''.join(f'\n{n} {w}' for n, w in ((misses, 'miss'), (excluded, 'excl.')) if n)
                    if len(v):
                        q1, m, q3 = np.percentile(v, [25, 50, 75])
                        top = max(top, q3)
                        ax.bar(k, m, 0.78, color=color, edgecolor='black', linewidth=0.7, hatch=hatch, zorder=3)
                        ax.errorbar(k, m, yerr=[[m - q1], [q3 - m]], fmt='none', ecolor='black', elinewidth=0.8,
                                    capsize=2, zorder=4)
                        ax.annotate(fmt(m) + note, (k, q3), xytext=(0, 2), textcoords='offset points', ha='center',
                                    va='bottom', fontsize=6.5)
                        table.append((sd, key, len(v), m, q1, q3, misses, excluded))
                    else:
                        ax.annotate(note.strip(), (k, 0), xytext=(0, 2), textcoords='offset points', ha='center',
                                    va='bottom', fontsize=6.5)
                        table.append((sd, key, 0, float('nan'), float('nan'), float('nan'), misses, excluded))
                ax.set_ylim(0, top * 1.25 if top else 1)
                ax.set_xticks([])
                ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
                ax.set_title(f'CLS SD {sd} ({len(members)} sets)', loc='left', fontsize=9.5)
                ax.text(0.02, 0.97, 'Lower is better ↓', transform=ax.transAxes, fontsize=8, va='top')
            axes[0].set_ylabel(f'Measured {label} (ms)')
            handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
            fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.55, 0.97),
                       fontsize=8.5)
            fig.suptitle(f'{label}: CLS mean {mean}, period CV {cv}, 12-20 tasks, per-core U 0.4, workload O2',
                         x=0.01, ha='left', y=0.995, fontsize=10.5)
            fig.tight_layout(rect=(0, 0, 1, 0.82))
            stem = f'cls-spread-{label.lower()}-cls{round(mean * 100):02d}-cv{round(cv * 100):02d}'
            for ext in ('png', 'pdf'):
                fig.savefig(O / f'figures/{stem}.{ext}', bbox_inches='tight')
            with open(O / f'figures/{stem}.csv', 'w') as f:
                f.write('cls_sd,configuration,n,median_ms,q1_ms,q3_ms,deadline_misses,excluded\n')
                for t in table:
                    f.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in t) + '\n')
            plt.close(fig)
            print('wrote', stem)
