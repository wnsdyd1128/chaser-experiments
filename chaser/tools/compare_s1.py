"""Compare full-stream Global RD and CSRD against a cold LRU model reference."""

import argparse
from pathlib import Path
import subprocess

from chaser.s1.evaluation import evaluate_task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id', help='Single matching function in the prepared APE')
    for name in ('ape', 'elf', 'cache', 'source', 'executable'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, dest='output_dir')
    for name in ('max-source-accesses', 'max-line-references', 'max-cumulative-loop-iterations'):
        parser.add_argument('--' + name, type=int, required=True)
    parser.add_argument('--timeout', type=float, default=60, help='Seconds per analyzer execution')
    args = parser.parse_args()
    try:
        report = evaluate_task(**vars(args))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f'{error}\n')
    print(f"{report['task_id']}: {report['status']}; {report['modeled_accesses']} modeled references; "
          f"report: {args.output_dir / 'comparison.json'}")
    if report['status'] == 'mismatch':
        parser.exit(1)


if __name__ == '__main__':
    main()
