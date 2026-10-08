"""Freeze the pre-run RF (experiment 43): choose the calibration, train on every development row, save.

Rows and features as rf_occupancy (experiment 42): experiments 17-25 and 27 with experiment 33's C1+3 runs and
experiment 41's P runs, feature set f35m. Two models are compared with each experiment held out: the RF without
calibration and the same RF with isotonic calibration fitted by group 5-fold inside the training rows; isotonic
is chosen only if it lowers the pooled held-out Brier score by at least MARGIN (choose_calibration, fixed in
EXPERIMENTS.md 43 before the run). The chosen model is trained on every row and saved with its SHA-256, the
feature order, tau, the training table's SHA-256 and a fingerprint of its predictions on the development rows.
The rows come from rf_rows' table (results/rf-model/training-rows.jsonl.gz); the frozen model was fitted on the
same rows read from the raw outputs (training_data in its model-spec.json).
Usage: python3 rf_freeze.py --rows <training rows table> --dest <dir>
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import sklearn

import rf_candidates as rc
import rf_devcheck as rd
import rf_occupancy as ro
import rf_rows

FEATURES = ro.FEATURE_SETS['f35m']
TAU = 0.8
MARGIN = 0.001
TREES, MIN_LEAF, SEED = 500, 3, 0


def matrix(rows, names) -> np.ndarray:
    return np.array([[r['features'][n] for n in names] for r in rows], dtype=float)


def fit(rows, names, calibration, trees=TREES):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupKFold
    x, y = matrix(rows, names), np.array([r['label'] for r in rows])
    forest = RandomForestClassifier(n_estimators=trees, min_samples_leaf=MIN_LEAF, random_state=SEED, n_jobs=-1)
    if calibration == 'none':
        return forest.fit(x, y)
    splits = list(GroupKFold(n_splits=5).split(x, y, groups=[str(r['group']) for r in rows]))
    return CalibratedClassifierCV(forest, method='isotonic', cv=splits).fit(x, y)


def choose_calibration(brier) -> str:
    return 'isotonic' if brier['none'] - brier['isotonic'] >= MARGIN else 'none'


def fingerprint(probs) -> str:
    return hashlib.sha256(json.dumps([round(float(p), 6) for p in probs]).encode()).hexdigest()


def save(model, path: Path) -> None:
    joblib.dump(model, path)


def load_model(path: Path):
    return joblib.load(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def held_out(rows, calibration) -> np.ndarray:
    probs = np.full(len(rows), np.nan)
    for train, test in rd.experiment_folds(rows):
        model = fit([rows[i] for i in train], FEATURES, calibration)
        probs[test] = model.predict_proba(matrix([rows[i] for i in test], FEATURES))[:, 1]
    return probs


def importance(model) -> dict:
    forests = [model] if hasattr(model, 'feature_importances_') else [c.estimator for c in model.calibrated_classifiers_]
    values = np.mean([f.feature_importances_ for f in forests], axis=0)
    return dict(sorted(zip(FEATURES, map(float, values)), key=lambda kv: -kv[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    rows = rf_rows.load(args.rows)
    y = np.array([r['label'] for r in rows])
    comparison = {}
    for calibration in ('none', 'isotonic'):
        p = held_out(rows, calibration)
        cases = list(rc.cases_of(rows, p).values())
        comparison[calibration] = dict(brier=float(np.mean((p - y) ** 2)), auc=rd.auc(list(y), list(p)),
                                       p_auc=ro.p_auc_by_source(rows, list(p)),
                                       decision=rc.simulate(cases, TAU, rc.CURRENT_ONLY))
    chosen = choose_calibration({k: v['brier'] for k, v in comparison.items()})
    model = fit(rows, FEATURES, chosen)
    args.dest.mkdir(parents=True, exist_ok=True)
    path = args.dest / 'model.joblib'
    save(model, path)
    probs = load_model(path).predict_proba(matrix(rows, FEATURES))[:, 1]
    spec = dict(model='RF f35m', calibration=chosen, tau=TAU, trees=TREES, min_samples_leaf=MIN_LEAF, seed=SEED,
                features=FEATURES, candidates=list(rc.CANDIDATES), decision_candidates=list(rc.CURRENT_ONLY),
                model_sha256=sha256(path), model_bytes=path.stat().st_size, rows=len(rows),
                rows_by_candidate={c: sum(r['candidate'] == c for r in rows) for c in rc.CANDIDATES},
                prediction_fingerprint=fingerprint(probs),
                training_data={args.rows.name: sha256(args.rows)},
                versions=dict(sklearn=sklearn.__version__, numpy=np.__version__, joblib=joblib.__version__),
                created_utc=datetime.now(timezone.utc).isoformat(), comparison=comparison, importance=importance(model))
    (args.dest / 'model-spec.json').write_text(json.dumps(spec, indent=1) + '\n')
    lines = ['# Frozen pre-run RF (experiment 43)', '',
             f"calibration **{chosen}**, tau {TAU}, {len(rows)} rows, {len(FEATURES)} features, model {spec['model_bytes'] / 1e6:.1f} MB",
             f"model SHA-256 `{spec['model_sha256']}`, prediction fingerprint `{spec['prediction_fingerprint']}`", '',
             '| calibration | held-out Brier | held-out AUC (all rows) | P-row AUC (all) | decision at tau: accepted met / false accept / false reject / saved / wrong switch |',
             '|---|---:|---:|---:|---|']
    for k, v in comparison.items():
        d = v['decision']
        lines.append(f"| {k} | {v['brier']:.4f} | {v['auc']:.4f} | {v['p_auc']['all']:.4f} | "
                     f"{d['accepted_met']} / {d['false_accept']} / {d['false_reject']} / {d['saved']} / {d['wrong_switch']} |")
    lines += ['', '## Feature importance (frozen model)', ''] + [f'- {k}: {v:.3f}' for k, v in spec['importance'].items()]
    (args.dest / 'model-spec.md').write_text('\n'.join(lines) + '\n')
    print('wrote', args.dest / 'model-spec.md')


if __name__ == '__main__':
    main()
