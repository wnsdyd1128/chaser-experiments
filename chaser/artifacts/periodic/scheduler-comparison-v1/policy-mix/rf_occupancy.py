"""Pre-run check: the static L2 + memory occupancy rule against the RF (experiment 42, development check).

Rows are experiment 35's (task set, candidate) rows plus experiment 41's P runs (wfd, cgb); cache values come
from the YARDA outputs. Each set gets the memory demand M (memcost_analysis.memory_demand) and the occupancy
D + M. Scores for "P meets every deadline", held out by experiment: D, D + M (static, no training), RF f35
(experiment 35's main features), RF f35m (f35 + M + D + M) and RF f35m with another seed (noise reference).
The static rule accepts CHASER's placement when D + M is below t*, the largest grid value keeping the
accepted P rows' miss rate at most MAX_MISS on the development rows; it never recommends G/C, since D + M
is the same for every configuration of a set. Judgment fixed beforehand (EXPERIMENTS.md 42): the RF is the
main method if its P-row AUC beats D + M by more than the seed noise in all but one held-out experiment.
Reads the rows from rf_rows' table (results/rf-model/training-rows.jsonl.gz).
Usage: python3 rf_occupancy.py --rows <training rows table> --dest <dir>
"""

import argparse
import json
from pathlib import Path

import numpy as np

import memcost_analysis as ma
import rf_candidates as rc
import rf_devcheck as rd
import rf_rows

SOURCES = rc.SOURCES + (('41 memory cost', (('memory-cost-v1', 'p', 'wfd', 'wfd'),
                                            ('memory-cost-v1', 'p_cgb', 'cgb', 'cgb'))),)
FEATURE_SETS = {'f35': rc.FEATURE_SETS['f35'], 'f35m': rc.FEATURE_SETS['f35'] + ['memory_demand', 'occupancy']}
GRID = tuple(round(0.7 + 0.025 * i, 3) for i in range(21))
MAX_MISS = 0.01
TAUS = (0.5, 0.8)


def demands(cache: Path) -> dict:
    """Case id -> memory demand M of the set (YARDA outputs of the first output's wfd build)."""
    out = {}
    for source, runs in SOURCES:
        first = runs[0][0]
        for key in rd._results(cache / first / 'results.jsonl'):
            case = cache / first / f'{key[0]}/u{round(key[1] * 100):03d}/s{key[2]:02d}'
            tasks = json.loads((case / 'wfd/configuration.json').read_text())['tasks']
            out[f'{source}/{key}'] = ma.memory_demand(rc.yarda_tasks(case, tasks))
    return out


def add_occupancy(rows, memory) -> None:
    for r in rows:
        r['features'].update(memory_demand=memory[r['case']], occupancy=r['features']['cache_demand'] + memory[r['case']])


def rule_threshold(rows, grid=GRID, max_miss=MAX_MISS) -> float:
    """Largest t whose accepted P rows (occupancy < t) miss at most max_miss of the time."""
    p = [r for r in rows if r['candidate'] in rc.P_CANDIDATES]
    ok = [t for t in grid
          if sum(1 - r['label'] for r in p if r['features']['occupancy'] < t)
          <= max_miss * max(1, sum(r['features']['occupancy'] < t for r in p))]
    return max(ok)


def rule_probs(probs, occupancy, threshold) -> dict:
    """The static rule as decision probabilities: CHASER's placement if below the threshold, nothing else."""
    return {c: float(c == rc.CURRENT and occupancy < threshold) for c in probs}


def judge(rf_auc, rule_auc, noise) -> dict:
    pairs = [(rf_auc[s], b) for s, b in rule_auc.items() if b is not None and rf_auc.get(s) is not None]
    higher = sum(a - b > noise for a, b in pairs)
    return dict(higher=higher, compared=len(pairs), noise=noise, main='rf' if higher >= len(pairs) - 1 else 'static rule')


def p_auc_by_source(rows, scores) -> dict:
    out = {}
    for source, _ in SOURCES:
        idx = [i for i, r in enumerate(rows) if r['source'] == source and r['candidate'] in rc.P_CANDIDATES]
        out[source] = rd.auc([rows[i]['label'] for i in idx], [scores[i] for i in idx])
    idx = [i for i, r in enumerate(rows) if r['candidate'] in rc.P_CANDIDATES]
    out['all'] = rd.auc([rows[i]['label'] for i in idx], [scores[i] for i in idx])
    return out


def rule_simulation(rows, threshold) -> dict:
    occupancy = {r['case']: r['features']['occupancy'] for r in rows}
    cases = rc.cases_of(rows, np.zeros(len(rows)))
    static = [dict(met=c['met'], probs=rule_probs(c['probs'], occupancy[k], threshold)) for k, c in cases.items()]
    return rc.simulate(static, 0.5)


