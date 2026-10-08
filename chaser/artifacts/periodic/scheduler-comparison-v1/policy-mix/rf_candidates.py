"""RF configuration recommender with several P placement candidates (experiment 35, exploratory).

Extends rf_devcheck (experiment 34): the P candidates are wfd, cgb, ra-cgb and, on experiment 32's sets,
ra-cgk (experiments 17 and 18 put cg and ra-cg in the cgb and ra-cgb slots), next to G4, C1+3 and
C1+1+2. Rows are (task set, candidate); the label is whether the run met every deadline over the whole
run (hl_run state ok; startup and other states are left out). Cache values come from the YARDA outputs
of the wfd build (locality.json CLS; L1 misses over the planned job time; unique lines x 32 B), the
other values from the configuration (U, period, core). Candidate features add release crowding, the
peak released work at time 0, the group core's inflated load and the other tasks' U on group cores.
One RF per feature set (f34, f35 main, f35-noid, f35-yarda); validation as in experiment 34. The
decision takes the most likely P placement when it reaches tau, else the most likely G/C at or above
tau, else rejects; saves and wrong switches are counted against ra-cgb, CHASER's current placement.
Judgment fixed beforehand (EXPERIMENTS.md 35): with f35, the P choice beats every fixed placement
(group 5-fold) and the net saves at TAU exceed experiment 34's 4 in both validations.
Usage: python3 rf_candidates.py --cache <.cache dir> --dest <dir>
"""

import argparse
from functools import reduce
import json
from math import gcd, lcm
from pathlib import Path

import numpy as np

from chaser.locality.ca import ca_from_histogram
import rf_devcheck as rd

LINE_BYTES = 32
CAAS_CA_THRESHOLD = 0.178  # the frozen CAAS policy's CA-CSRD threshold (experiment 28)
P_CANDIDATES = ('wfd', 'cgb', 'ra-cgb', 'ra-cgk')
GC_CANDIDATES = ('g', 'c13', 'c112')
CANDIDATES = P_CANDIDATES + GC_CANDIDATES
CURRENT = 'ra-cgb'
CURRENT_ONLY = (CURRENT,) + GC_CANDIDATES
FIXED = ('wfd', 'cgb', 'ra-cgb')
REQUIRED = {'wfd', 'cgb', 'ra-cgb', 'g', 'c112'}
TAUS = rd.TAUS
TAU = rd.TAU
EXP34_NET = 4  # experiment 34: 4 saved, 0 wrong switches at TAU

SET = ['tasks', 'total_u', 'max_u', 'u_cv', 'heavy_tasks', 'period_cv', 'distinct_periods', 'cache_demand',
       'low_affinity_u', 'weighted_one_minus_cls', 'working_set_over_l2', 'max_working_set_kib']
IDS = [f'is_{c}' for c in CANDIDATES]
CANDIDATE = ['max_domain_u', 'group_cores', 'max_group_core_u']
NEW = ['release_crowding', 't0_peak', 'effective_group_core_u', 'other_u_on_group_cores']
YARDA_EXTRA = ['u_p_l1', 'u_p_llc', 'u_p_mem', 'u_one_minus_ca', 'low_ca_u']
FEATURE_SETS = {'f34': SET + IDS + CANDIDATE, 'f35': SET + IDS + CANDIDATE + NEW,
                'f35-noid': SET + CANDIDATE + NEW, 'f35-yarda': SET + IDS + CANDIDATE + NEW + YARDA_EXTRA}
MAIN = 'f35'


def _p3(out):
    return ((out, 'p', 'wfd', 'wfd'), (out, 'p_cgb', 'cgb', 'cgb'), (out, 'p_racgb', 'ra-cgb', 'ra-cgb'))


def _gc(out, c13=None):
    return ((out, 'g', 'wfd', 'g'), (out, 'c2', 'wfd', 'c112')) + (((c13, 'c', 'wfd', 'c13'),) if c13 else ())


