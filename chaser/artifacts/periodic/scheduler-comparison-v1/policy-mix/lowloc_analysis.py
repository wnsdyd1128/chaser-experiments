"""Experiment 47's pre-registered analysis (EXPERIMENTS.md 47): experiment 27's tests on the lowloc-kernels output.

Per case and build, rt_metrics.metrics gives the run state, the missed jobs over the expected jobs and the worst job CPU
over the planned budget of the low tasks (role 'low'); TET and TAT come from results.jsonl. The tests are
deadline_analysis' functions (alpha 0.05, Holm within each family):
  V2  violated jobs, RA-CGB against WFD and against RA (two-sided Wilcoxon over the pairs with a violation; the deadline
      McNemar is reported with it)
  V3  worst low-task job CPU / budget, RA-CGB against WFD and against RA (log ratio over the pairs where both met)
  V4  TAT equivalence of RA-CGB and RA within +-2 % (TOST)
  V6  TET, RA-CGB against WFD and against RA (log ratio over the pairs where both met)
  secondary (one Holm family): V2 and V3 per period-CV cell, and CGB against WFD for V2, V3 and V6
A hypothesis is supported when every test of its family is significant in the stated direction (V4: equivalent).
Usage: python3 lowloc_analysis.py --output <lowloc-kernels output> --dest <dir>
Run with PYTHONPATH=<c3 code copy>:policy-mix:period-distribution (the analysis reads JSON only).
"""

import argparse
import json
from pathlib import Path

import deadline_analysis as da
import rt_metrics

PLACEMENTS = {'wfd': 'p', 'cgb': 'p_cgb', 'ra': 'p_ra', 'ra-cgb': 'p_racgb'}
CANDIDATE, REFERENCES = 'ra-cgb', ('wfd', 'ra')


def load(output: Path) -> list[dict]:
    cases = []
    for line in (output / 'results.jsonl').read_text().splitlines():
        row = json.loads(line)
        case = output / da.label(row['heaviness'], row['load'], row['set_id'])
        runs = {}
        for build, key in PLACEMENTS.items():
            entry = rt_metrics.metrics((case, build))
            if entry is not None and entry['state'] != row[key]['state']:
                raise ValueError(f'{case}/{build}: rt_metrics state {entry["state"]} != results {row[key]["state"]}')
            runs[build] = None if entry is None else dict(entry, tet_ns=row[key].get('tet_ns'), tat_ns=row[key].get('tat_ns'))
        cases.append(dict(heaviness=row['heaviness'], load=row['load'], set_id=row['set_id'], runs=runs))
    return cases


def judge(cases) -> dict:
    v2 = da._holm([dict(da.violation_test(cases, CANDIDATE, ref), reference=ref) for ref in REFERENCES])
    v3 = da._holm([dict(da.inflation_test(cases, CANDIDATE, ref), reference=ref) for ref in REFERENCES])
    v4 = da._holm([dict(da.tat_equivalence(cases, CANDIDATE, 'ra'))], directional=False)
    v6 = da._holm([dict(da.tet_test(cases, CANDIDATE, ref), reference=ref) for ref in REFERENCES])
    secondary = []
    for cell in sorted({c['heaviness'] for c in cases}):
        group = [c for c in cases if c['heaviness'] == cell]
        for ref in REFERENCES:
            secondary.append(dict(da.violation_test(group, CANDIDATE, ref), metric='violated', cell=cell, first=CANDIDATE, reference=ref))
            secondary.append(dict(da.inflation_test(group, CANDIDATE, ref), metric='inflation', cell=cell, first=CANDIDATE, reference=ref))
    for metric, test in (('violated', da.violation_test), ('inflation', da.inflation_test), ('tet', da.tet_test)):
        secondary.append(dict(test(cases, 'cgb', 'wfd'), metric=metric, cell='all', first='cgb', reference='wfd'))
    supported = lambda tests: all(t['significant'] for t in tests)
    met = {}
    for c in cases:
        cell = met.setdefault(f"{c['heaviness']} u{round(c['load'] * 100):03d}", {b: [0, 0] for b in PLACEMENTS})
        for b in PLACEMENTS:
            r = c['runs'][b]
            if da.measured(r):
                cell[b][1] += 1
                cell[b][0] += da.met(r)
    return dict(alpha=da.ALPHA, candidate=CANDIDATE, references=REFERENCES, cases=len(cases),
                V2=dict(tests=v2, supported=supported(v2)), V3=dict(tests=v3, supported=supported(v3)),
                V4=dict(tests=v4, supported=supported(v4)), V6=dict(tests=v6, supported=supported(v6)),
                secondary=da._holm(secondary), met_per_cell=met)


