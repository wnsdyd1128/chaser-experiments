"""Compare a validated host S1 suite with stock Cachegrind."""
import argparse
from pathlib import Path
import subprocess
from chaser.s1.cachegrind import run_cachegrind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, dest='input_dir')
    parser.add_argument('--output', type=Path, required=True, dest='output_dir')
    parser.add_argument('--cold-prefix', type=Path, help='S1-patched Valgrind install prefix')
    parser.add_argument('--timeout', type=float, default=120)
    try:
        report = run_cachegrind(**vars(parser.parse_args()))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f'{error}\n')
    if report['status'] != 'ok':
        parser.exit(1)


if __name__ == '__main__':
    main()
