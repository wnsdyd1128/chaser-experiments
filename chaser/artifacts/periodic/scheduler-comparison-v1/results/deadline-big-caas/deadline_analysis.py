"""Pre-registered analysis of experiment 27 (confirmatory deadline study): V1-V4 and G/C rescue.

Fixed, with its tests, before any run of deadline-small-v1 or deadline-big-v1 (EXPERIMENTS.md 27).
  predict  after prepare and before any run (it refuses once a measurements.jsonl exists): for
           every case of an output, the static L2 demand ratio of the wfd configuration,
           sum(U_i x planned L1 misses per us_i) / (1000/48 requests per us), and experiment 23's
           verdict (< 0.9 ok, >= 1.0 miss, else uncertain), to <output>/prediction-l2-demand.json
  analyze  reads each output's results.jsonl (hl_run summarize), rt-metrics.json (rt_metrics.py
           with --builds wfd,cgb,ra,ra-cgb,rnd0,rnd1,rnd2) and prediction file; writes
           <dest>/deadline-confirm.json and .md
A case is one set at one load and period cell. A run is measured when it met every deadline
('ok') or missed one ('deadline'); startup failures and other states are missing and drop the
pairs they are in.
  V1  (32 KiB type) the static L2 demand predicts deadlines: a predicted-ok case is correct when
      every deterministic P placement (wfd, cgb, ra, ra-cgb) met every deadline, a predicted-miss
      case when every one missed; supported when both verdicts have a one-sided 95 %
      Clopper-Pearson lower bound >= 0.9 on the share of correct cases. Random draws (cores up
      to U 0.95) are reported, not judged. The 768 KiB type is reported only: the rule ignores
      L2 capacity (experiment 20).
  V2  ra-cgb violates fewer jobs than ra and than wfd: per type and reference, over the measured
      pairs where at least one run violated a job, two-sided Wilcoxon signed-rank on the
      difference of violated-job ratios (missed_jobs / expected_jobs); Holm over the four tests;
      supported for a type when both references are significant with a negative median
      difference and more pairs where ra-cgb violated fewer. Exact McNemar on met-every-deadline
      is reported.
  V3  ra-cgb has a smaller worst memory-task inflation than ra and than wfd: pairs where both met
      every deadline, two-sided Wilcoxon on log ratios, Holm over the four tests; supported when
      significant with a negative median change.
  V4  ra-cgb's TAT is equivalent to ra's within +-TAT_MARGIN: pairs where both met every deadline,
      TOST of one-sided Wilcoxon tests of the log ratio against log(1 + margin) and
      log(1 - margin); Holm over the two types.
  V6  (amendment, registered 2026-10-06 before any result of either output was read) ra-cgb's TET
      is smaller than ra's and than wfd's: pairs where both met every deadline, two-sided
      Wilcoxon on log ratios, Holm over the four tests; supported when significant with a negative
      median change.
Secondary, Holm within its own family: V2 and V3 per period cell, and ra-cgb against the mean of
the three random draws (violated-job ratio; log inflation over draws that all met every
deadline). Descriptive: per cell and placement, runs that met every deadline and violated jobs;
G/C rescue where every deterministic P missed. Tests need MIN_PAIRS nonzero differences.
Usage: python3 deadline_analysis.py predict --output <run output>
       python3 deadline_analysis.py analyze --small <output> --big <output> --dest <dir>
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
import sys

from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'period-distribution'))

from stats import ALPHA, holm

PLACEMENTS = {'wfd': 'p', 'cgb': 'p_cgb', 'ra': 'p_ra', 'ra-cgb': 'p_racgb', 'rnd0': 'p_rnd0', 'rnd1': 'p_rnd1',
              'rnd2': 'p_rnd2'}
DETERMINISTIC = ('wfd', 'cgb', 'ra', 'ra-cgb')
DRAWS = ('rnd0', 'rnd1', 'rnd2')
CANDIDATE, REFERENCES = 'ra-cgb', ('ra', 'wfd')
L2_REQUESTS_PER_US = 1000 / 48
OK_BELOW, MISS_FROM = 0.9, 1.0
BOUND, CONFIDENCE = 0.9, 0.95
TAT_MARGIN = 0.02
MIN_PAIRS = 6


def label(heaviness: str, load: float, set_id: int) -> str:
    """hl_run's case directory."""
    return f'{heaviness}/u{round(load * 100):03d}/s{set_id:02d}'