def fmt(v, spec):
    return '-' if v is None else format(v, spec)


def markdown(result) -> str:
    lines = ['# Experiment 47: CHASER placement on real low-locality kernels (pre-registered)', '',
             f"{result['cases']} cases; candidate {result['candidate']} against {', '.join(result['references'])}; alpha {result['alpha']}", '',
             '## V2: violated jobs (ratio of released jobs)', '',
             '| reference | pairs | violating | fewer ra-cgb / ref | median difference | only ra-cgb / only ref met | McNemar p | Holm p | significant |',
             '|---|---:|---:|---|---:|---|---:|---:|---|']
    for t in result['V2']['tests']:
        lines.append(f"| {t['reference']} | {t['pairs']} | {t['violating_pairs']} | {t['fewer_first']} / {t['fewer_second']} | "
                     f"{fmt(t['median_difference'], '+.4f')} | {t['only_first_met']} / {t['only_second_met']} | {fmt(t['mcnemar_p'], '.3g')} | "
                     f"{fmt(t['holm_p'], '.3g')} | {t['significant']} |")
    for name, title in (('V3', 'worst low-task job CPU / budget'), ('V6', 'TET')):
        lines += ['', f'## {name}: {title}', '', '| reference | pairs | median change | wins / losses | Holm p | significant |',
                  '|---|---:|---:|---|---:|---|']
        for t in result[name]['tests']:
            lines.append(f"| {t['reference']} | {t['pairs']} | {fmt(t['median_change'], '+.1%')} | {t['wins']} / {t['losses']} | "
                         f"{fmt(t['holm_p'], '.3g')} | {t['significant']} |")
    t = result['V4']['tests'][0]
    lines += ['', '## V4: TAT equivalence with ra (+-2 %)', '', f"pairs {t['pairs']}, median ratio {fmt(t['median_ratio'], '.4f')}, "
              f"TOST Holm p {fmt(t['holm_p'], '.3g')}, equivalent {t['significant']}", '',
              '## Supported', '', ', '.join(f"{k}: {result[k]['supported']}" for k in ('V2', 'V3', 'V4', 'V6')), '',
              '## Secondary', '', '| metric | cell | first vs reference | pairs | effect | Holm p | significant |', '|---|---|---|---:|---:|---:|---|']
    for s in result['secondary']:
        effect = fmt(s.get('median_difference'), '+.4f') if s['metric'] == 'violated' else fmt(s.get('median_change'), '+.1%')
        lines.append(f"| {s['metric']} | {s['cell']} | {s['first']} vs {s['reference']} | {s['pairs']} | {effect} | "
                     f"{fmt(s['holm_p'], '.3g')} | {s['significant']} |")
    lines += ['', '## Runs that met every deadline (met / measured)', '', '| cell | ' + ' | '.join(PLACEMENTS) + ' |',
              '|---|' + '---|' * len(PLACEMENTS)]
    for cell, v in result['met_per_cell'].items():
        lines.append(f'| {cell} | ' + ' | '.join(f'{m}/{n}' for m, n in v.values()) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    result = judge(load(args.output.resolve()))
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'lowloc.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'lowloc.md').write_text(markdown(result))
    print('wrote', args.dest / 'lowloc.md')


if __name__ == '__main__':
    main()
