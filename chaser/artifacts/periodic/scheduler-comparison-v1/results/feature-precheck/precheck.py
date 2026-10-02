"""Feature pre-check on finished studies: can static task-set features pick the better choice?

Inputs are the exported bundles in results/ (results*.jsonl, per-set.jsonl.gz). Features come
from taskset_features.py and use no run result. The plan's baseline RF (100 trees, no depth
limit, max_features sqrt, seeds 42-46) is trained per representation without tuning.

Decisions (label = lowest TAT, exact ties by TET; regret = chosen TAT / best TAT - 1):
  placement  Partitioned grouped vs mixed; experiments 5-8 pooled, exact duplicate sets dropped
  hl-policy  Partitioned informed vs WFD; experiment 9
  hl-family  best Partitioned vs best Clustered vs Global; experiment 9. A configuration that
             missed a deadline is infeasible; choosing a family with none feasible is a failure.
Learners:
  classifier  hard label
  weighted    hard label, sample weight = loss of the wrong choice (margin, capped at 1)
  regressor   predicts every option's regret (infeasible: 1) and picks the smallest
Cross-validation:
  set        GroupKFold(10) over set ids, which the CRN draws share across conditions:
             unseen task sets of conditions present in training
  condition  each condition held out in turn: a condition absent from training
Collision audit: pairs whose min-max-scaled features all differ by < 1% of the range while
their labels differ, both with a margin of at least 1%.
Outputs (--output): protocol.json, samples.jsonl, results.json, predictions.jsonl (every
method's choices per seed), collisions.json, summary.md and snapshots of the two scripts.
Usage: python3 precheck.py --output <dir> [--jobs N]
"""

import argparse
from dataclasses import dataclass, field
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from joblib import Parallel, delayed
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import GroupKFold

from taskset_features import LINE_BYTES, REPRESENTATIONS, Task, best_choice

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / 'results'
SEEDS = (42, 43, 44, 45, 46)
RF = dict(n_estimators=100, max_depth=None, min_samples_leaf=1, max_features='sqrt', n_jobs=1)
LEARNERS = ('classifier', 'weighted', 'regressor')
SCHEMES = ('set', 'condition')
MARGIN = 0.01  # below this TAT margin a label is a near-tie
NEAR = 0.01  # collision: every scaled feature within 1% of its range
CAP = 1.0  # regret given to an infeasible option, and the cap on sample weights
OPTIONS = {'placement': ('mixed', 'grouped'), 'hl-policy': ('WFD', 'informed'),
           'hl-family': ('Partitioned', 'Clustered', 'Global')}


@dataclass
class Sample:
    study: str
    condition: str
    set_id: int
    cell: dict
    tasks: list
    tat: tuple  # per option in ns; inf when infeasible
    tet: tuple
    label: int = field(init=False)

    def __post_init__(self):
        self.label = best_choice(self.tat, self.tet)

    @property
    def margin(self) -> float:
        best, second = sorted(self.tat)[:2]
        return second / best - 1


def ok(entry) -> bool:
    return isinstance(entry, dict) and entry.get('state', entry.get('status')) == 'ok'


def read_rows(study: str, name: str = 'results.jsonl') -> list[dict]:
    return [json.loads(line) for line in (RESULTS / study / name).read_text().splitlines()]


def read_per_set(*studies: str) -> dict:
    out = {}
    for study in studies:
        with gzip.open(RESULTS / study / 'per-set.jsonl.gz', 'rt') as stream:
            for line in stream:
                record = json.loads(line)
                out.setdefault(record['path'], record['content'])
    return out


def bimodal_tasks(row: dict, locality: dict, configuration: dict) -> list[Task]:
    """Join yarda counts and periods to the row's measured isolated CPU, checking task order."""
    analysed = sorted(locality['tasks'], key=lambda t: t['task_id'])
    spec = sorted(configuration['tasks'], key=lambda t: t['task_id'])
    tasks = []
    for t, s, cls, cpu, misses in zip(analysed, spec, row['cls'], row['isolated_cpu_ns'],
                                      row['l1_misses'], strict=True):
        if t['task_id'] != s['task_id'] or abs(t['cls'] - cls) > 1e-9 or t['l1_misses'] != misses:
            raise ValueError(f"locality does not match the result row at {t['task_id']}")
        period_ms = s['period_ticks']  # 1 ms tick (measurement contract v3)
        accesses = t['accesses']
        tasks.append(Task(u=cpu / (period_ms * 1e6), period_ms=period_ms, cls=t['cls'],
                          p_l1=t['l1_hits'] / accesses, p_llc=t['llc_hits'] / accesses,
                          p_miss=t['memory'] / accesses, traffic=t['l1_misses'] / (cpu / 1e3),
                          footprint_kib=t['memory'] * LINE_BYTES / 1024))
    return tasks


