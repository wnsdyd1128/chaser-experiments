"""Paper-style grouped bars: G/C/C2 gap vs P for TAT and TET by period CV (v2 main run)."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

O = Path(__file__).resolve().parents[4] / '.cache/period-distribution-v2'
import sys
# Primary analysis keeps every random draw (n = 20); --dedup merges identical task sets.
DEDUP = '--dedup' in sys.argv
SUFFIX = '-dedup' if DEDUP else ''
RESULTS = 'results-dedup.jsonl' if DEDUP else 'results.jsonl'
STATS = 'stats-dedup.json' if DEDUP else 'stats.json'
rows = [json.loads(l) for l in open(O / RESULTS)]
stats = json.load(open(O / STATS))
CVS = (0.0, 0.1, 0.2, 0.3)
SERIES = (('g', 'Global', '#2a78d6', ''), ('c', 'Clustered (1+3)', '#eb6834', '//'), ('c2', 'Clustered (1+1+2)', '#4a3aa7', '..'))
METRICS = (('tat_ns', '(a) TAT'), ('tet_ns', '(b) TET'))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 11,
                     'hatch.linewidth': 0.8, 'axes.linewidth': 1.0})

def gaps(metric, arch, cv):
    return [r[arch][metric] / r['p'][metric] - 1 for r in rows
            if r['cv'] == cv and all(r[a]['status'] == 'ok' for a in ('g', 'c', 'p', 'c2'))]

def significant_everywhere(metric, pair, cv):
    cells = [e for e in stats['cells'] if e['metric'] == metric and e['pair'] == pair and e['cv'] == cv]
    return bool(cells) and all(e.get('significant') for e in cells)

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), dpi=200)
width, x = 0.24, np.arange(len(CVS))
table = []
for ax, (metric, title) in zip(axes, METRICS):
    for k, (arch, label, color, hatch) in enumerate(SERIES):
        med, lo, hi = [], [], []
        for cv in CVS:
            v = np.array(gaps(metric, arch, cv)) * 100
            q1, m, q3 = np.percentile(v, [25, 50, 75])
            med.append(m); lo.append(m - q1); hi.append(q3 - m)
            table.append((title, label, cv, len(v), m, q1, q3, significant_everywhere(metric, f'{arch}-p', cv)))
        pos = x + (k - 1) * width
        bars = ax.bar(pos, med, width, color=color, edgecolor='black', linewidth=0.9, hatch=hatch, zorder=3)
        ax.errorbar(pos, med, yerr=[lo, hi], fmt='none', ecolor='black', elinewidth=0.9, capsize=2.5, zorder=4)
        span = np.ptp(ax.get_ylim()) if ax.has_data() else 1
        for p, m, l, h, cv in zip(pos, med, lo, hi, CVS):
            star = '*' if significant_everywhere(metric, f'{arch}-p', cv) else ''
            text = f'{m:+.2f}{star}'
            y, va = (m + h, 'bottom') if m >= 0 else (m - l, 'top')
            ax.annotate(text, (p, y), xytext=(0, 3 if m >= 0 else -3), textcoords='offset points',
                        ha='center', va=va, rotation=90, fontsize=8)
    ax.axhline(0, color='black', linewidth=1.0, zorder=5)
    ax.set_xticks(x, [f'{cv:g}' for cv in CVS])
    ax.set_xlabel('Period coefficient of variation (CV = σ/μ)')
    ax.set_title(title, loc='left', fontsize=12)
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.text(0.02, 0.04, 'Lower is better ↓', transform=ax.transAxes, fontsize=10)
axes[0].set_ylabel('Relative difference vs. Partitioned (%)')
axes[0].set_ylim(-25.5, 4)
axes[1].set_ylim(-0.05, 0.26)
handles = [Patch(facecolor=c, edgecolor='black', hatch=h, label=l) for _, l, c, h in SERIES]
fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0), fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.93))
for ext in ('png', 'pdf'):
    fig.savefig(O / f'figures/v2-gap-bars{SUFFIX}.{ext}', bbox_inches='tight')
with open(O / f'figures/v2-gap-bars{SUFFIX}.csv', 'w') as f:
    f.write('panel,series,cv,n,median_pct,q1_pct,q3_pct,significant_all_mu\n')
    for t in table:
        f.write(','.join(str(v) if not isinstance(v, float) else f'{v:.4f}' for v in t) + '\n')
for t in table: print(t[0], t[1], t[2], f'n={t[3]} median={t[4]:+.2f} IQR=[{t[5]:+.2f},{t[6]:+.2f}] sig_all={t[7]}')