def p_acceptance(rows, accept) -> dict:
    """Accept/reject of the P rows alone: accepted, accepted misses, rejected rows that met."""
    p = [(r, a) for r, a in zip(rows, accept) if r['candidate'] in rc.P_CANDIDATES]
    return dict(rows=len(p), accepted=sum(a for _, a in p), false_accept=sum(a and not r['label'] for r, a in p),
                false_reject=sum((not a) and r['label'] for r, a in p))


def markdown(result) -> str:
    f = lambda v: '-' if v is None else f'{v:.3f}'
    auc = result['p_auc']
    sources = [s for s in auc['D + M'] if s != 'all']
    lines = ['# Pre-run check: static D + M rule against the RF (experiment 42, development check)', '',
             f"{result['rows']} rows (P rows {result['p_rows']}); static threshold t* = {result['threshold']} "
             f"(accepted P rows miss at most {MAX_MISS:.0%})", '',
             '## P rows: AUC for meeting every deadline, each experiment held out', '',
             '| score | ' + ' | '.join(sources) + ' | all |', '|---|' + '---:|' * (len(sources) + 1)]
    for name, v in auc.items():
        lines.append(f'| {name} | ' + ' | '.join(f(v[s]) for s in sources) + f" | {f(v['all'])} |")
    j = result['judgment']
    lines += ['', f"Judgment: RF f35m above D + M by more than the seed noise ({j['noise']:.3f}) in {j['higher']} of "
                  f"{j['compared']} experiments -> main method: **{j['main']}**", '',
              '## P rows alone: accept or reject (development rows, held out by experiment for the RF)', '',
              '| method | P rows | accepted | false accept | false reject |', '|---|---:|---:|---:|---:|']
    for name, s in result['p_acceptance'].items():
        lines.append(f"| {name} | {s['rows']} | {s['accepted']} | {s['false_accept']} | {s['false_reject']} |")
    lines += ['', '## Decision simulation on the sets with CHASER, G4 and C1+1+2 runs (held out by experiment for the RF)', '',
              '| method | sets | accepted (met / false accept) | rejected (false reject) | chose other | saved | wrong switch |',
              '|---|---:|---|---|---:|---:|---:|']
    for name, s in result['simulation'].items():
        lines.append(f"| {name} | {s['cases']} | {s['accepted']} ({s['accepted_met']} / {s['false_accept']}) "
                     f"| {s['rejected']} ({s['false_reject']}) | {s['chose_other']} | {s['saved']} | {s['wrong_switch']} |")
    first = next(iter(result['simulation'].values()))
    lines += ['', f"Always CHASER: {first['current_met']} of {first['cases']} sets meet every deadline; "
                  f"the best candidate meets {first['oracle_met']}; rescuable {first['oracle_saves']}."]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    rows = rf_rows.load(args.rows)
    threshold = rule_threshold(rows)
    probs = {name: rc.out_of_fold(rows, names, rd.experiment_folds) for name, names in FEATURE_SETS.items()}
    probs['f35m (seed 1)'] = rc.out_of_fold(rows, FEATURE_SETS['f35m'], rd.experiment_folds, seed=1)
    scores = {'D': [-r['features']['cache_demand'] for r in rows], 'D + M': [-r['features']['occupancy'] for r in rows],
              **{f'RF {k}': list(v) for k, v in probs.items()}}
    auc = {name: p_auc_by_source(rows, s) for name, s in scores.items()}
    noise = max(abs(a - b) for s in auc['RF f35m'] if s != 'all'
                for a, b in [(auc['RF f35m'][s], auc['RF f35m (seed 1)'][s])] if a is not None and b is not None)
    accept = {f'D + M < {threshold}': [r['features']['occupancy'] < threshold for r in rows],
              **{f'RF f35m, tau {t}': [bool(p >= t) for p in probs['f35m']] for t in TAUS}}
    simulation = {f'D + M < {threshold} (CHASER or reject)': rule_simulation(rows, threshold),
                  **{f'RF f35m, tau {t}': rc.simulate(list(rc.cases_of(rows, probs['f35m']).values()), t) for t in TAUS},
                  # Added after the first run (descriptive): experiment 35 kept the candidates at CHASER + G/C.
                  **{f'RF f35m, tau {t}, CHASER + G/C only': rc.simulate(list(rc.cases_of(rows, probs['f35m']).values()), t,
                                                                          rc.CURRENT_ONLY) for t in TAUS}}
    result = dict(rows=len(rows), p_rows=sum(r['candidate'] in rc.P_CANDIDATES for r in rows), threshold=threshold,
                  p_auc=auc, judgment=judge({s: v for s, v in auc['RF f35m'].items() if s != 'all'},
                                            {s: v for s, v in auc['D + M'].items() if s != 'all'}, noise),
                  p_acceptance={k: p_acceptance(rows, v) for k, v in accept.items()}, simulation=simulation)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'rf-occupancy.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'rf-occupancy.md').write_text(markdown(result))
    print('wrote', args.dest / 'rf-occupancy.md')


if __name__ == '__main__':
    main()