# (study, bundle, results file, set directory, condition, cell keys)
PLACEMENT_STUDIES = (
    ('exp5', 'cls-bimodal-ext', 'results-combined.jsonl',
     lambda r: f"{r['traffic']}/p{round(r['mean'] * 100):03d}/cv{round(r['cv'] * 100):02d}/s{r['set_id']:02d}",
     lambda r: f"{r['traffic']} p={r['mean']:g}", lambda r: dict(traffic=r['traffic'], p=r['mean'], cv=r['cv'])),
    ('exp6', 'load-level', 'results.jsonl',
     lambda r: f"as-is/t{r['period']:03d}/p050/cv10/s{r['set_id']:02d}",
     lambda r: f"period {r['period']} ms", lambda r: dict(period=r['period'])),
    ('exp7', 'u-imbalance', 'results.jsonl',
     lambda r: f"as-is/u{round(r['u_cv'] * 100):03d}/p050/cv10/s{r['set_id']:02d}",
     lambda r: f"U CV {r['u_cv']:g}", lambda r: dict(u_cv=r['u_cv'])),
    ('exp8', 'footprint', 'results.jsonl', lambda r: f"{r['kind']}/s{r['set_id']:02d}",
     lambda r: r['kind'], lambda r: dict(kind=r['kind'])),
)


def placement_samples() -> tuple[list[Sample], int]:
    """Sets with both placements measured; drops sets repeated in another study (same runs)."""
    per_set = read_per_set('cls-bimodal', 'cls-bimodal-ext', 'load-level', 'u-imbalance', 'footprint')
    samples, seen, dropped = [], set(), 0
    for study, bundle, name, directory, condition, cell in PLACEMENT_STUDIES:
        for row in read_rows(bundle, name):
            if not (ok(row['p']) and ok(row['p_grp'])):
                continue
            key = (tuple(row['cls']), tuple(row['l1_misses']),
                   *(row[c][m] for c in ('p', 'p_grp') for m in ('tat_ns', 'tet_ns')))
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            base = directory(row)
            tasks = bimodal_tasks(row, per_set[f'{base}/locality.json'],
                                  per_set[f'{base}/mixed/configuration.json'])
            samples.append(Sample(study, condition(row), row['set_id'], cell(row), tasks,
                                  (row['p']['tat_ns'], row['p_grp']['tat_ns']),
                                  (row['p']['tet_ns'], row['p_grp']['tet_ns'])))
    return samples, dropped


def cyclic_task(spec: dict) -> Task:
    """Experiment 9 has no yarda run: a cyclic L1-resident sweep, first pass cold, rest L1 hits."""
    sweeps, lines, period_ms, u = spec['sweeps'], spec['distinct'], spec['period_ticks'], spec['u_planned']
    return Task(u=u, period_ms=period_ms, cls=1 - 1 / sweeps, p_l1=1 - 1 / sweeps, p_llc=0.0,
                p_miss=1 / sweeps, traffic=lines / (u * period_ms * 1e3),
                footprint_kib=lines * LINE_BYTES / 1024)


