"""PCA scatter of v2 task sets colored by the best-TAT architecture (0=G, 1=C, 2=P)."""
import csv, glob, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

O = Path(__file__).resolve().parents[4] / '.cache/period-distribution-v2'
import sys
# Primary analysis keeps every random draw (n = 20); --dedup merges identical task sets.
DEDUP = '--dedup' in sys.argv
SUFFIX = '-dedup' if DEDUP else ''
RESULTS = 'results-dedup.jsonl' if DEDUP else 'results.jsonl'
STATS = 'stats-dedup.json' if DEDUP else 'stats.json'
NAMES = ('G', 'C', 'P')
COLORS = ('#2a78d6', '#eb6834', '#1baf7a')   # reference categorical slots 1-3
KEEP = {(r['mean'], r['cv'], r['set_id']) for r in map(json.loads, open(O / RESULTS))} if DEDUP else None
rows = []
for d in sorted(glob.glob(str(O / 'm*/cv*/s*'))):
    recs = []
    for a in 'gcp':
        try:
            recs.append(json.loads(open(f'{d}/{a}/measurements.jsonl').read().splitlines()[0]))
        except Exception:
            break
    if len(recs) < 3 or any(r['execution_status'] != 'ok' for r in recs):
        continue
    cfg = json.load(open(f'{d}/configuration.json'))
    mean, cv = cfg['period_distribution']['mean_ticks'], cfg['period_distribution']['cv']
    if KEEP is not None and (mean, cv, cfg['period_distribution']['set_id']) not in KEEP:
        continue
    tat = [r['tat_ns'] for r in recs]
    order = sorted(range(3), key=lambda i: tat[i])
    rows.append(dict(cell=f'mu{mean}/cv{cv}', mean=mean, cv=cv, set_id=cfg['period_distribution']['set_id'],
                     periods=sorted(t['period_ticks'] for t in cfg['tasks']), tat_g=tat[0], tat_c=tat[1], tat_p=tat[2],
                     best=order[0], margin=tat[order[1]] / tat[order[0]] - 1))
X = np.array([[p / r['mean'] for p in r['periods']] for r in rows])
Z = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)
U, S, Vt = np.linalg.svd(Z, full_matrices=False)
pc = Z @ Vt[:2].T
explained = S[:2] ** 2 / (S ** 2).sum()

MEANS = sorted({r['mean'] for r in rows})
fig, axes = plt.subplots(1, len(MEANS), figsize=(22, 5.4), dpi=150, sharex=True, sharey=True)
fig.patch.set_facecolor('#fcfcfb')
for ax, mean in zip(axes, MEANS):
    ax.set_facecolor('#fcfcfb')
    members = [(xy, r) for xy, r in zip(pc, rows) if r['mean'] == mean]
    for (x, y), r in members:
        color = COLORS[r['best']]
        filled = r['margin'] >= 0.01
        if r['set_id'] == 0:
            ax.scatter(x, y, s=150, facecolors='none', edgecolors='#0b0b0b', linewidths=1.6, zorder=2)
        ax.scatter(x, y, s=48, facecolors=color if filled else 'none', edgecolors=color,
                   linewidths=1.8, alpha=0.9, zorder=3)
    c = Counter(r['best'] for _, r in members)
    ax.set_title(f'μ = {mean} ms  (n={len(members)}: G {c[0]}, C {c[1]}, P {c[2]})', color='#0b0b0b', loc='left', fontsize=11)
    ax.set_xlabel(f'PC1 ({explained[0]:.0%} of variance)', color='#52514e')
    ax.grid(color='#e4e3df', linewidth=0.6, zorder=0)
    for sp in ax.spines.values(): sp.set_color('#c3c2b7')
    ax.tick_params(colors='#52514e')
axes[0].set_ylabel(f'PC2 ({explained[1]:.0%} of variance)', color='#52514e')
counts = Counter(r['best'] for r in rows)
handles = [Line2D([], [], marker='o', ls='', color=COLORS[i], markersize=8, label=f'{i} = {NAMES[i]}  (n={counts[i]})') for i in range(3)]
handles += [Line2D([], [], marker='o', ls='', markerfacecolor='none', markeredgecolor='#52514e', markersize=8, label='hollow: best−2nd TAT margin < 1%'),
            Line2D([], [], marker='o', ls='', markerfacecolor='none', markeredgecolor='#0b0b0b', markeredgewidth=1.6, markersize=12, label='outer black ring: pilot (set 0)')]
fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, fontsize=9.5, labelcolor='#0b0b0b', bbox_to_anchor=(0.5, 1.0))
fig.suptitle(f'v2 task sets (n={len(rows)}): best architecture by TAT', x=0.01, y=0.93, ha='left', color='#0b0b0b', fontsize=13)
fig.text(0.01, 0.01, 'Features: 16 sorted periods / μ (standardized, PCA; axes shared). CV ∈ {0, 0.1, 0.2, 0.3}; colors: best TAT among G/C/P per task set (C2 not colored).',
         fontsize=8.5, color='#52514e')
fig.tight_layout(rect=(0, 0.03, 1, 0.9))
fig.savefig(O / f'figures/v2-best-tat-pca{SUFFIX}.png', facecolor=fig.get_facecolor())
with open(O / f'figures/v2-best-tat-pca{SUFFIX}.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['cell', 'set_id', 'pc1', 'pc2', 'best', 'best_name', 'margin', 'tat_g_ns', 'tat_c_ns', 'tat_p_ns'])
    for (x, y), r in zip(pc, rows):
        w.writerow([r['cell'], r['set_id'], f'{x:.4f}', f'{y:.4f}', r['best'], NAMES[r['best']], f'{r["margin"]:.5f}', r['tat_g'], r['tat_c'], r['tat_p']])
print('explained', explained.round(3), 'counts', dict(counts))
per_cell = {}
for r in rows:
    per_cell.setdefault(r['cell'], Counter())[NAMES[r['best']] + ('~' if r['margin'] < 0.01 else '')] += 1
for k, v in sorted(per_cell.items(), key=lambda kv: (int(kv[0].split('/')[0][2:]), kv[0])): print(k, dict(v))
print('PC1 loadings (top):', sorted(zip(np.abs(Vt[0]).round(2), [f'p{i}' for i in range(16)] + ['log_mu']), reverse=True)[:4])
print('PC2 loadings (top):', sorted(zip(np.abs(Vt[1]).round(2), [f'p{i}' for i in range(16)] + ['log_mu']), reverse=True)[:4])
