"""Pre-registered analysis of experiment 28: CAAS Algorithm 1 against the CLS steps on experiment 27's sets.

Fixed, with its tests, before any result of experiment 27 or 28 was read (EXPERIMENTS.md 28).
Per type, joins experiment 27's output (wfd, cgb, ra, ra-cgb) with experiment 28's (caas, cls-a1,
cls-a1-cal) case by case: results.jsonl (state, TAT, TET), rt-metrics.json (violated jobs, worst
memory-task inflation) and experiment 28's configurations (placeable). A run Algorithm 1 could not
place (algorithm1.py's fallback) is 'unplaceable': it stays out of every paired violated-job,
inflation, TET and TAT test, and counts as not meeting every deadline in the deployability test.
Startup failures and other states are missing, as in deadline_analysis.
Primary steps, Holm over the 4 steps x 2 types; a step is supported for a type when significant
after Holm in the stated direction:
  L1 metric    cls-a1 against caas: violated-job ratio (deadline_analysis.violation_test), fewer
  L2 balance   cgb against cls-a1: deployability, exact McNemar of 'placed and met every
               deadline' (two-sided), more
  L3 release   ra-cgb against cgb: TAT log ratio over pairs that both met, two-sided Wilcoxon, shorter
  L4 overall   ra-cgb against caas: violated-job ratio, fewer
Secondary, Holm within: per step and type, worst inflation and TET (pairs that both met),
deployability for L1, L3 and L4, violated jobs for L2 and L3; sensitivity cls-a1-cal against caas
(violated jobs) and against cls-a1 (deployability). Descriptive: per cell and placement, placeable,
met and violated jobs; per Algorithm 1 variant, isolated share of each task role.
Usage: python3 ladder_analysis.py --small <27 small> --small-caas <28 small> --big <27 big>
       --big-caas <28 big> --dest <dir>
"""

import argparse
import json
from pathlib import Path
import sys

from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deadline_analysis import ALPHA, _holm, _log_ratio_test, _fmt, label, inflation_test, met, tet_test
from deadline_analysis import violation_test  # noqa: F401  re-exported for the steps and the tests

BASE = {'wfd': 'p', 'cgb': 'p_cgb', 'ra': 'p_ra', 'ra-cgb': 'p_racgb'}
ALGORITHM1 = {'caas': 'p_caas', 'cls-a1': 'p_clsa1', 'cls-a1-cal': 'p_clsa1cal'}
PLACEMENTS = tuple(BASE) + tuple(ALGORITHM1)
STEPS = {'L1': ('cls-a1', 'caas', 'violated'), 'L2': ('cgb', 'cls-a1', 'deployable'),
         'L3': ('ra-cgb', 'cgb', 'tat'), 'L4': ('ra-cgb', 'caas', 'violated')}


def entry(rt, row, placeable: bool):
    if rt is None:
        return None
    out = dict(rt, tat_ns=row['tat_ns'], tet_ns=row['tet_ns'])
    if not placeable:
        out['state'] = 'unplaceable'
    return out


def deployable_test(cases, a, b) -> dict:
    keep = lambda r: bool(r) and r['state'] in ('ok', 'deadline', 'unplaceable')
    pairs = [(c['runs'][a], c['runs'][b]) for c in cases if keep(c['runs'][a]) and keep(c['runs'][b])]
    only_a = sum(met(x) and not met(y) for x, y in pairs)
    only_b = sum(met(y) and not met(x) for x, y in pairs)
    p = float(scipy_stats.binomtest(min(only_a, only_b), only_a + only_b).pvalue) if only_a + only_b else 1.0
    return dict(pairs=len(pairs), only_first=only_a, only_second=only_b, p=p, direction_holds=only_a > only_b)


def tat_test(cases, a, b) -> dict:
    return _log_ratio_test(cases, a, b, 'tat_ns')


TESTS = {'violated': violation_test, 'deployable': deployable_test, 'tat': tat_test, 'inflation': inflation_test,
         'tet': tet_test}


def summary(cases) -> dict:
    table = {}
    for c in cases:
        cell = table.setdefault(f"{c['heaviness']}/u{round(c['load'] * 1000):04d}", {})
        for p in PLACEMENTS:
            e = cell.setdefault(p, dict(runs=0, placeable=0, met=0, missed_jobs=0, expected_jobs=0))
            r = c['runs'][p]
            if not r or r['state'] not in ('ok', 'deadline', 'unplaceable'):
                continue
            e['runs'] += 1
            if r['state'] == 'unplaceable':
                continue
            e['placeable'] += 1
            e['met'] += met(r)
            e['missed_jobs'] += r['missed_jobs']
            e['expected_jobs'] += r['expected_jobs']
    return dict(sorted(table.items()))


