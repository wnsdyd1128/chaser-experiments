"""Analyze the policy-mix run: does a combined placement win, does the winner vary, can static features pick it?

Reads <output>/results.jsonl (pm_run summarize), protocol.json (set factors) and every
case's wfd configuration and locality.json (yarda_cpp counts). Per case the four
Partitioned placements (wfd, tg, ra, ra-tg) are compared on measured TAT; a run with a
deadline miss is infeasible (regret counted separately). Writes analysis.json and
analysis.md with:
  schedulable    runs meeting every deadline, per load and configuration
  policies       per placement: mean regret over feasible runs (TAT / best placement's
                 TAT - 1), infeasible runs, wins (ties count for each tied placement)
  pairwise       ra-tg against wfd, tg and ra: paired relative TAT difference, wins /
                 ties / losses, Wilcoxon signed-rank (zeros dropped) with Holm
  factors        per factor level: each placement's mean regret and wins
  architectures  G and C2 (1+1+2) against the best placement of the same case
  selector       the feature pre-check's RF (precheck.evaluate) on this run's cases:
                 set-level CV and leave-one-mechanism-out CV (mechanism = low-CLS
                 count x their traffic x 768 KiB count)
Usage: python3 pm_analysis.py --output <run output dir> [--jobs N]
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy import stats as scipy_stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'feature-precheck'))

import precheck
from taskset_features import LINE_BYTES, Task

KEYS = ('p', 'p_tg', 'p_ra', 'p_ratg')
NAMES = dict(p='wfd', p_tg='tg', p_ra='ra', p_ratg='ra-tg')
ARCHITECTURES = ('g', 'c2')
FACTOR_ORDER = ('periods', 'low', 'traffic', 'big', 'alpha', 'heavy')
ALPHA = 0.05


def feasible(entry) -> bool:
    return entry.get('state') == 'ok'


def tat(row, key) -> float:
    return row[key]['tat_ns'] if feasible(row[key]) else float('inf')


def tet(row, key) -> float:
    return row[key]['tet_ns'] if feasible(row[key]) else float('inf')


def mechanism(f) -> str:
    low = 'low0' if f['low'] == 0 else f"low{f['low']}-{f['traffic']}"
    return f"{low}/big{f['big']}"


def holm(ps):
    order = np.argsort(ps)
    adjusted, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adjusted[i] = running
    return adjusted


def policy_summary(rows):
    out = {}
    for key in KEYS:
        regrets, wins, unique = [], 0, 0
        for r in rows:
            values = [tat(r, k) for k in KEYS]
            best = min(values)
            if not np.isfinite(best):
                continue
            if np.isfinite(tat(r, key)):
                regrets.append(tat(r, key) / best - 1)
            wins += tat(r, key) == best
            unique += tat(r, key) == best and values.count(best) == 1
        out[NAMES[key]] = dict(cases=len(rows), infeasible=sum(not feasible(r[key]) for r in rows),
                               mean_regret=float(np.mean(regrets)) if regrets else None,
                               p95_regret=float(np.percentile(regrets, 95)) if regrets else None,
                               regret_5pct=sum(x >= 0.05 for x in regrets), wins=int(wins), unique_wins=int(unique))
    return out


def pairwise(rows):
    out = []
    for other in ('p', 'p_tg', 'p_ra'):
        d = [tat(r, 'p_ratg') / tat(r, other) - 1 for r in rows
             if np.isfinite(tat(r, 'p_ratg')) and np.isfinite(tat(r, other))]
        entry = dict(pair=f'ra-tg vs {NAMES[other]}', n=len(d), wins=sum(x < 0 for x in d),
                     ties=sum(x == 0 for x in d), losses=sum(x > 0 for x in d),
                     median=float(np.median(d)) if d else None,
                     infeasible=dict(ra_tg=sum(not feasible(r['p_ratg']) for r in rows),
                                     other=sum(not feasible(r[other]) for r in rows)))
        nonzero = [x for x in d if x != 0]
        if len(nonzero) >= 6:
            entry['wilcoxon_p'] = float(scipy_stats.wilcoxon(nonzero).pvalue)
        out.append(entry)
    tested = [e for e in out if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    return out


def architectures(rows):
    out = {}
    for arch in ARCHITECTURES:
        better, gaps, rescues = 0, [], 0
        for r in rows:
            best = min(tat(r, k) for k in KEYS)
            if np.isfinite(best) and feasible(r[arch]):
                gaps.append(tat(r, arch) / best - 1)
                better += tat(r, arch) < best
            rescues += not np.isfinite(best) and feasible(r[arch])
        out[arch] = dict(cases=len(rows), feasible=sum(feasible(r[arch]) for r in rows), beats_best_p=better,
                         median_gap=float(np.median(gaps)) if gaps else None,
                         min_gap=float(min(gaps)) if gaps else None, feasible_when_no_p=rescues)
    return out


def feature_tasks(output, row):
    base = output / f"mix/u{round(row['load'] * 100):03d}/s{row['set_id']:02d}"
    config = json.loads((base / 'wfd/configuration.json').read_text())['tasks']
    counts = {t['task_id']: t for t in json.loads((base / 'locality.json').read_text())['tasks']}
    tasks = []
    for t in config:
        c = counts[t['task_id']]
        job_us = t['u_planned'] * t['period_ticks'] * 1e3
        tasks.append(Task(u=t['u_planned'], period_ms=t['period_ticks'], cls=c['cls'],
                          p_l1=c['l1_hits'] / c['accesses'], p_llc=c['llc_hits'] / c['accesses'],
                          p_miss=c['memory'] / c['accesses'], traffic=c['l1_misses'] / job_us,
                          footprint_kib=c['memory'] * LINE_BYTES / 1024))
    return tasks


def selector(output, rows, jobs):
    precheck.OPTIONS['policy-mix'] = tuple(NAMES[k] for k in KEYS)
    usable = [r for r in rows if np.isfinite(min(tat(r, k) for k in KEYS))]
    samples = [precheck.Sample('policy-mix', mechanism(r['factors']), r['set_id'], dict(load=r['load']),
                               feature_tasks(output, r), tuple(tat(r, k) for k in KEYS),
                               tuple(tet(r, k) for k in KEYS)) for r in usable]
    results, _ = precheck.evaluate('policy-mix', samples, jobs)
    compact = {scheme: {name: value['mean'] for name, value in methods.items()} for scheme, methods in results.items()}
    labels = {NAMES[k]: sum(s.label == i for s in samples) for i, k in enumerate(KEYS)}
    return dict(cases=len(samples), excluded_no_feasible_p=len(rows) - len(usable), labels=labels,
                near_ties=sum(s.margin < precheck.MARGIN for s in samples), results=compact)


def pct(v):
    return '-' if v is None else f'{v * 100:.2f}%'


def p_value(entry):
    return f"{entry['holm_p']:.3g}" if 'holm_p' in entry else '-'


def markdown(result) -> str:
    lines = ['# Policy-mix analysis', '',
             'Regret: measured TAT of a placement / the best placement of the same case - 1, over runs that met',
             'every deadline; infeasible = runs with a deadline miss.', '', '## Schedulable runs', '',
             '| load | ' + ' | '.join(result['schedulable_keys']) + ' |',
             '|---|' + '---:|' * len(result['schedulable_keys'])]
    for load, counts in result['schedulable'].items():
        lines.append(f'| {load} | ' + ' | '.join(f"{counts[k]}/{result['cases_per_load'][load]}"
                                                 for k in result['schedulable_keys']) + ' |')
    for scope, summary in result['policies'].items():
        lines += ['', f'## Placements ({scope})', '',
                  '| placement | mean regret | p95 | regret >= 5% | infeasible | wins | unique wins |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name, s in summary.items():
            lines.append(f"| {name} | {pct(s['mean_regret'])} | {pct(s['p95_regret'])} | {s['regret_5pct']} | "
                         f"{s['infeasible']} | {s['wins']} | {s['unique_wins']} |")
    lines += ['', '## ra-tg against single placements (both feasible)', '',
              '| pair | n | ra-tg better / tie / worse | median difference | Holm p |', '|---|---:|---|---:|---:|']
    for e in result['pairwise']:
        lines.append(f"| {e['pair']} | {e['n']} | {e['wins']} / {e['ties']} / {e['losses']} | {pct(e['median'])} | "
                     f"{p_value(e)} |")
    lines += ['', '## Mean regret by factor level', '']
    for factor, levels in result['factors'].items():
        lines += [f'### {factor}', '', '| level | cases | ' + ' | '.join(NAMES.values()) + ' |',
                  '|---|---:|' + '---:|' * len(NAMES)]
        for level, entry in levels.items():
            lines.append(f"| {level} | {entry['cases']} | " + ' | '.join(
                f"{pct(entry['policies'][n]['mean_regret'])} ({entry['policies'][n]['wins']} wins)" for n in NAMES.values()) + ' |')
        lines.append('')
    lines += ['## Global and Clustered (1+1+2) against the best placement', '',
              '| configuration | feasible | beats best placement | median gap | feasible when no placement is |',
              '|---|---:|---:|---:|---:|']
    for arch, e in result['architectures'].items():
        lines.append(f"| {arch} | {e['feasible']}/{e['cases']} | {e['beats_best_p']} | {pct(e['median_gap'])} | "
                     f"{e['feasible_when_no_p']} |")
    sel = result['selector']
    lines += ['', '## Placement selector (feature pre-check RF)', '',
              f"{sel['cases']} cases (excluded with no feasible placement: {sel['excluded_no_feasible_p']}); "
              f"labels {sel['labels']}; near-ties {sel['near_ties']}", '']
    for scheme, methods in sel['results'].items():
        lines += [f'### {scheme}-level cross-validation', '',
                  '| method | mean regret | p95 | max | accuracy | infeasible choices |', '|---|---:|---:|---:|---:|---:|']
        for name, m in methods.items():
            lines.append(f"| {name} | {pct(m['mean_regret'])} | {pct(m['p95_regret'])} | {pct(m['max_regret'])} | "
                         f"{pct(m['accuracy'])} | {m['infeasible']:.1f} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    set_factors = json.loads((output / 'protocol.json').read_text())['set_factors']
    for r in rows:
        r['factors'] = set_factors[r['set_id']]
    loads = sorted({r['load'] for r in rows})
    keys = list(ARCHITECTURES) + list(KEYS)
    result = dict(
        cases=len(rows), cases_per_load={str(l): sum(r['load'] == l for r in rows) for l in loads},
        schedulable_keys=keys,
        schedulable={str(l): {k: sum(feasible(r[k]) for r in rows if r['load'] == l) for k in keys} for l in loads},
        policies={'all': policy_summary(rows), **{f'load {l}': policy_summary([r for r in rows if r['load'] == l])
                                                 for l in loads}},
        pairwise=pairwise(rows),
        factors={f: {str(level): dict(cases=sum(r['factors'][f] == level for r in rows),
                                      policies=policy_summary([r for r in rows if r['factors'][f] == level]))
                     for level in sorted({r['factors'][f] for r in rows}, key=str)} for f in FACTOR_ORDER},
        architectures=architectures(rows),
        selector=selector(output, rows, args.jobs))
    (output / 'analysis.json').write_text(json.dumps(result, indent=1, default=float) + '\n')
    (output / 'analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), output / 'pm_analysis.py')
    print('wrote', output / 'analysis.md')


if __name__ == '__main__':
    main()
