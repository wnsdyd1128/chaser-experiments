"""Analyze the small-memory run: where do CLS-aware placements beat release-aware placement?

Reads <output>/results.jsonl, protocol.json (task count per set) and, for the selector, each
case's wfd configuration and locality.json. A run that failed at startup (state startup or
other: nothing measured) is missing, not infeasible; only deadline misses count against
feasibility. Writes small-memory-analysis.json/md:
  states      ok / deadline miss / excluded runs per cell and configuration
  cells       per cell (period CV x low-CLS share) and metric: median, mean regret against
              the best Partitioned placement of the case, wins
  contrasts   cgb and ra-cgb against ra per low-CLS cell, per period CV (low-CLS cells
              pooled) and per low-CLS share (CV > 0 pooled); in the cells without low-CLS
              tasks, ra against wfd (experiments 1-2): paired relative difference, wins /
              ties / losses, Wilcoxon (zeros dropped), deadline-miss discordance
  task_count  the CLS contrasts per task-count group and multiple-of-4 split, separately for
              period CV 0 and CV > 0 (low-CLS cells), and ra against wfd per group in the
              CV > 0 cells without low-CLS tasks; G and C2 against the best Partitioned
              placement per group
  selector    the feature pre-check RF per metric (set-level and cell-level CV)
Holm runs over every Wilcoxon test in contrasts and task_count.
Usage: python3 smallmem_analysis.py --output <run output dir> [--jobs N]
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'feature-precheck'))

from boundary_analysis import KEYS, NAMES, best, paired, placement_summary, value
from pm_analysis import holm, pct
from smallmem_set import cell
from taskcount_analysis import CORES, GROUPS, selector

METRICS = ('tat_ns', 'tet_ns')
CONFIGS = ('g', 'c2') + KEYS
CLS_PAIRS = (('p_cgb', 'p_ra'), ('p_racgb', 'p_ra'))
EXCLUDED = ('startup', 'other')
ALPHA = 0.05


def state(row, key) -> str:
    return row[key].get('state')


def discordance(rows, a, b):
    """Cases where one of the two met every deadline and the other missed one."""
    return dict(only_a=sum(state(r, a) == 'ok' and state(r, b) == 'deadline' for r in rows),
                only_b=sum(state(r, b) == 'ok' and state(r, a) == 'deadline' for r in rows))


def contrasts(rows, pairs, label):
    return [dict(paired(rows, a, b, metric, label), deadline=discordance(rows, a, b))
            for a, b in pairs for metric in METRICS]


def against_partitioned(rows):
    out = {}
    for arch in ('g', 'c2'):
        entry = dict(ok=sum(state(r, arch) == 'ok' for r in rows),
                     deadline=sum(state(r, arch) == 'deadline' for r in rows), cases=len(rows))
        for metric in METRICS:
            gaps = [value(r, arch, metric) / best(r, metric) - 1 for r in rows
                    if np.isfinite(best(r, metric)) and state(r, arch) == 'ok']
            label = metric.split('_')[0]
            entry[f'{label}_beats_best_partitioned'] = sum(g < 0 for g in gaps)
            entry[f'{label}_median_gap'] = float(np.median(gaps)) if gaps else None
        out[arch] = entry
    return out


def markdown(result) -> str:
    lines = ['# Small-memory analysis', '',
             'Regret: value / best Partitioned placement of the same case - 1. Startup failures are excluded,',
             'not counted as infeasible.', '', '## Runs: ok / deadline miss / excluded', '',
             '| cell | ' + ' | '.join(CONFIGS) + ' |', '|---|' + '---|' * len(CONFIGS)]
    for name, e in result['states'].items():
        lines.append(f'| {name} | ' + ' | '.join(f"{e[k]['ok']} / {e[k]['deadline']} / {e[k]['excluded']}"
                                                 for k in CONFIGS) + ' |')
    for metric in METRICS:
        label = metric.split('_')[0].upper()
        lines += ['', f'## {label} per cell', '', '| cell | ' + ' | '.join(f'{n} median / regret / wins'
                                                                         for n in NAMES.values()) + ' |',
                  '|---|' + '---|' * len(NAMES)]
        for name, e in result['cells'].items():
            s = e[metric]
            lines.append(f'| {name} | ' + ' | '.join(
                f"{s[n]['median_ms']:.1f} / {pct(s[n]['mean_regret'])} / {s[n]['wins']}" if s[n]['median_ms'] else '-'
                for n in NAMES.values()) + ' |')
    lines += ['', '## Paired contrasts', '',
              '| scope | metric | pair | n | better / tie / worse | median | Holm p | only first / only second meets deadlines |',
              '|---|---|---|---:|---|---:|---:|---|']
    for e in result['contrasts'] + result['task_count']['contrasts']:
        p = f"{e['holm_p']:.3g}" if 'holm_p' in e else '-'
        lines.append(f"| {e['test']} | {e['metric']} | {e['pair']} | {e['n']} | {e['wins']} / {e['ties']} / {e['losses']} "
                     f"| {pct(e['median'])} | {p} | {e['deadline']['only_a']} / {e['deadline']['only_b']} |")
    lines += ['', '## G and C2 against the best Partitioned placement', '',
              '| scope | cases | G ok / beats best P (TAT, TET) / median TAT gap | C2 ok / beats best P (TAT, TET) / median TAT gap |',
              '|---|---:|---|---|']
    for scope, e in result['task_count']['groups'].items():
        cols = [f"{a['ok']} / {a['tat_beats_best_partitioned']}, {a['tet_beats_best_partitioned']} / {pct(a['tat_median_gap'])}"
                for a in (e['g'], e['c2'])]
        lines.append(f"| {scope} | {e['g']['cases']} | {cols[0]} | {cols[1]} |")
    for metric, sel in result['selector'].items():
        lines += ['', f"## Placement selector ({metric.split('_')[0].upper()} labels)", '',
                  f"{sel['cases']} cases; labels {sel['labels']}; near-ties {sel['near_ties']}", '']
        for scheme, methods in sel['results'].items():
            lines += [f'### {scheme}-level cross-validation', '', '| method | mean regret | p95 | max | accuracy |',
                      '|---|---:|---:|---:|---:|']
            for name, m in methods.items():
                if name.startswith(('oracle', 'always', 'fixed')) or name.endswith(('classifier', 'regressor')):
                    lines.append(f"| {name} | {pct(m['mean_regret'])} | {pct(m['p95_regret'])} | {pct(m['max_regret'])} "
                                 f"| {pct(m['accuracy'])} |")
            lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    protocol = json.loads((output / 'protocol.json').read_text())
    for r in rows:
        r['tasks'] = protocol['task_counts'][r['set_id']]
        r.update(cell(r['heaviness']))
    cells = list(protocol['cells'])
    in_cell = lambda h: [r for r in rows if r['heaviness'] == h]
    low = [r for r in rows if r['low_share'] > 0]
    cvs, shares = sorted({r['period_cv'] for r in rows}), sorted({r['low_share'] for r in low})
    tests = [e for h in cells if cell(h)['low_share'] > 0 for e in contrasts(in_cell(h), CLS_PAIRS, h)]
    tests += [e for cv in cvs for e in contrasts([r for r in low if r['period_cv'] == cv], CLS_PAIRS,
                                                 f'CV {cv}, low-CLS cells')]
    tests += [e for s in shares for e in contrasts([r for r in low if r['low_share'] == s and r['period_cv'] > 0],
                                                   CLS_PAIRS, f'low {s:.0%}, CV > 0')]
    tests += [e for cv in cvs for e in contrasts([r for r in rows if r['low_share'] == 0 and r['period_cv'] == cv],
                                                 (('p_ra', 'p'),), f'CV {cv}, no low-CLS tasks')]
    scopes = [(label, lambda r, v=values: r['tasks'] in v) for label, values in GROUPS]
    scopes += [('multiple of 4', lambda r: r['tasks'] % CORES == 0),
               ('not a multiple of 4', lambda r: r['tasks'] % CORES != 0)]
    group_tests = [e for cv_label, cv_rows in (('CV 0', [r for r in low if r['period_cv'] == 0]),
                                               ('CV > 0', [r for r in low if r['period_cv'] > 0]))
                   for label, member in scopes
                   for e in contrasts([r for r in cv_rows if member(r)], CLS_PAIRS, f'{cv_label}, {label} tasks')]
    no_low = [r for r in rows if r['low_share'] == 0 and r['period_cv'] > 0]
    group_tests += [e for label, member in scopes for e in contrasts([r for r in no_low if member(r)], (('p_ra', 'p'),),
                                                                  f'CV > 0, no low-CLS tasks, {label} tasks')]
    tested = [e for e in tests + group_tests if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    result = dict(
        cases=len(rows),
        states={h: {k: dict(ok=sum(state(r, k) == 'ok' for r in in_cell(h)),
                            deadline=sum(state(r, k) == 'deadline' for r in in_cell(h)),
                            excluded=sum(state(r, k) in EXCLUDED for r in in_cell(h))) for k in CONFIGS}
                for h in cells},
        cells={h: {m: placement_summary(in_cell(h), m) for m in METRICS} for h in cells},
        contrasts=tests,
        task_count=dict(contrasts=group_tests,
                        groups={label: against_partitioned([r for r in rows if member(r)]) for label, member in scopes}),
        selector={m: selector(output, rows, m, args.jobs) for m in METRICS})
    # Counts summed from numpy booleans are numpy integers.
    (output / 'small-memory-analysis.json').write_text(json.dumps(result, indent=1, default=lambda o: o.item()) + '\n')
    (output / 'small-memory-analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), output / 'smallmem_analysis.py')
    print('wrote', output / 'small-memory-analysis.md')


if __name__ == '__main__':
    main()
