"""Recompute CLS from existing C++ exports without rerunning the analyzer."""

import argparse
import json
from pathlib import Path

from chaser.cls import DEFAULT_ALPHAS
from tools.export_locality import ROOT, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alpha', default=','.join(map(str, DEFAULT_ALPHAS)),
                        help='Comma-separated nonnegative alpha values')
    parser.add_argument('--output', type=Path, default=ROOT / 'exports/locality.json')
    args = parser.parse_args()
    try:
        alphas = tuple(float(value) for value in args.alpha.split(','))
        result = summary(alphas)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
