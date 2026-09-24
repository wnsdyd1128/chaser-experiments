"""Export CLP+U RF samples for the frozen final analysis set."""

import argparse
from pathlib import Path

from chaser.final_clp import export_final_clp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('datasets/periodic-final-v1'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = export_final_clp(args.source, args.output)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f'{error}\n')
    print(f"Exported {summary['common_eligible']} CLP workloads per policy; "
          f"feature dimension {summary['feature_dimension']}")


if __name__ == '__main__':
    main()