def high_load_samples() -> dict[str, list[Sample]]:
    per_set = read_per_set('high-load')
    out = {'hl-policy': [], 'hl-family': []}
    for row in read_rows('high-load'):
        spec = per_set[f"{row['heaviness']}/u{round(row['load'] * 100):03d}/s{row['set_id']:02d}/wfd/configuration.json"]
        tasks = [cyclic_task(t) for t in sorted(spec['tasks'], key=lambda t: t['task_id'])]
        condition = f"{row['heaviness']} U/core {row['load']:g}"
        cell = dict(heaviness=row['heaviness'], load=row['load'])
        if not (ok(row['p']) and ok(row['p_inf'])):
            raise ValueError(f'Partitioned failed in {condition} set {row["set_id"]}')
        out['hl-policy'].append(Sample('exp9', condition, row['set_id'], cell, tasks,
                                       (row['p']['tat_ns'], row['p_inf']['tat_ns']),
                                       (row['p']['tet_ns'], row['p_inf']['tet_ns'])))
        tat, tet = [], []
        for family in (('p', 'p_inf'), ('c', 'c2', 'c_inf'), ('g',)):
            feasible = [(row[k]['tat_ns'], row[k]['tet_ns']) for k in family if ok(row[k])]
            best = min(feasible) if feasible else (float('inf'), float('inf'))
            tat.append(best[0])
            tet.append(best[1])
        out['hl-family'].append(Sample('exp9', condition, row['set_id'], cell, tasks, tuple(tat), tuple(tet)))
    return out


def tables(samples: list[Sample]):
    tat = np.array([s.tat for s in samples], dtype=float)
    regrets = tat / tat.min(axis=1, keepdims=True) - 1  # inf for infeasible options
    labels = np.array([s.label for s in samples])
    margins = np.minimum(np.array([s.margin for s in samples]), CAP)
    return tat, regrets, labels, margins


def splits(samples: list[Sample], scheme: str) -> list[tuple[np.ndarray, np.ndarray]]:
    if scheme == 'set':
        groups = [s.set_id for s in samples]
        return list(GroupKFold(n_splits=10).split(np.zeros(len(samples)), groups=groups))
    conditions = sorted({(s.study, s.condition) for s in samples})
    members = np.array([(s.study, s.condition) for s in samples], dtype=object)
    return [(np.flatnonzero([tuple(m) != c for m in members]), np.flatnonzero([tuple(m) == c for m in members]))
            for c in conditions]


def predict(learner, X, regrets, labels, margins, folds, seed) -> np.ndarray:
    choices = np.empty(len(X), dtype=int)
    for train, test in folds:
        if learner == 'regressor':
            model = RandomForestRegressor(random_state=seed, **RF)
            model.fit(X[train], np.minimum(regrets[train], CAP))
            choices[test] = model.predict(X[test]).argmin(axis=1)
            continue
        model = RandomForestClassifier(random_state=seed, **RF)
        weight = margins[train] if learner == 'weighted' else None
        model.fit(X[train], labels[train], sample_weight=weight)
        choices[test] = model.predict(X[test])
    return choices


def baselines(regrets, labels, folds, options) -> dict[str, np.ndarray]:
    out = {'oracle': labels.copy()}
    for k, name in enumerate(options):
        out[f'always {name}'] = np.full(len(labels), k)
    fixed = np.empty(len(labels), dtype=int)
    for train, test in folds:
        fixed[test] = np.minimum(regrets[train], CAP).mean(axis=0).argmin()
    out['fixed (train)'] = fixed
    return out


def metrics(choices, tat, regrets, labels, margins) -> dict:
    chosen = regrets[np.arange(len(choices)), choices]
    feasible = np.isfinite(chosen)
    clear = margins >= MARGIN
    hit = choices == labels
    return dict(n=len(choices), infeasible=int((~feasible).sum()),
                mean_regret=float(chosen[feasible].mean()) if feasible.any() else None,
                p95_regret=float(np.percentile(chosen[feasible], 95)) if feasible.any() else None,
                max_regret=float(chosen[feasible].max()) if feasible.any() else None,
                accuracy=float(hit.mean()), clear_n=int(clear.sum()),
                clear_accuracy=float(hit[clear].mean()) if clear.any() else None,
                mean_tat_ms=float(tat[np.arange(len(choices)), choices][feasible].mean() / 1e6))


def average(runs: list[dict]) -> dict:
    out = {}
    for key in runs[0]:
        values = [r[key] for r in runs if r[key] is not None]
        out[key] = float(np.mean(values)) if values else None
    return out