# (experiment, runs as (output, results key, build, candidate)); the first output holds the set's YARDA outputs
SOURCES = (('17 and 18 mixed tasks', (('policy-mix-v1', 'p', 'wfd', 'wfd'), ('policy-mix-cls-v1', 'p_cg', 'cg', 'cgb'),
                                      ('policy-mix-cls-v1', 'p_racg', 'ra-cg', 'ra-cgb'),
                                      ('policy-mix-v1', 'g', 'wfd', 'g'), ('policy-mix-v1', 'c2', 'wfd', 'c112'))),
           ('19 placement boundary', _p3('policy-boundary-v1')),
           ('20 768 KiB', _p3('task-count-v1') + _gc('task-count-v1', 'task-count-c13-v1')
            + (('task-count-k-v1', 'p_racgk', 'ra-cgk', 'ra-cgk'),)),
           ('21 32 KiB', _p3('small-memory-v1') + _gc('small-memory-v1')),
           ('23 continuous CLS', _p3('cls-spread-v1') + _gc('cls-spread-v1', 'cls-spread-c13-v1')),
           ('24 32 KiB under load', _p3('small-memory-load-v1') + _gc('small-memory-load-v1', 'small-memory-load-c13-v1')
            + (('small-memory-load-k-v1', 'p_racgk', 'ra-cgk', 'ra-cgk'),)),
           ('25 conflict-miss', _p3('conflict-cls-v2') + _gc('conflict-cls-v2')),
           ('27 32 KiB', _p3('deadline-small-v1') + _gc('deadline-small-v1', 'deadline-small-c13-v1')),
           ('27 768 KiB', _p3('deadline-big-v1') + _gc('deadline-big-v1', 'deadline-big-c13-v1')))


def yarda_tasks(case: Path, tasks) -> list[dict]:
    """The tasks with their cache values replaced by the YARDA outputs of `case` (rf_devcheck's key names)."""
    cls = {r['task_id']: r['cls'] for r in json.loads((case / 'locality.json').read_text())['tasks']}
    out = []
    for t in tasks:
        y = json.loads((case / 'yarda' / f"{t['task_id']}.json").read_text())['tasks'][0]
        out.append(dict(t, cls_planned=cls[t['task_id']],
                        traffic_planned=y['l1']['misses'] / (t['u_planned'] * t['period_ticks'] * 1000),
                        footprint_kib=y['l1']['unique_lines'] * LINE_BYTES / 1024,
                        p_l1=y['l1_first_hit_ratio'], p_llc=y['llc_first_hit_ratio'], p_mem=y['all_cache_miss_ratio'],
                        ca=ca_from_histogram(y['l1']['csrd_histogram'])))
    return out


def release_features(tasks, domains) -> dict:
    """Released work per core of the busiest domain, summed over one hyperperiod's release instants and
    divided by the evenly split sum; and the busiest domain's work per core at time 0 over the shortest period."""
    periods = [t['period_ticks'] for t in tasks]
    hyperperiod, step = reduce(lcm, periods), reduce(gcd, periods)
    where = {core: i for i, d in enumerate(domains) for core in d}
    crowded = even = peak0 = 0.0
    for instant in range(0, hyperperiod, step):
        work = [0.0] * len(domains)
        for t in tasks:
            if instant % t['period_ticks'] == 0:
                work[where[t['core']]] += t['u_planned'] * t['period_ticks']
        busiest = max(w / len(d) for w, d in zip(work, domains))
        crowded += busiest
        even += sum(work) / rd.CORES
        if instant == 0:
            peak0 = busiest
    return dict(release_crowding=crowded / even, t0_peak=peak0 / min(periods))


def group_features(tasks) -> dict:
    """The most loaded group core's U times the request inflation (placement_lib.request_inflation with the
    group cores in use), and the U of the other tasks sharing the group cores. Zero without low-CLS tasks."""
    low = [t for t in tasks if t['cls_planned'] <= rd.CLS_LOW]
    if not low:
        return dict(effective_group_core_u=0.0, other_u_on_group_cores=0.0)
    others = [t for t in tasks if t['cls_planned'] > rd.CLS_LOW]
    cores = {t['core'] for t in low}
    rate = lambda ts: sum(t['traffic_planned'] for t in ts) / len(ts) if ts else 0.0
    kappa = max(1.0, (len(cores) * rate(low) + (rd.CORES - len(cores)) * rate(others)) / rd.L2_REQUESTS_PER_US)
    core_u = max(sum(t['u_planned'] for t in tasks if t['core'] == c) for c in cores)
    return dict(effective_group_core_u=core_u * kappa,
                other_u_on_group_cores=sum(t['u_planned'] for t in others if t['core'] in cores))


