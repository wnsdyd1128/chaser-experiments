"""Analyze the CLS spread run: when CLS is continuous, which CLS-aware placement beats release-aware?

Reads <output>/results.jsonl, protocol.json (task count per set) and, for the selector, each
case's wfd configuration and locality.json. Partitioned placements: wfd, cgb, ra, ra-cgb
(absolute cut CLS <= 0.5) and cgr, ra-cgr (relative cut: the lower-CLS half of the U). A run
that failed at startup (state startup or other) is missing; only deadline misses count against
feasibility. Writes cls-spread-analysis.json/md:
  states      ok / deadline miss / excluded runs per cell and configuration
  cells       per cell (CLS mean x CLS SD x period CV) and metric: median, mean regret against
              the best Partitioned placement of the case, wins
  contrasts   per cell: the four CLS-aware placements against ra, and the relative against the
              absolute cut (cgr vs cgb, ra-cgr vs ra-cgb): paired relative difference, wins /
              ties / losses, Wilcoxon (zeros dropped), deadline-miss discordance
  task_count  ra-cgr and ra-cgb against ra per task-count group and multiple-of-4 split, in
              the cells with spread (SD > 0) at CLS mean 0.6 and 0.9, per period CV; G and C2
              against the best Partitioned placement per CLS mean
  selector    the feature pre-check RF per metric over the six placements
Holm runs over every Wilcoxon test in contrasts and task_count.
Usage: python3 clsspread_analysis.py --output <run output dir> [--jobs N]
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy import stats as scipy_stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'feature-precheck'))

import precheck
from clsspread_set import cell
from pm_analysis import feature_tasks, holm, pct

KEYS = ('p', 'p_cgb', 'p_ra', 'p_racgb', 'p_cgr', 'p_racgr')
NAMES = dict(p='wfd', p_cgb='cgb', p_ra='ra', p_racgb='ra-cgb', p_cgr='cgr', p_racgr='ra-cgr')
CONFIGS = ('g', 'c2') + KEYS
METRICS = ('tat_ns', 'tet_ns')
CLS_PAIRS = (('p_cgb', 'p_ra'), ('p_racgb', 'p_ra'), ('p_cgr', 'p_ra'), ('p_racgr', 'p_ra'),
             ('p_cgr', 'p_cgb'), ('p_racgr', 'p_racgb'))
GROUP_PAIRS = (('p_racgb', 'p_ra'), ('p_racgr', 'p_ra'))
GROUPS = (('12-14', range(12, 15)), ('15-17', range(15, 18)), ('18-20', range(18, 21)))
EXCLUDED = ('startup', 'other')
CORES = 4
ALPHA = 0.05


def state(row, key) -> str:
    return row[key].get('state')


def value(row, key, metric) -> float:
    return row[key][metric] if state(row, key) == 'ok' else float('inf')


def best(row, metric) -> float:
    return min(value(row, k, metric) for k in KEYS)


def placement_summary(rows, metric):
    out = {}
    for key in KEYS:
        regrets = [value(r, key, metric) / best(r, metric) - 1 for r in rows
                   if np.isfinite(best(r, metric)) and np.isfinite(value(r, key, metric))]
        ok = [value(r, key, metric) / 1e6 for r in rows if np.isfinite(value(r, key, metric))]
        out[NAMES[key]] = dict(median_ms=float(np.median(ok)) if ok else None,
                               mean_regret=float(np.mean(regrets)) if regrets else None,
                               wins=sum(np.isfinite(best(r, metric)) and value(r, key, metric) == best(r, metric)
                                        for r in rows))
    return out


def paired(rows, a, b, metric, name):
    d = [value(r, a, metric) / value(r, b, metric) - 1 for r in rows
         if np.isfinite(value(r, a, metric)) and np.isfinite(value(r, b, metric))]
    entry = dict(test=name, metric=metric.split('_')[0].upper(), pair=f'{NAMES[a]} vs {NAMES[b]}', n=len(d),
                 wins=sum(x < 0 for x in d), ties=sum(x == 0 for x in d), losses=sum(x > 0 for x in d),
                 median=float(np.median(d)) if d else None,
                 deadline=dict(only_a=sum(state(r, a) == 'ok' and state(r, b) == 'deadline' for r in rows),
                               only_b=sum(state(r, b) == 'ok' and state(r, a) == 'deadline' for r in rows)))
    nonzero = [x for x in d if x != 0]
    if len(nonzero) >= 6:
        entry['wilcoxon_p'] = float(scipy_stats.wilcoxon(nonzero).pvalue)
    return entry


def against_partitioned(rows):
    out = {}
    for arch in ('g', 'c2'):
        entry = dict(cases=len(rows), ok=sum(state(r, arch) == 'ok' for r in rows),
                     deadline=sum(state(r, arch) == 'deadline' for r in rows),
                     ok_when_no_partitioned=sum(state(r, arch) == 'ok' and not np.isfinite(best(r, 'tat_ns'))
                                                for r in rows))
        for metric in METRICS:
            gaps = [value(r, arch, metric) / best(r, metric) - 1 for r in rows
                    if np.isfinite(best(r, metric)) and state(r, arch) == 'ok']
            label = metric.split('_')[0]
            entry[f'{label}_beats_best_partitioned'] = sum(g < 0 for g in gaps)
            entry[f'{label}_median_gap'] = float(np.median(gaps)) if gaps else None
        out[arch] = entry
    return out


def selector(output, rows, metric, jobs):
    precheck.OPTIONS['cls-spread'] = tuple(NAMES[k] for k in KEYS)
    other = 'tet_ns' if metric == 'tat_ns' else 'tat_ns'
    usable = [r for r in rows if np.isfinite(best(r, metric))]
    samples = [precheck.Sample('cls-spread', r['heaviness'], r['set_id'], dict(tasks=r['tasks']),
                               feature_tasks(output, r), tuple(value(r, k, metric) for k in KEYS),
                               tuple(value(r, k, other) for k in KEYS)) for r in usable]
    results, _ = precheck.evaluate('cls-spread', samples, jobs)
    return dict(cases=len(samples), labels={NAMES[k]: sum(s.label == i for s in samples) for i, k in enumerate(KEYS)},
                near_ties=sum(s.margin < precheck.MARGIN for s in samples),
                results={scheme: {n: v['mean'] for n, v in methods.items()} for scheme, methods in results.items()})


def markdown(result) -> str:
    lines = ['# CLS spread analysis', '',
             'Regret: value / best Partitioned placement of the same case - 1. Startup failures are excluded,',
             'not counted as infeasible.', '', '## Runs: ok / deadline miss / excluded', '',
             '| cell | ' + ' | '.join(CONFIGS) + ' |', '|---|' + '---|' * len(CONFIGS)]
    for name, e in result['states'].items():
        lines.append(f'| {name} | ' + ' | '.join(f"{e[k]['ok']} / {e[k]['deadline']} / {e[k]['excluded']}"
                                                 for k in CONFIGS) + ' |')
    for metric in METRICS:
        label = metric.split('_')[0].upper()
        lines += ['', f'## {label} per cell (median ms / mean regret / wins)', '',
                  '| cell | ' + ' | '.join(NAMES.values()) + ' |', '|---|' + '---|' * len(NAMES)]
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
        lines.append(f"| {e['test']} | {e['metric']} | {e['pair']} | {e['n']} | {e['wins']} / {e['ties']} / "
                     f"{e['losses']} | {pct(e['median'])} | {p} | {e['deadline']['only_a']} / {e['deadline']['only_b']} |")
    lines += ['', '## G and C2 against the best Partitioned placement', '',
              '| CLS mean | cases | G ok / ok without any P / beats best P (TAT, TET) / median TAT gap | C2 likewise |',
              '|---|---:|---|---|']
    for scope, e in result['task_count']['architectures'].items():
        cols = [f"{a['ok']} / {a['ok_when_no_partitioned']} / {a['tat_beats_best_partitioned']}, "
                f"{a['tet_beats_best_partitioned']} / {pct(a['tat_median_gap'])}" for a in (e['g'], e['c2'])]
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
    tests = [paired(in_cell(h), a, b, m, h) for h in cells for a, b in CLS_PAIRS for m in METRICS]
    scopes = [(label, lambda r, v=values: r['tasks'] in v) for label, values in GROUPS]
    scopes += [('multiple of 4', lambda r: r['tasks'] % CORES == 0),
               ('not a multiple of 4', lambda r: r['tasks'] % CORES != 0)]
    spread = [r for r in rows if r['cls_sd'] > 0 and r['cls_mean'] > 0.5]
    group_tests = [paired([r for r in spread if r['period_cv'] == cv and member(r)], a, b, m,
                          f'CLS 0.6-0.9 with spread, CV {cv}, {label} tasks')
                   for cv in sorted({r['period_cv'] for r in rows}) for label, member in scopes
                   for a, b in GROUP_PAIRS for m in METRICS]
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
                        architectures={f'{mean}': against_partitioned([r for r in rows if r['cls_mean'] == mean])
                                       for mean in sorted({r['cls_mean'] for r in rows})}),
        selector={m: selector(output, rows, m, args.jobs) for m in METRICS})
    # Counts summed from numpy booleans are numpy integers.
    (output / 'cls-spread-analysis.json').write_text(json.dumps(result, indent=1, default=lambda o: o.item()) + '\n')
    (output / 'cls-spread-analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), output / 'clsspread_analysis.py')
    print('wrote', output / 'cls-spread-analysis.md')


if __name__ == '__main__':
    main()
