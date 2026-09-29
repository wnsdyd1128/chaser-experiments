"""Validate all 30 original PolyBench MEDIUM kernels and execute yarda_cpp."""

import argparse
from pathlib import Path

from chaser.periodic.polybench.suite import execution_passed, verify_suite


def main() -> None:
    """Expose suite verification separately from periodic measurement runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--periodic', action='store_true', help='also build/analyze G/C/P RTEMS ELFs')
    parser.add_argument('--timeout', type=float, default=120, help='seconds per analysis process (also native validation without --periodic)')
    args = parser.parse_args()
    if not 0 < args.timeout < float('inf'):
        parser.error('--timeout must be positive and finite')
    report = verify_suite(args.output, periodic=args.periodic, timeout=args.timeout)
    if not execution_passed(report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