def candidate_features(tasks, candidate) -> dict:
    config = candidate if candidate in GC_CANDIDATES else 'p'
    out = {f'is_{c}': int(c == candidate) for c in CANDIDATES}
    out.update({k: v for k, v in rd.config_features(tasks, config).items() if not k.startswith('config_')})
    out.update(release_features(tasks, rd.DOMAINS[config]))
    out.update(group_features(tasks) if config == 'p' else dict(effective_group_core_u=0.0, other_u_on_group_cores=0.0))
    return out


def yarda_extras(tasks) -> dict:
    return dict(u_p_l1=sum(t['u_planned'] * t['p_l1'] for t in tasks),
                u_p_llc=sum(t['u_planned'] * t['p_llc'] for t in tasks),
                u_p_mem=sum(t['u_planned'] * t['p_mem'] for t in tasks),
                u_one_minus_ca=sum(t['u_planned'] * (1 - t['ca']) for t in tasks),
                low_ca_u=sum(t['u_planned'] for t in tasks if t['ca'] <= CAAS_CA_THRESHOLD))


def load(cache: Path, sources=None):
    rows = []
    for source, runs in sources or SOURCES:
        results = {out: rd._results(cache / out / 'results.jsonl') for out, *_ in runs}
        first = runs[0][0]
        for key in results[first]:
            case = lambda out: cache / out / f'{key[0]}/u{round(key[1] * 100):03d}/s{key[2]:02d}'
            wfd = json.loads((case(first) / 'wfd/configuration.json').read_text())
            base = {t['task_id']: t for t in yarda_tasks(case(first), wfd['tasks'])}
            set_features = dict(rd.set_features(list(base.values())), **yarda_extras(list(base.values())))
            group = (wfd['high_load']['seed'] - key[2], key[2])
            for out, result_key, build, candidate in runs:
                state = results[out].get(key, {}).get(result_key, {}).get('state')
                if state not in ('ok', 'deadline'):
                    continue
                placed = json.loads((case(out) / build / 'configuration.json').read_text())['tasks']
                tasks = [dict(base[t['task_id']], core=t['core']) for t in placed]
                rows.append(dict(source=source, case=f'{source}/{key}', group=group, candidate=candidate,
                                 label=int(state == 'ok'), features=dict(set_features, **candidate_features(tasks, candidate))))
    return rows


def decide(probs, tau, allowed=None):
    """The most likely P placement if it reaches tau, else the most likely G/C at or above tau, else None."""
    for family in (P_CANDIDATES, GC_CANDIDATES):
        best = max(((v, c) for c, v in probs.items() if c in family and (allowed is None or c in allowed)), default=None)
        if best and best[0] >= tau:
            return best[1]
    return None


def simulate(cases, tau, allowed=None) -> dict:
    out = dict(cases=len(cases), accepted=0, accepted_met=0, false_accept=0, rejected=0, false_reject=0, chose_other=0,
               saved=0, wrong_switch=0, current_met=0, oracle_met=0, oracle_saves=0)
    for c in cases:
        met = {k: v for k, v in c['met'].items() if allowed is None or k in allowed}
        choice = decide({k: c['probs'][k] for k in met}, tau)
        out['current_met'] += met[CURRENT]
        out['oracle_met'] += any(met.values())
        out['oracle_saves'] += (not met[CURRENT]) and any(met.values())
        if choice is None:
            out['rejected'] += 1
            out['false_reject'] += any(met.values())
            continue
        out['accepted'] += 1
        out['accepted_met'] += met[choice]
        out['false_accept'] += not met[choice]
        if choice != CURRENT:
            out['chose_other'] += 1
            out['saved'] += met[choice] and not met[CURRENT]
            out['wrong_switch'] += met[CURRENT] and not met[choice]
    return out