def measured(entry) -> bool:
    return bool(entry) and entry['state'] in ('ok', 'deadline')


def met(entry) -> bool:
    return bool(entry) and entry['state'] == 'ok'


def lower_bound(successes: int, n: int, confidence: float = CONFIDENCE) -> float:
    """One-sided Clopper-Pearson lower bound of a binomial share."""
    return 0.0 if successes == 0 else float(scipy_stats.beta.ppf(1 - confidence, successes, n - successes + 1))


def prediction_check(cases) -> dict:
    out = {}
    for verdict in ('ok', 'miss', 'uncertain'):
        group = [c for c in cases if c['predicted'] == verdict
                 and all(measured(c['runs'][p]) for p in DETERMINISTIC)]
        draws = [c['runs'][d] for c in group for d in DRAWS if measured(c['runs'][d])]
        entry = dict(cases=len(group), runs=len(group) * len(DETERMINISTIC),
                     met_runs=sum(met(c['runs'][p]) for c in group for p in DETERMINISTIC),
                     random_runs=len(draws), random_met=sum(met(r) for r in draws))
        if verdict != 'uncertain':
            correct = sum(all(met(c['runs'][p]) == (verdict == 'ok') for p in DETERMINISTIC) for c in group)
            entry.update(correct=correct, accuracy=correct / len(group) if group else None,
                         lower_bound=lower_bound(correct, len(group)) if group else None)
        out[verdict] = entry
    out['supported'] = all(out[v]['lower_bound'] is not None and out[v]['lower_bound'] >= BOUND
                           for v in ('ok', 'miss'))
    return out


def _paired(cases, a, b, keep):
    """(run a, runs of b) per case where keep holds for a and every run of b; b 'random' is the draws."""
    pairs = []
    for c in cases:
        x, ys = c['runs'][a], [c['runs'][d] for d in (DRAWS if b == 'random' else (b,))]
        if keep(x) and all(keep(y) for y in ys):
            pairs.append((x, ys))
    return pairs


def _wilcoxon(values, **kwargs):
    return float(scipy_stats.wilcoxon(values, **kwargs).pvalue) if sum(v != 0 for v in values) >= MIN_PAIRS else None


def violation_test(cases, a, b) -> dict:
    ratio = lambda r: r['missed_jobs'] / r['expected_jobs']
    pairs = _paired(cases, a, b, measured)
    violating = [(x, ys) for x, ys in pairs if x['missed_jobs'] or any(y['missed_jobs'] for y in ys)]
    diffs = [ratio(x) - sum(ratio(y) for y in ys) / len(ys) for x, ys in violating]
    out = dict(pairs=len(pairs), violating_pairs=len(violating), fewer_first=sum(d < 0 for d in diffs),
               fewer_second=sum(d > 0 for d in diffs), median_difference=median(diffs) if diffs else None,
               only_first_met=None, only_second_met=None, mcnemar_p=None, p=_wilcoxon(diffs))
    if b != 'random':
        only_a = sum(met(x) and not met(ys[0]) for x, ys in pairs)
        only_b = sum(met(ys[0]) and not met(x) for x, ys in pairs)
        out.update(only_first_met=only_a, only_second_met=only_b,
                   mcnemar_p=float(scipy_stats.binomtest(min(only_a, only_b), only_a + only_b).pvalue)
                   if only_a + only_b else 1.0)
    out['direction_holds'] = bool(diffs) and out['median_difference'] < 0 and out['fewer_first'] > out['fewer_second']
    return out


def _log_ratio_test(cases, a, b, field) -> dict:
    keep = lambda r: met(r) and bool(r[field])
    logs = [math.log(x[field]) - sum(math.log(y[field]) for y in ys) / len(ys) for x, ys in _paired(cases, a, b, keep)]
    change = math.exp(median(logs)) - 1 if logs else None
    return dict(pairs=len(logs), median_change=change, wins=sum(v < 0 for v in logs), losses=sum(v > 0 for v in logs),
                p=_wilcoxon(logs), direction_holds=change is not None and change < 0)


def inflation_test(cases, a, b) -> dict:
    return _log_ratio_test(cases, a, b, 'worst_memory_inflation')


