"""Build four JSONL tables from locality, workload and measurement records."""

import argparse
import json
from pathlib import Path

from chaser.dataset.builder import Workload, build_dataset, freeze_split, write_dataset
from chaser.dataset.labeling import Measurement
from chaser.dataset.splits import LEGACY_POLICY, TASKSET_POLICY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON: cases, workloads, measurements, provenance')
    parser.add_argument('--split', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--split-policy', choices=(TASKSET_POLICY, LEGACY_POLICY),
                        default=TASKSET_POLICY)
    parser.add_argument('--expected-runs', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError(f'Dataset already exists: {args.output}')
        data = json.loads(args.input.read_text())
        workloads = [Workload(**row) for row in data['workloads']]
        measurements = [Measurement(**row) for row in data['measurements']]
        split = freeze_split(args.split, workloads, seed=args.seed, policy=args.split_policy)
        dataset = build_dataset(data['cases'], workloads, measurements, data['provenance'],
                                split, expected_runs=args.expected_runs)
        write_dataset(args.output, dataset)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f'{error}\n')
    print(f"Exported {len(dataset['rf_samples'])} RF samples; "
          f"excluded {len(dataset['metadata']['excluded'])} workloads")


if __name__ == '__main__':
    main()