def evaluate(decision, samples, jobs) -> tuple[dict, list[dict]]:
    tat, regrets, labels, margins = tables(samples)
    options = OPTIONS[decision]
    matrices = {rep: np.array([build(s.tasks) for s in samples]) for rep, build in REPRESENTATIONS.items()}
    conditions = np.array([s.condition for s in samples], dtype=object)
    results, records = {}, []
    for scheme in SCHEMES:
        folds = splits(samples, scheme)
        work = [(rep, learner, seed) for rep in REPRESENTATIONS for learner in LEARNERS for seed in SEEDS]
        predicted = Parallel(n_jobs=jobs)(
            delayed(predict)(learner, matrices[rep], regrets, labels, margins, folds, seed)
            for rep, learner, seed in work)
        methods = {name: [c] for name, c in baselines(regrets, labels, folds, options).items()}
        for (rep, learner, seed), choices in zip(work, predicted):
            methods.setdefault(f'{rep} / {learner}', []).append(choices)
        results[scheme] = {}
        for name, runs in methods.items():
            per_condition = {}
            for condition in sorted(set(conditions)):
                mask = conditions == condition
                per_condition[condition] = average([metrics(c[mask], tat[mask], regrets[mask], labels[mask],
                                                            margins[mask]) for c in runs])
            results[scheme][name] = dict(
                mean=average([metrics(c, tat, regrets, labels, margins) for c in runs]),
                per_condition=per_condition)
            records.append(dict(decision=decision, scheme=scheme, method=name,
                                choices=[c.tolist() for c in runs]))
    return results, records


NAMED_PAIRS = {
    'placement': {
        'exp5 traffic as-is vs matched (same p, CV, set)':
            lambda a, b: a.study == b.study == 'exp5' and a.set_id == b.set_id
            and a.cell['p'] == b.cell['p'] and a.cell['cv'] == b.cell['cv']
            and {a.cell['traffic'], b.cell['traffic']} == {'as-is', 'matched'},
        'exp8 SH vs BH (same set)':
            lambda a, b: a.study == b.study == 'exp8' and a.set_id == b.set_id
            and {a.cell['kind'], b.cell['kind']} == {'SH', 'BH'},
        'exp8 SL vs BL (same set)':
            lambda a, b: a.study == b.study == 'exp8' and a.set_id == b.set_id
            and {a.cell['kind'], b.cell['kind']} == {'SL', 'BL'},
    },
}


def collisions(decision, samples) -> dict:
    labels = np.array([s.label for s in samples])
    margins = np.array([s.margin for s in samples])
    named = NAMED_PAIRS.get(decision, {})
    named_index = {name: [(i, j) for i in range(len(samples)) for j in range(i + 1, len(samples))
                          if test(samples[i], samples[j])] for name, test in named.items()}
    out = {}
    for rep, build in REPRESENTATIONS.items():
        X = np.array([build(s.tasks) for s in samples])
        span = X.max(axis=0) - X.min(axis=0)
        Z = (X - X.min(axis=0)) / np.where(span > 0, span, 1)
        near, conflicts, kinds = 0, 0, {}
        for i in range(len(Z) - 1):
            close = np.flatnonzero(np.abs(Z[i + 1:] - Z[i]).max(axis=1) < NEAR) + i + 1
            near += len(close)
            for j in close:
                if labels[i] != labels[j] and margins[i] >= MARGIN and margins[j] >= MARGIN:
                    conflicts += 1
                    pair = ' | '.join(sorted(f'{samples[k].study} {samples[k].condition}' for k in (i, j)))
                    kinds[pair] = kinds.get(pair, 0) + 1
        named_out = {}
        for name, pairs in named_index.items():
            distance = [float(np.abs(Z[i] - Z[j]).max()) for i, j in pairs]
            named_out[name] = dict(pairs=len(pairs), near=int(sum(d < NEAR for d in distance)),
                                   labels_differ=int(sum(labels[i] != labels[j] for i, j in pairs)),
                                   median_max_scaled_difference=float(np.median(distance)) if distance else None)
        out[rep] = dict(dimensions=int(X.shape[1]), near_pairs=near, conflicting_pairs=conflicts,
                        conflicts_by_condition=dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
                        named=named_out)
    return out


def pct(value) -> str:
    return '-' if value is None else f'{value * 100:.2f}%'


