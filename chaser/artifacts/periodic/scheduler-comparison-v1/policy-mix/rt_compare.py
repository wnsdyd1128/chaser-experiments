"""Compare Partitioned placements on real-time metrics across experiments 17-25 and their random baselines.

Reads rt_metrics.py's rt-metrics.json of each study's outputs (base runs and the random-baseline
run on the same sets) under --cache and keeps the cases the random run covers. Per study writes,
to --output/rt-compare.json and .md:
  placements   per placement (each random draw counts as a run): runs that met every deadline /
               runs that met or missed (startup failures are left out), deadline-violating jobs /
               released jobs over those runs (rt_metrics.py's missed_jobs / expected_jobs), and, over the cases where
               every placement and draw met every deadline, the median worst memory-task inflation
               (worst job CPU / planned budget) and the median worst response / period
  contrasts    each CLS-based placement against wfd, ra and the random draws, paired by case
               (and draw): deadline discordance (only the first / only the second met every
               deadline), median relative change of the worst memory-task inflation with wins
               (smaller) over the pairs where both met every deadline, median change of the worst
               response ratio, and over the pairs where at least one run missed a deadline: which
               run violated fewer jobs and the median difference of violated jobs (first - second)
Usage: python3 rt_compare.py --cache <.cache dir> --output <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import median

DRAWS = ('rnd0', 'rnd1', 'rnd2')
STUDIES = (
    dict(name='17-18 policy mix', base=(('policy-mix-v1', ('wfd', 'tg', 'ra', 'ra-tg')),
                                        ('policy-mix-cls-v1', ('cg', 'ra-cg'))),
         random='random-policy-mix-v1', cls=('cg', 'ra-cg', 'tg', 'ra-tg')),
    dict(name='19 period spread x memory mix', base=(('policy-boundary-v1', ('wfd', 'cgb', 'ra', 'ra-cgb')),),
         random='random-policy-boundary-v1', cls=('cgb', 'ra-cgb')),
    dict(name='20 768 KiB tasks at 25 % of U', base=(('task-count-v1', ('wfd', 'cgb', 'ra', 'ra-cgb')),),
         random='random-task-count-v1', cls=('cgb', 'ra-cgb')),
    dict(name='21 32 KiB low-CLS tasks', base=(('small-memory-v1', ('wfd', 'cgb', 'ra', 'ra-cgb')),),
         random='random-small-memory-v1', cls=('cgb', 'ra-cgb')),
    dict(name='23 continuous CLS (mean 0.6-0.9, SD > 0)',
         base=(('cls-spread-v1', ('wfd', 'cgb', 'ra', 'ra-cgb', 'cgr', 'ra-cgr')),),
         random='random-cls-spread-v1', cls=('cgb', 'ra-cgb', 'cgr', 'ra-cgr')),
    dict(name='24 32 KiB low-CLS tasks under load', base=(('small-memory-load-v1', ('wfd', 'cgb', 'ra', 'ra-cgb')),),
         random='random-small-memory-load-v1', cls=('cgb', 'ra-cgb')),
    dict(name='25 conflict-miss low-CLS tasks', base=(('conflict-cls-v2', ('wfd', 'cgb', 'ra', 'ra-cgb')),),
         random='random-conflict-cls-v1', cls=('cgb', 'ra-cgb')),
)


def load(cache: Path, study: dict) -> tuple[dict, list[str]]:
    cases = json.loads((cache / study['random'] / 'rt-metrics.json').read_text())['cases']
    table = {case: dict(entries) for case, entries in cases.items()}
    placements = []
    for output, builds in study['base']:
        base = json.loads((cache / output / 'rt-metrics.json').read_text())['cases']
        for case in table:
            table[case].update({b: base[case][b] for b in builds})
        placements += builds
    return table, placements


def measured(entry) -> bool:
    return bool(entry) and entry['state'] in ('ok', 'deadline')


def ok(entry) -> bool:
    return bool(entry) and entry['state'] == 'ok'


def contrast(table, a, refs):
    pairs = [(e[a], e[r]) for e in table.values() for r in refs if measured(e[a]) and measured(e[r])]
    both = [(x, y) for x, y in pairs if ok(x) and ok(y) and x['worst_memory_inflation'] and y['worst_memory_inflation']]
    change = [x['worst_memory_inflation'] / y['worst_memory_inflation'] - 1 for x, y in both]
    response = [x['max_response_ratio'] - y['max_response_ratio'] for x, y in both]
    missing = [(x['missed_jobs'], y['missed_jobs']) for x, y in pairs if x['missed_jobs'] or y['missed_jobs']]
    return dict(pairs=len(pairs), only_first=sum(ok(x) and not ok(y) for x, y in pairs),
                miss_pairs=len(missing), fewer_misses_first=sum(a < b for a, b in missing),
                fewer_misses_second=sum(b < a for a, b in missing),
                missed_difference=median(a - b for a, b in missing) if missing else None,
                only_second=sum(ok(y) and not ok(x) for x, y in pairs), both_ok=len(both),
                inflation_change=median(change) if change else None, inflation_wins=sum(c < 0 for c in change),
                response_change=median(response) if response else None)


def study_result(table, placements, cls):
    columns = placements + list(DRAWS)
    common = [e for e in table.values()
              if all(ok(e[p]) and e[p]['worst_memory_inflation'] for p in columns)]
    rows = {}
    for p in placements + ['random']:
        runs = [e[d] for e in table.values() for d in (DRAWS if p == 'random' else (p,)) if measured(e[d])]
        values = [e[d] for e in common for d in (DRAWS if p == 'random' else (p,))]
        rows[p] = dict(runs=len(runs), met=sum(ok(r) for r in runs), missed_jobs=sum(r['missed_jobs'] for r in runs),
                       expected_jobs=sum(r['expected_jobs'] for r in runs),
                       inflation=median(v['worst_memory_inflation'] for v in values) if values else None,
                       response=median(v['max_response_ratio'] for v in values) if values else None)
    contrasts = {f'{a} vs {name}': contrast(table, a, refs) for a in cls
                 for name, refs in (('wfd', ('wfd',)), ('ra', ('ra',)), ('random', DRAWS))}
    return dict(cases=len(table), common_cases=len(common), placements=rows, contrasts=contrasts)


def fmt(value, spec):
    return '-' if value is None else format(value, spec)


def markdown(result) -> str:
    lines = ['# Real-time metrics across experiments 17-25', '',
             'Inflation: worst memory-task job CPU / planned budget; response: worst (completion - release) / period.',
             'Medians over the cases where every placement and random draw met every deadline.', '']
    for name, s in result.items():
        lines += [f'## {name}', '',
                  f"{s['cases']} cases, {s['common_cases']} with every run meeting every deadline", '',
                  '| placement | met every deadline | violated jobs / released | median worst inflation '
                  '| median worst response |', '|---|---|---|---:|---:|']
        for p, r in s['placements'].items():
            lines.append(f"| {p} | {r['met']} / {r['runs']} | {r['missed_jobs']} / {r['expected_jobs']} "
                         f"| {fmt(r['inflation'], '.2f')} "
                         f"| {fmt(r['response'], '.2f')} |")
        lines += ['', '| contrast | deadline only first / only second | fewer violated jobs first / second '
                      '(median difference) | inflation change (wins / both ok) | response change |',
                  '|---|---|---|---|---:|']
        for c, v in s['contrasts'].items():
            change = '-' if v['inflation_change'] is None else f"{v['inflation_change'] * 100:+.1f}%"
            fewer = f"{v['fewer_misses_first']} / {v['fewer_misses_second']} ({fmt(v['missed_difference'], '+g')})"
            lines.append(f"| {c} | {v['only_first']} / {v['only_second']} | {fewer} | {change} "
                         f"({v['inflation_wins']} / {v['both_ok']}) | {fmt(v['response_change'], '+.3f')} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for study in STUDIES:
        table, placements = load(args.cache.resolve(), study)
        result[study['name']] = study_result(table, placements, study['cls'])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'rt-compare.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.output / 'rt-compare.md').write_text(markdown(result))
    print('wrote', args.output / 'rt-compare.md')


if __name__ == '__main__':
    main()