def choice_accuracy(cases) -> dict:
    """Among sets whose P placements disagree: how often the most likely one met, and each fixed placement."""
    out = dict(cases=0, rf=0, fixed={k: 0 for k in FIXED})
    for c in cases:
        met = {k: v for k, v in c['met'].items() if k in P_CANDIDATES}
        if len(set(met.values())) < 2:
            continue
        best = max(met, key=lambda k: (c['probs'][k], k))
        out['cases'] += 1
        out['rf'] += met[best]
        for k in FIXED:
            out['fixed'][k] += met[k]
    return out


def judge(choice, group_simulation, held_simulation) -> dict:
    net = lambda s: s[str(TAU)]['saved'] - s[str(TAU)]['wrong_switch']
    choosing = choice['rf'] > max(choice['fixed'].values())
    saving = net(group_simulation) > EXP34_NET and net(held_simulation) > EXP34_NET
    return {'choice': choosing, 'saves': saving, 'net_group': net(group_simulation), 'net_held': net(held_simulation),
            'pass': choosing and saving}


def out_of_fold(rows, names, split, seed=0):
    from sklearn.ensemble import RandomForestClassifier
    probs = np.full(len(rows), np.nan)
    for train, test in split(rows):
        model = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=seed, n_jobs=-1)
        model.fit(*rd.matrix([rows[i] for i in train], names))
        probs[test] = model.predict_proba(rd.matrix([rows[i] for i in test], names)[0])[:, 1]
    return probs


def cases_of(rows, probs):
    by_case = {}
    for i, r in enumerate(rows):
        by_case.setdefault(r['case'], {})[r['candidate']] = (bool(r['label']), float(probs[i]))
    return {case: dict(met={c: v[0] for c, v in d.items()}, probs={c: v[1] for c, v in d.items()})
            for case, d in by_case.items() if REQUIRED <= set(d)}


def evaluate(rows, probs) -> dict:
    cases = list(cases_of(rows, probs).values())
    p = [i for i, r in enumerate(rows) if r['candidate'] in P_CANDIDATES]
    return dict(auc_all=rd.auc([r['label'] for r in rows], list(probs)),
                auc_p=rd.auc([rows[i]['label'] for i in p], [probs[i] for i in p]),
                choice=choice_accuracy(cases),
                simulation={str(t): simulate(cases, t) for t in TAUS},
                current_only={str(t): simulate(cases, t, CURRENT_ONLY) for t in TAUS})