def summary(protocol, results, collided) -> str:
    lines = ['# Feature pre-check', '',
             'Columns: mean / p95 / max TAT regret of the chosen option (chosen TAT / best TAT - 1),',
             'accuracy on all sets and on sets whose TAT margin is at least 1%, infeasible choices.', '']
    for decision, by_scheme in results.items():
        info = protocol['decisions'][decision]
        lines += [f"## {decision}: {' vs '.join(info['options'])}", '',
                  f"{info['samples']} sets; labels {info['label_counts']}; near-ties (<1%) {info['near_ties']}", '']
        for scheme, methods in by_scheme.items():
            lines += [f'### {scheme}-level cross-validation', '',
                      '| method | mean | p95 | max | accuracy | clear accuracy | infeasible |',
                      '|---|---:|---:|---:|---:|---:|---:|']
            for name, value in methods.items():
                m = value['mean']
                lines.append(f"| {name} | {pct(m['mean_regret'])} | {pct(m['p95_regret'])} | {pct(m['max_regret'])} | "
                             f"{pct(m['accuracy'])} | {pct(m['clear_accuracy'])} | {m['infeasible']:.1f} |")
            lines.append('')
        if decision in collided:
            lines += ['### Collision audit', '',
                      '| representation | dims | near pairs | conflicting pairs | ' +
                      ' | '.join(f'{k}: near/pairs' for k in NAMED_PAIRS.get(decision, {})) + ' |',
                      '|---|---:|---:|---:|' + '---:|' * len(NAMED_PAIRS.get(decision, {}))]
            for rep, c in collided[decision].items():
                named = ' | '.join(f"{v['near']}/{v['pairs']}" for v in c['named'].values())
                lines.append(f"| {rep} | {c['dimensions']} | {c['near_pairs']} | {c['conflicting_pairs']} | {named} |")
            lines.append('')
    return '\n'.join(lines) + '\n'


def manifest_hashes() -> dict:
    out = {}
    for bundle in ('cls-bimodal', 'cls-bimodal-ext', 'load-level', 'u-imbalance', 'footprint', 'high-load'):
        for name in ('results.jsonl', 'results-combined.jsonl', 'per-set.jsonl.gz'):
            path = RESULTS / bundle / name
            if path.exists():
                out[f'{bundle}/{name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    placement, dropped = placement_samples()
    decisions = {'placement': placement, **high_load_samples()}
    first = decisions['placement'][0].tasks
    protocol = dict(
        design='feature-precheck', inputs=manifest_hashes(), seeds=SEEDS, rf=RF, learners=LEARNERS,
        schemes=SCHEMES, margin=MARGIN, near=NEAR, cap=CAP,
        representations={rep: len(build(first)) for rep, build in REPRESENTATIONS.items()},
        decisions={name: dict(options=OPTIONS[name], samples=len(s),
                              label_counts={OPTIONS[name][k]: int(sum(x.label == k for x in s))
                                            for k in range(len(OPTIONS[name]))},
                              near_ties=int(sum(x.margin < MARGIN for x in s)),
                              conditions=sorted({f'{x.study} {x.condition}' for x in s}))
                   for name, s in decisions.items()},
        dropped_duplicate_sets=dropped)
    (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    with open(args.output / 'samples.jsonl', 'w') as stream:
        for name, s in decisions.items():
            for index, x in enumerate(s):
                stream.write(json.dumps(dict(decision=name, index=index, study=x.study, condition=x.condition,
                                             set_id=x.set_id, cell=x.cell, tat_ns=x.tat, tet_ns=x.tet,
                                             label=x.label, margin=x.margin)) + '\n')
    results, records = {}, []
    for name, s in decisions.items():
        results[name], rec = evaluate(name, s, args.jobs)
        records += rec
        print(f'{name}: evaluated', flush=True)
    collided = {'placement': collisions('placement', decisions['placement'])}
    (args.output / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
    (args.output / 'collisions.json').write_text(json.dumps(collided, indent=1) + '\n')
    with open(args.output / 'predictions.jsonl', 'w') as stream:
        for record in records:
            stream.write(json.dumps(record) + '\n')
    (args.output / 'summary.md').write_text(summary(protocol, results, collided))
    for script in ('precheck.py', 'taskset_features.py'):
        shutil.copyfile(HERE / script, args.output / script)
    print('wrote', args.output)


if __name__ == '__main__':
    main()
