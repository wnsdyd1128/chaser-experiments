"""Check chaser.policy.pfirst against the development data and the frozen RF (step 2 of the confirmatory plan).

For every development set (rf_occupancy's sources) this rebuilds the task values from the plan and the YARDA
outputs with chaser.policy.pfirst.inputs, then compares
  - the U-balanced and CHASER (ra-cgb) mappings with the stored wfd and ra-cgb configurations (experiments
    17 and 18 used ra-cg and experiment 41 placed on target U, so their mappings are not compared),
  - every candidate row's f35m features with the experiment code's rows (exact equality),
  - the frozen model's probability on the framework row with the one on the experiment row,
and times the full decision per set. Run with PYTHONPATH holding the workspace root (main chaser package).
Usage: python3 pfirst_check.py --cache <.cache dir> --policy <frozen policy dir> --dest <json>
"""

import argparse
import json
from pathlib import Path
import time

import numpy as np

from chaser.policy.pfirst import decision, features, inputs, placement
import rf_candidates as rc
import rf_occupancy as ro

SKIP_MAPPING = ('17 and 18 mixed tasks', '41 memory cost')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    cache = args.cache.resolve()
    rows = rc.load(cache, sources=ro.SOURCES)
    ro.add_occupancy(rows, ro.demands(cache))
    policy = decision.Policy(args.policy)
    names = policy.names
    by_case = {}
    for r in rows:
        by_case.setdefault(r['case'], []).append(r)
    first = {s: runs[0][0] for s, runs in ro.SOURCES}
    builds = {s: {cand: (out, build) for out, _, build, cand in runs} for s, runs in ro.SOURCES}
    out = dict(sets=0, rows=0, mapping=dict(wfd=[0, 0], chaser=[0, 0]), feature_mismatch=[], max_probability_gap=0.0,
               decide_seconds=[])
    for case_id, case_rows in by_case.items():
        source, key = case_id.split('/', 1)
        h, load, k = eval(key)
        case_dir = lambda o: cache / o / f'{h}/u{round(load * 100):03d}/s{k:02d}'
        config = json.loads((case_dir(first[source]) / 'wfd/configuration.json').read_text())
        tasks = inputs.load_case(case_dir(first[source]), [dict(task_id=t['task_id'], u=t['u_planned'], period=t['period_ticks'])
                                                         for t in config['tasks']])
        seed = config['high_load']['seed']
        cores = lambda cand: [t['core'] for t in json.loads((case_dir(builds[source][cand][0]) / builds[source][cand][1]
                                                              / 'configuration.json').read_text())['tasks']]
        if source not in SKIP_MAPPING:
            out['mapping']['wfd'][0] += placement.wfd(tasks) == cores('wfd')
            out['mapping']['wfd'][1] += 1
            if any(r['candidate'] == 'ra-cgb' for r in case_rows):
                out['mapping']['chaser'][0] += placement.release_aware_grouped(tasks, seed) == cores('ra-cgb')
                out['mapping']['chaser'][1] += 1
        mine, theirs = [], []
        for r in case_rows:
            row = features.row(tasks, cores(r['candidate']), r['candidate'], names)
            exp = [float(r['features'][n]) for n in names]
            if row != exp:
                out['feature_mismatch'].append(dict(case=case_id, candidate=r['candidate'],
                                                    features=[n for n, a, b in zip(names, row, exp) if a != b]))
            mine.append(row)
            theirs.append(exp)
        gap = np.abs(policy.model.predict_proba(np.array(mine))[:, 1] - policy.model.predict_proba(np.array(theirs))[:, 1])
        out['max_probability_gap'] = max(out['max_probability_gap'], float(gap.max()))
        start = time.perf_counter()
        decision.decide(tasks, policy, seed)
        out['decide_seconds'].append(time.perf_counter() - start)
        out['sets'] += 1
        out['rows'] += len(case_rows)
    t = out.pop('decide_seconds')
    out['decide_seconds'] = dict(median=float(np.median(t)), p95=float(np.quantile(t, 0.95)), max=float(max(t)))
    out['feature_mismatch_rows'] = len(out['feature_mismatch'])
    out['feature_mismatch'] = out['feature_mismatch'][:20]
    args.dest.parent.mkdir(parents=True, exist_ok=True)
    args.dest.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'feature_mismatch'}))


if __name__ == '__main__':
    main()
