"""Analyze the task-count run: does CLS-aware placement win under memory pressure, at every task count?

Reads <output>/results.jsonl, protocol.json (task count per set) and each case's wfd
configuration and locality.json. Partitioned placements wfd, cgb, ra, ra-cgb; G and C2
(1+1+2) on wfd. A run with a deadline miss is infeasible. Writes task-count-analysis.json/md:
  schedulable   runs meeting every deadline per cell (memory share x load) and configuration
  cells         per cell and metric (TAT, TET): median, mean regret against the best
                Partitioned placement of the case, wins
  cls_vs_ra     cgb and ra-cgb against ra per cell: paired relative difference (both
                feasible), wins / ties / losses, Wilcoxon (zeros dropped) with Holm, and the
                feasibility discordance (only one of the two met every deadline)
  task_count    per task-count group (12-14, 15-17, 18-20) and for counts that are or are
                not multiples of the core count: the same contrasts, WFD's regret, and G and
                C2 against the best Partitioned placement
  selector      the feature pre-check RF per metric (set-level and cell-level CV)
Usage: python3 taskcount_analysis.py --output <run output dir> [--jobs N]
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

import precheck
from boundary_analysis import KEYS, NAMES, best, paired, placement_summary, value
from pm_analysis import feature_tasks, holm, pct

METRICS = ('tat_ns', 'tet_ns')
CONFIGS = ('g', 'c2') + KEYS
GROUPS = (('12-14', range(12, 15)), ('15-17', range(15, 18)), ('18-20', range(18, 21)))
CORES = 4
ALPHA = 0.05


def feasible(row, key) -> bool:
    return row[key].get('state') == 'ok'


def discordance(rows, a, b):
    return dict(only_a=sum(feasible(r, a) and not feasible(r, b) for r in rows),
                only_b=sum(feasible(r, b) and not feasible(r, a) for r in rows))


def contrasts(rows, label):
    out = []
    for a in ('p_cgb', 'p_racgb'):
        for metric in METRICS:
            out.append(dict(paired(rows, a, 'p_ra', metric, label), feasibility=discordance(rows, a, 'p_ra')))
    return out


def against_partitioned(rows):
    out = {}
    for arch in ('g', 'c2'):
        gaps = [value(r, arch, 'tat_ns') / best(r, 'tat_ns') - 1 for r in rows
                if np.isfinite(best(r, 'tat_ns')) and feasible(r, arch)]
        out[arch] = dict(feasible=sum(feasible(r, arch) for r in rows), cases=len(rows),
                         beats_best_partitioned=sum(g < 0 for g in gaps),
                         median_gap=float(np.median(gaps)) if gaps else None,
                         feasible_when_no_partitioned=sum(feasible(r, arch) and not np.isfinite(best(r, 'tat_ns'))
                                                          for r in rows))
    return out


def selector(output, rows, metric, jobs):
    precheck.OPTIONS['task-count'] = tuple(NAMES[k] for k in KEYS)
    other = 'tet_ns' if metric == 'tat_ns' else 'tat_ns'
    usable = [r for r in rows if np.isfinite(best(r, metric))]
    samples = [precheck.Sample('task-count', f"{r['heaviness']}/u{r['load']}", r['set_id'], dict(tasks=r['tasks']),
                               feature_tasks(output, r), tuple(value(r, k, metric) for k in KEYS),
                               tuple(value(r, k, other) for k in KEYS)) for r in usable]
    results, _ = precheck.evaluate('task-count', samples, jobs)
    return dict(cases=len(samples), labels={NAMES[k]: sum(s.label == i for s in samples) for i, k in enumerate(KEYS)},
                near_ties=sum(s.margin < precheck.MARGIN for s in samples),
                results={scheme: {n: v['mean'] for n, v in methods.items()} for scheme, methods in results.items()})


def markdown(result) -> str:
    lines = ['# Task-count analysis', '', 'Regret: value / best Partitioned placement of the same case - 1 (feasible runs).',
             '', '## Runs meeting every deadline', '', '| cell | cases | ' + ' | '.join(CONFIGS) + ' |',
             '|---|---:|' + '---:|' * len(CONFIGS)]
    for cell, e in result['schedulable'].items():
        lines.append(f"| {cell} | {e['cases']} | " + ' | '.join(str(e[k]) for k in CONFIGS) + ' |')
    for metric in METRICS:
        label = metric.split('_')[0].upper()
        lines += ['', f'## {label} per cell', '', '| cell | ' + ' | '.join(f'{n} median / regret / wins' for n in NAMES.values())
                  + ' |', '|---|' + '---|' * len(NAMES)]
        for cell, e in result['cells'].items():
            s = e[metric]
            lines.append(f'| {cell} | ' + ' | '.join(
                f"{s[n]['median_ms']:.1f} / {pct(s[n]['mean_regret'])} / {s[n]['wins']}" if s[n]['median_ms'] else '-'
                for n in NAMES.values()) + ' |')
    lines += ['', '## CLS-aware placements against release-aware (ra)', '',
              '| scope | metric | pair | n | better / tie / worse | median | Holm p | only CLS-aware / only ra feasible |',
              '|---|---|---|---:|---|---:|---:|---|']
    for e in result['cls_vs_ra'] + result['task_count']['cls_vs_ra']:
        p = f"{e['holm_p']:.3g}" if 'holm_p' in e else '-'
        lines.append(f"| {e['test']} | {e['metric']} | {e['pair']} | {e['n']} | {e['wins']} / {e['ties']} / {e['losses']} "
                     f"| {pct(e['median'])} | {p} | {e['feasibility']['only_a']} / {e['feasibility']['only_b']} |")
    lines += ['', '## Task count: WFD regret (TAT) and G / C2 against the best Partitioned placement', '',
              '| scope | cases | WFD mean regret | G feasible / beats best P / median gap | C2 feasible / beats best P / median gap |',
              '|---|---:|---:|---|---|']
    for scope, e in result['task_count']['groups'].items():
        g, c = e['architectures']['g'], e['architectures']['c2']
        lines.append(f"| {scope} | {e['cases']} | {pct(e['wfd_regret'])} | {g['feasible']} / {g['beats_best_partitioned']} / "
                     f"{pct(g['median_gap'])} | {c['feasible']} / {c['beats_best_partitioned']} / {pct(c['median_gap'])} |")
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
    counts = json.loads((output / 'protocol.json').read_text())['task_counts']
    for r in rows:
        r['tasks'] = counts[r['set_id']]
    cells = sorted({(r['heaviness'], r['load']) for r in rows})
    in_cell = lambda c: [r for r in rows if (r['heaviness'], r['load']) == c]
    name = lambda c: f'{c[0]} U{c[1]}'
    cls_vs_ra = [e for c in cells if c[0] != 'mem00' for e in contrasts(in_cell(c), name(c))]
    memory_rows = [r for r in rows if r['heaviness'] != 'mem00']
    scopes = [(label, [r for r in rows if r['tasks'] in values]) for label, values in GROUPS]
    scopes += [('multiple of 4', [r for r in rows if r['tasks'] % CORES == 0]),
               ('not a multiple of 4', [r for r in rows if r['tasks'] % CORES])]
    group_contrasts = [e for label, subset in scopes
                       for e in contrasts([r for r in subset if r['heaviness'] != 'mem00'], f'memory cells, {label} tasks')]
    tested = [e for e in cls_vs_ra + group_contrasts if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    result = dict(
        cases=len(rows),
        schedulable={name(c): dict(cases=len(in_cell(c)), **{k: sum(feasible(r, k) for r in in_cell(c)) for k in CONFIGS})
                     for c in cells},
        cells={name(c): {m: placement_summary(in_cell(c), m) for m in METRICS} for c in cells},
        cls_vs_ra=cls_vs_ra,
        task_count=dict(cls_vs_ra=group_contrasts, groups={
            label: dict(cases=len(subset), architectures=against_partitioned(subset),
                        wfd_regret=placement_summary(subset, 'tat_ns')['wfd']['mean_regret'])
            for label, subset in scopes}),
        memory_cases=len(memory_rows),
        selector={m: selector(output, rows, m, args.jobs) for m in METRICS})
    # Counts summed from numpy booleans are numpy integers.
    (output / 'task-count-analysis.json').write_text(json.dumps(result, indent=1, default=lambda o: o.item()) + '\n')
    (output / 'task-count-analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), output / 'taskcount_analysis.py')
    print('wrote', output / 'task-count-analysis.md')


if __name__ == '__main__':
    main()