def tet_test(cases, a, b) -> dict:
    return _log_ratio_test(cases, a, b, 'tet_ns')


def tat_equivalence(cases, a, b, margin: float = TAT_MARGIN) -> dict:
    logs = [math.log(x['tat_ns'] / ys[0]['tat_ns']) for x, ys in _paired(cases, a, b, met)]
    out = dict(pairs=len(logs), margin=margin, median_ratio=math.exp(median(logs)) if logs else None,
               p_upper=None, p_lower=None, p=None)
    if len(logs) >= MIN_PAIRS:
        out.update(p_upper=_wilcoxon([v - math.log(1 + margin) for v in logs], alternative='less'),
                   p_lower=_wilcoxon([v - math.log(1 - margin) for v in logs], alternative='greater'))
        out['p'] = max(out['p_upper'], out['p_lower'])
    return out


def rescue(cases) -> dict:
    group = [c for c in cases if all(measured(c['runs'][p]) and not met(c['runs'][p]) for p in DETERMINISTIC)]
    return dict(all_p_missed=len(group), g_met=sum(met(c['runs']['g']) for c in group),
                c2_met=sum(met(c['runs']['c2']) for c in group),
                either_met=sum(met(c['runs']['g']) or met(c['runs']['c2']) for c in group))


def summary(cases) -> dict:
    table = {}
    for c in cases:
        cell = table.setdefault(f"{c['heaviness']}/u{round(c['load'] * 1000):04d}", {})
        for name, members in [(p, (p,)) for p in DETERMINISTIC] + [('random', DRAWS), ('g', ('g',)), ('c2', ('c2',))]:
            jobs = name not in ('g', 'c2')  # rt_metrics.py reads P runs only
            entry = cell.setdefault(name, dict(runs=0, met=0, missed_jobs=0, expected_jobs=0, excluded=0) if jobs
                                    else dict(runs=0, met=0, excluded=0))
            for run in (c['runs'][m] for m in members):
                if not measured(run):
                    entry['excluded'] += 1
                    continue
                entry['runs'] += 1
                entry['met'] += met(run)
                if jobs:
                    entry['missed_jobs'] += run['missed_jobs']
                    entry['expected_jobs'] += run['expected_jobs']
    return dict(sorted(table.items()))


def _holm(tests, directional=True):
    tested = [t for t in tests if t['p'] is not None]
    for t, adjusted in zip(tested, holm([t['p'] for t in tested])):
        t.update(holm_p=adjusted, significant=adjusted < ALPHA and (not directional or t['direction_holds']))
    for t in tests:
        t.setdefault('holm_p', None)
        t.setdefault('significant', False)
    return tests


def confirm(studies: dict) -> dict:
    """studies: type ('small', 'big') -> cases."""
    v2 = _holm([dict(violation_test(cases, CANDIDATE, ref), type=t, reference=ref)
                for t, cases in studies.items() for ref in REFERENCES])
    v3 = _holm([dict(inflation_test(cases, CANDIDATE, ref), type=t, reference=ref)
                for t, cases in studies.items() for ref in REFERENCES])
    v4 = _holm([dict(tat_equivalence(cases, CANDIDATE, 'ra'), type=t) for t, cases in studies.items()],
               directional=False)
    v6 = _holm([dict(tet_test(cases, CANDIDATE, ref), type=t, reference=ref)
                for t, cases in studies.items() for ref in REFERENCES])
    secondary = []
    for t, cases in studies.items():
        for cv in sorted({c['heaviness'].split('-')[0] for c in cases}):
            group = [c for c in cases if c['heaviness'].startswith(cv + '-')]
            for ref in REFERENCES:
                secondary.append(dict(violation_test(group, CANDIDATE, ref), metric='violated', type=t, cell=cv,
                                      reference=ref))
                secondary.append(dict(inflation_test(group, CANDIDATE, ref), metric='inflation', type=t, cell=cv,
                                      reference=ref))
        secondary.append(dict(violation_test(cases, CANDIDATE, 'random'), metric='violated', type=t, cell='all',
                              reference='random'))
        secondary.append(dict(inflation_test(cases, CANDIDATE, 'random'), metric='inflation', type=t, cell='all',
                              reference='random'))
    by_type = lambda tests: {t: all(e['significant'] for e in tests if e['type'] == t) for t in studies}
    return dict(alpha=ALPHA, candidate=CANDIDATE, references=REFERENCES,
                V1={t: prediction_check(cases) for t, cases in studies.items()},
                V2=dict(tests=v2, supported=by_type(v2)), V3=dict(tests=v3, supported=by_type(v3)),
                V4=dict(tests=v4, supported=by_type(v4)), V6=dict(tests=v6, supported=by_type(v6)),
                secondary=_holm(secondary),
                rescue={t: rescue(cases) for t, cases in studies.items()},
                summary={t: summary(cases) for t, cases in studies.items()})


