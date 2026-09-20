"""Collect host Lackey traces and validate filtered S1 accesses against YARDA."""

import argparse
from pathlib import Path
import subprocess

from chaser.s1_execution import run_execution_suite
from chaser.s1_workloads import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, dest='output_dir')
    parser.add_argument('--cases', nargs='+', choices=[c['id'] for c in cases()], dest='case_ids')
    parser.add_argument('--sweeps', type=int, default=3)
    parser.add_argument('--max-references', type=int, default=250000)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--max-trace-bytes', type=int, default=512 * 1024 * 1024)
    try:
        report = run_execution_suite(**vars(parser.parse_args()))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f'{error}\n')
    if report['status'] != 'ok':
        parser.exit(1)


if __name__ == '__main__':
    main()