def confirm(studies: dict, isolation: dict | None = None) -> dict:
    primary = _holm([dict(TESTS[metric](cases, a, b), step=step, type=t, first=a, second=b, metric=metric)
                     for t, cases in studies.items() for step, (a, b, metric) in STEPS.items()])
    secondary = []
    for t, cases in studies.items():
        for step, (a, b, main) in STEPS.items():
            extra = ['inflation', 'tet'] + (['violated'] if step in ('L2', 'L3') else ['deployable'])
            secondary += [dict(TESTS[m](cases, a, b), step=step, type=t, first=a, second=b, metric=m) for m in extra]
        secondary.append(dict(violation_test(cases, 'cls-a1-cal', 'caas'), step='S1', type=t, first='cls-a1-cal',
                              second='caas', metric='violated'))
        secondary.append(dict(deployable_test(cases, 'cls-a1-cal', 'cls-a1'), step='S2', type=t, first='cls-a1-cal',
                              second='cls-a1', metric='deployable'))
    supported = {t: {s['step']: s['significant'] for s in primary if s['type'] == t} for t in studies}
    return dict(alpha=ALPHA, steps=STEPS, primary=primary, supported=supported, secondary=_holm(secondary),
                summary={t: summary(cases) for t, cases in studies.items()}, isolation=isolation or {})


def load_type(base: Path, caas: Path) -> tuple[list[dict], dict]:
    rt27 = json.loads((base / 'rt-metrics.json').read_text())['cases']
    rt28 = json.loads((caas / 'rt-metrics.json').read_text())['cases']
    rows28 = {(r['heaviness'], r['load'], r['set_id']): r
              for r in map(json.loads, (caas / 'results.jsonl').read_text().splitlines())}
    cases, isolated = [], {}
    for row in map(json.loads, (base / 'results.jsonl').read_text().splitlines()):
        key = label(row['heaviness'], row['load'], row['set_id'])
        other = rows28.get((row['heaviness'], row['load'], row['set_id']))
        runs = {p: entry(rt27[key][p], row[k], True) for p, k in BASE.items()}
        for p, k in ALGORITHM1.items():
            if other is None:
                runs[p] = None
                continue
            config = json.loads((caas / key / p / 'configuration.json').read_text())
            runs[p] = entry(rt28[key][p], other[k], config['high_load']['placeable'])
            if config['high_load']['placeable']:
                for t in config['tasks']:
                    count = isolated.setdefault(p, {}).setdefault(t['role'], [0, 0])
                    count[0] += t['core'] == 0
                    count[1] += 1
        cases.append(dict(heaviness=row['heaviness'], load=row['load'], set_id=row['set_id'], runs=runs))
    return cases, isolated


def markdown(result: dict) -> str:
    lines = ['# Experiment 28: CAAS Algorithm 1 against the CLS steps (pre-registered)', '',
             f"alpha {result['alpha']}; unplaceable runs count as not meeting every deadline (deployability) and stay out of paired tests.",
             '', '## Primary steps', '', '| type | step | first vs second | metric | pairs | effect | Holm p | supported |',
             '|---|---|---|---|---:|---|---:|---|']
    for e in result['primary'] + result['secondary']:
        if e is result['secondary'][0]:
            lines += ['', '## Secondary', '', '| type | step | first vs second | metric | pairs | effect | Holm p | significant |',
                      '|---|---|---|---|---:|---|---:|---|']
        if e['metric'] == 'deployable':
            effect = f"only first {e['only_first']} / only second {e['only_second']}"
        elif e['metric'] == 'violated':
            effect = f"{_fmt(e['median_difference'], '+.4f')} (fewer {e['fewer_first']} / {e['fewer_second']})"
        else:
            effect = '-' if e['median_change'] is None else f"{e['median_change'] * 100:+.1f}% ({e['wins']} / {e['losses']})"
        lines.append(f"| {e['type']} | {e['step']} | {e['first']} vs {e['second']} | {e['metric']} | {e['pairs']} "
                     f"| {effect} | {_fmt(e['holm_p'], '.2g')} | {e['significant']} |")
    for t, table in result['summary'].items():
        lines += ['', f'## Placed / met every deadline / violated jobs, {t}', '',
                  '| cell | ' + ' | '.join(PLACEMENTS) + ' |', '|---|' + '---|' * len(PLACEMENTS)]
        for cell, row in table.items():
            parts = [f"{row[p]['placeable']}/{row[p]['met']}/{row[p]['runs']}"
                     + (f" ({row[p]['missed_jobs'] / row[p]['expected_jobs']:.1%})" if row[p]['expected_jobs'] else '')
                     for p in PLACEMENTS]
            lines.append(f'| {cell} | ' + ' | '.join(parts) + ' |')
    lines += ['', '## Isolated share per role (placeable runs)', '']
    for t, by_policy in result['isolation'].items():
        for p, roles in by_policy.items():
            lines.append(f"- {t} {p}: " + ', '.join(f'{r} {v[0]}/{v[1]}' for r, v in sorted(roles.items())))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ('--small', '--small-caas', '--big', '--big-caas', '--dest'):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    studies, isolation = {}, {}
    for t, base, caas in (('small', args.small, args.small_caas), ('big', args.big, args.big_caas)):
        studies[t], isolation[t] = load_type(base.resolve(), caas.resolve())
    result = confirm(studies, isolation)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'ladder.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'ladder.md').write_text(markdown(result))
    print('wrote', args.dest / 'ladder.md')


if __name__ == '__main__':
    main()