def load_study(output: Path) -> list[dict]:
    rt = json.loads((output / 'rt-metrics.json').read_text())['cases']
    predicted = json.loads((output / 'prediction-l2-demand.json').read_text())['cases']
    cases = []
    for line in (output / 'results.jsonl').read_text().splitlines():
        row = json.loads(line)
        key = label(row['heaviness'], row['load'], row['set_id'])
        runs = {}
        for placement, k in PLACEMENTS.items():
            entry = rt[key][placement]
            if entry is not None and entry['state'] != row[k]['state']:
                raise ValueError(f'{key}/{placement}: rt-metrics state {entry["state"]} != results {row[k]["state"]}')
            runs[placement] = None if entry is None else dict(entry, tat_ns=row[k]['tat_ns'], tet_ns=row[k]['tet_ns'])
        runs.update(g=dict(state=row['g']['state']), c2=dict(state=row['c2']['state']))
        cases.append(dict(heaviness=row['heaviness'], load=row['load'], set_id=row['set_id'],
                          predicted=predicted[key]['predicted'], demand_ratio=predicted[key]['demand_ratio'], runs=runs))
    return cases


def predict(output: Path) -> dict:
    started = next(output.rglob('measurements.jsonl'), None)
    if started is not None:
        raise RuntimeError(f'A run already exists ({started}); the prediction must come first')
    cases = {}
    for path in sorted(output.glob('*/u0*/s*/wfd/configuration.json')):
        config = json.loads(path.read_text())
        hl = config['high_load']
        ratio = sum(t['u_planned'] * t['traffic_planned'] for t in config['tasks']) / L2_REQUESTS_PER_US
        verdict = 'miss' if ratio >= MISS_FROM else 'ok' if ratio < OK_BELOW else 'uncertain'
        cases[label(hl['heaviness'], hl['load'], hl['set_id'])] = dict(demand_ratio=ratio, predicted=verdict)
    per_cell = {}
    for key, value in cases.items():
        cell = per_cell.setdefault(key.rsplit('/', 1)[0], {})
        cell[value['predicted']] = cell.get(value['predicted'], 0) + 1
    out = dict(made_utc=datetime.now(timezone.utc).isoformat(), l2_requests_per_us=L2_REQUESTS_PER_US,
               ok_below=OK_BELOW, miss_from=MISS_FROM,
               note='Written before any run of this output. Rule fitted on experiment 23 and checked on 24: '
                    'every P placement meets deadlines below ok_below, every one misses from miss_from.',
               per_cell=per_cell, cases=cases)
    (output / 'prediction-l2-demand.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


def _fmt(value, spec):
    return '-' if value is None else format(value, spec)


def markdown(result: dict) -> str:
    lines = ['# Experiment 27: pre-registered deadline confirmation', '',
             f"Candidate {result['candidate']} against {', '.join(result['references'])}; alpha {result['alpha']}.", '',
             '## V1: static L2 demand verdicts', '',
             '| type | verdict | cases | correct | lower bound | P runs met | random runs met |', '|---|---|---:|---:|---:|---:|---:|']
    for t, v in result['V1'].items():
        for verdict in ('ok', 'miss', 'uncertain'):
            e = v[verdict]
            lines.append(f"| {t} | {verdict} | {e['cases']} | {e.get('correct', '-')} | {_fmt(e.get('lower_bound'), '.3f')} "
                         f"| {e['met_runs']} / {e['runs']} | {e['random_met']} / {e['random_runs']} |")
        lines.append(f"| {t} | supported | {v['supported']} | | | | |")
    lines += ['', '## V2: violated jobs (ra-cgb - reference, ratio of released jobs)', '',
              '| type | reference | pairs | violating | fewer ra-cgb / ref | median difference | only ra-cgb / only ref met '
              '| Holm p | significant |', '|---|---|---:|---:|---|---:|---|---:|---|']
    for e in result['V2']['tests']:
        lines.append(f"| {e['type']} | {e['reference']} | {e['pairs']} | {e['violating_pairs']} | {e['fewer_first']} / "
                     f"{e['fewer_second']} | {_fmt(e['median_difference'], '+.4f')} | {e['only_first_met']} / "
                     f"{e['only_second_met']} | {_fmt(e['holm_p'], '.2g')} | {e['significant']} |")
    lines += ['', '## V3: worst memory-task inflation', '',
              '| type | reference | pairs | median change | wins / losses | Holm p | significant |',
              '|---|---|---:|---:|---|---:|---|']
    for e in result['V3']['tests']:
        change = '-' if e['median_change'] is None else f"{e['median_change'] * 100:+.1f}%"
        lines.append(f"| {e['type']} | {e['reference']} | {e['pairs']} | {change} | {e['wins']} / {e['losses']} "
                     f"| {_fmt(e['holm_p'], '.2g')} | {e['significant']} |")
    lines += ['', '## V4: TAT equivalence with ra', '', '| type | pairs | median ratio | TOST Holm p | equivalent |',
              '|---|---:|---:|---:|---|']
    for e in result['V4']['tests']:
        lines.append(f"| {e['type']} | {e['pairs']} | {_fmt(e['median_ratio'], '.4f')} | {_fmt(e['holm_p'], '.2g')} "
                     f"| {e['significant']} |")
    lines += ['', '## V6: TET (amendment registered before any result was read)', '',
              '| type | reference | pairs | median change | wins / losses | Holm p | significant |',
              '|---|---|---:|---:|---|---:|---|']
    for e in result['V6']['tests']:
        change = '-' if e['median_change'] is None else f"{e['median_change'] * 100:+.1f}%"
        lines.append(f"| {e['type']} | {e['reference']} | {e['pairs']} | {change} | {e['wins']} / {e['losses']} "
                     f"| {_fmt(e['holm_p'], '.2g')} | {e['significant']} |")
    lines += ['', '## Secondary', '', '| metric | type | cell | reference | pairs | effect | Holm p | significant |',
              '|---|---|---|---|---:|---:|---:|---|']
    for e in result['secondary']:
        effect = (_fmt(e['median_difference'], '+.4f') if e['metric'] == 'violated'
                  else '-' if e['median_change'] is None else f"{e['median_change'] * 100:+.1f}%")
        lines.append(f"| {e['metric']} | {e['type']} | {e['cell']} | {e['reference']} | {e['pairs']} | {effect} "
                     f"| {_fmt(e['holm_p'], '.2g')} | {e['significant']} |")
    lines += ['', '## G/C where every deterministic P missed', '', '| type | cases | G met | C2 met | either |',
              '|---|---:|---:|---:|---:|']
    for t, e in result['rescue'].items():
        lines.append(f"| {t} | {e['all_p_missed']} | {e['g_met']} | {e['c2_met']} | {e['either_met']} |")
    for t, table in result['summary'].items():
        names = list(next(iter(table.values())))
        lines += ['', f'## Runs that met every deadline, {t} (violated jobs / released for P)', '',
                  '| cell | ' + ' | '.join(names) + ' |', '|---|' + '---|' * len(names)]
        for cell, row in table.items():
            parts = [f"{row[n]['met']}/{row[n]['runs']}" + (f" ({row[n]['missed_jobs'] / row[n]['expected_jobs']:.1%})"
                                                          if row[n].get('expected_jobs') else '') for n in names]
            lines.append(f'| {cell} | ' + ' | '.join(parts) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='stage', required=True)
    sub.add_parser('predict').add_argument('--output', type=Path, required=True)
    analyze = sub.add_parser('analyze')
    for name in ('--small', '--big', '--dest'):
        analyze.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    if args.stage == 'predict':
        out = predict(args.output.resolve())
        for cell, counts in out['per_cell'].items():
            print(cell, counts)
        return
    result = confirm(dict(small=load_study(args.small.resolve()), big=load_study(args.big.resolve())))
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'deadline-confirm.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'deadline-confirm.md').write_text(markdown(result))
    print('wrote', args.dest / 'deadline-confirm.md')


if __name__ == '__main__':
    main()
