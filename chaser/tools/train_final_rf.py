"""Train frozen 3x3 RF comparisons with a shared validation search budget."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import traceback

import numpy
import sklearn

from chaser.final_clp import POLICIES
from chaser.rf_experiment import GRID, REPRESENTATIONS, SEEDS, load_samples, train_cell


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


def _log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'[{stamp}] {message}', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path('datasets/periodic-final-v1'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    manifest = {'status': 'preparing', 'source': str(args.source.resolve()),
                'seeds': SEEDS, 'workers': args.workers,
                'grid': [{'candidate_id': i, 'max_depth': c[0],
                          'min_samples_leaf': c[1], 'max_features': c[2],
                          'class_weight': c[3]} for i, c in enumerate(GRID)],
                'fit_count_expected': len(POLICIES) * len(REPRESENTATIONS) * len(GRID) * len(SEEDS),
                'split_counts': {'train': 120, 'validation': 41, 'test': 37},
                'selection': 'minimum mean validation TAT regret over five seeds; '
                             'tie: maximum mean macro-F1, then candidate ID',
                'sklearn_version': sklearn.__version__,
                'numpy_version': numpy.__version__,
                'started_at': datetime.now(timezone.utc).isoformat()}
    _write_json(args.output / 'run.json', manifest)
    try:
        samples, provenance = load_samples(args.source)
        manifest['analysis_set_id'] = provenance['lock']['analysis_set_id']
        manifest['source_hashes'] = provenance['lock']['source_hashes']
        manifest['clp_file_hashes'] = provenance['clp_summary']['files']
        manifest['status'] = 'running'
        _write_json(args.output / 'run.json', manifest)
        _log(f"Validated {manifest['analysis_set_id']}; 9 cells x 36 candidates x 5 seeds; "
             f'{args.workers} workers')
        results = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(train_cell, policy, rep,
                                   samples[(policy, rep)], args.output): (policy, rep)
                       for policy in POLICIES for rep in REPRESENTATIONS}
            for future in as_completed(futures):
                policy, rep = futures[future]
                result = future.result()
                results.append(result)
                manifest['completed_cells'] = len(results)
                manifest['completed_fits'] = sum(r['fit_count'] for r in results)
                _write_json(args.output / 'run.json', manifest)
                _log(f"{len(results)}/9 cells; {manifest['completed_fits']}/1620 fits; "
                     f'{policy}/{rep} selected candidate {result["best_candidate_id"]}')
        manifest['status'] = 'complete'
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        _write_json(args.output / 'summary.json', {'analysis_set_id': manifest['analysis_set_id'],
                                                   'cells': sorted(results, key=lambda r: (
                                                       r['policy'], r['representation']))})
        _write_json(args.output / 'run.json', manifest)
        _log('COMPLETE: 1620 fits; baseline and tuned validation/test artifacts saved')
        return 0
    except Exception:
        manifest['status'] = 'failed'
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['error'] = traceback.format_exc()
        _write_json(args.output / 'run.json', manifest)
        _log('FAILED; inspect run.json and traceback below')
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