def markdown(result) -> str:
    m = result['models']
    f = lambda v: '-' if v is None else f'{v:.3f}'
    lines = ['# RF recommender with several P placement candidates (experiment 35, exploratory)', '',
             f"{result['rows']} rows: " + ', '.join(f"{c} {v['met']}/{v['rows']} met" for c, v in result['by_candidate'].items()), '',
             '## P placement choice where the P placements disagree (sets whose chosen placement met)', '',
             '| feature set | group 5-fold | held out by experiment |', '|---|---:|---:|']
    for name, v in m.items():
        lines.append(f"| RF {name} | {v['group_cv']['choice']['rf']} / {v['group_cv']['choice']['cases']} "
                     f"| {v['held_out']['choice']['rf']} / {v['held_out']['choice']['cases']} |")
    fixed = m[MAIN]['group_cv']['choice']
    for k in FIXED:
        lines.append(f"| always {k} | {fixed['fixed'][k]} / {fixed['cases']} | {fixed['fixed'][k]} / {fixed['cases']} |")
    lines += ['', '## AUC (all rows / P rows)', '', '| feature set | group 5-fold | held out by experiment |', '|---|---|---|']
    for name, v in m.items():
        lines.append(f"| {name} | {f(v['group_cv']['auc_all'])} / {f(v['group_cv']['auc_p'])} "
                     f"| {f(v['held_out']['auc_all'])} / {f(v['held_out']['auc_p'])} |")
    lines += ['', f'## Net saves (saved − wrong switch) at tau {TAU}', '',
              '| feature set | group 5-fold, all candidates | group 5-fold, ra-cgb + G/C | held out, all candidates | held out, ra-cgb + G/C |',
              '|---|---:|---:|---:|---:|']
    net = lambda s: f"{s[str(TAU)]['saved'] - s[str(TAU)]['wrong_switch']} ({s[str(TAU)]['saved']} − {s[str(TAU)]['wrong_switch']})"
    for name, v in m.items():
        lines.append(f"| {name} | {net(v['group_cv']['simulation'])} | {net(v['group_cv']['current_only'])} "
                     f"| {net(v['held_out']['simulation'])} | {net(v['held_out']['current_only'])} |")
    for validation in ('group_cv', 'held_out'):
        v = m[MAIN][validation]
        first = v['simulation'][str(TAUS[0])]
        lines += ['', f"## Decision simulation, {MAIN}, {validation} ({first['cases']} sets; always ra-cgb meets "
                      f"{first['current_met']}, best candidate {first['oracle_met']}, rescuable {first['oracle_saves']})", '',
                  '| tau | candidates | accepted (met / false accept) | rejected (false reject) | chose other | saved | wrong switch |',
                  '|---:|---|---|---|---:|---:|---:|']
        for t in map(str, TAUS):
            for label, s in (('all', v['simulation'][t]), ('ra-cgb + G/C', v['current_only'][t])):
                lines.append(f"| {t} | {label} | {s['accepted']} ({s['accepted_met']} / {s['false_accept']}) "
                             f"| {s['rejected']} ({s['false_reject']}) | {s['chose_other']} | {s['saved']} | {s['wrong_switch']} |")
    lines += ['', f'## Held out by experiment, {MAIN}, tau {TAU}', '',
              '| experiment | sets | saved | wrong switch | false accept | false reject | rescuable |', '|---|---:|---:|---:|---:|---:|---:|']
    for source, s in result['held_out_by_source'].items():
        lines.append(f"| {source} | {s['cases']} | {s['saved']} | {s['wrong_switch']} | {s['false_accept']} | {s['false_reject']} | {s['oracle_saves']} |")
    j = result['judgment']
    lines += ['', f"## Judgment ({MAIN}, tau {TAU}): {'PASS' if j['pass'] else 'FAIL'}", '',
              f"- P choice above every fixed placement (group 5-fold): {j['choice']}",
              f"- net saves above experiment 34's {EXP34_NET} (group {j['net_group']}, held out {j['net_held']}): {j['saves']}", '',
              f'## Feature importance ({MAIN}, all rows)', '']
    lines += [f'- {k}: {v:.3f}' for k, v in list(result['importance'].items())[:12]]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    rows = load(args.cache.resolve())
    result = dict(rows=len(rows), by_candidate={c: dict(rows=sum(r['candidate'] == c for r in rows),
                                                        met=sum(r['label'] for r in rows if r['candidate'] == c))
                                                for c in CANDIDATES},
                  feature_sets=FEATURE_SETS, models={})
    for name, names in FEATURE_SETS.items():
        held = out_of_fold(rows, names, rd.experiment_folds)
        result['models'][name] = dict(group_cv=evaluate(rows, out_of_fold(rows, names, rd.group_folds)),
                                      held_out=evaluate(rows, held))
        if name == MAIN:
            cases = cases_of(rows, held)
            result['held_out_by_source'] = {s: simulate([c for k, c in cases.items() if k.startswith(s + '/')], TAU)
                                            for s, _ in SOURCES if any(k.startswith(s + '/') for k in cases)}
    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1)
    rf.fit(*rd.matrix(rows, FEATURE_SETS[MAIN]))
    result['importance'] = dict(sorted(zip(FEATURE_SETS[MAIN], map(float, rf.feature_importances_)), key=lambda kv: -kv[1]))
    g = result['models'][MAIN]
    result['judgment'] = judge(g['group_cv']['choice'], g['group_cv']['simulation'], g['held_out']['simulation'])
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'rf-candidates.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'rf-candidates.md').write_text(markdown(result))
    print('wrote', args.dest / 'rf-candidates.md')


if __name__ == '__main__':
    main()
