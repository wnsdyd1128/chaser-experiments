"""The RF's development rows as one table, the training input once the development experiments' raw outputs are removed.

Rows as rf_occupancy builds them (experiments 17-25 and 27 with experiment 33's C1+3 runs and experiment 41's P runs,
in that order): source, case, group, candidate, label and features, the rf_candidates features with the memory demand
M and D + M, plus rf_stats' distribution statistics on the rows of rf_candidates.SOURCES. Read by rf_freeze
(experiment 43), rf_occupancy (42) and memcost_analysis (41's predictors). One JSON object per line, gzip with a fixed
header; floats round-trip exactly, so a model fitted on the table equals one fitted on the raw outputs.
Usage: python3 rf_rows.py --cache <.cache dir> --dest <file>
"""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np


def build(cache: Path) -> list[dict]:
    import rf_candidates as rc
    import rf_occupancy as ro
    import rf_stats as rs
    rows = rc.load(cache, sources=ro.SOURCES)
    ro.add_occupancy(rows, ro.demands(cache))
    stats = rs.stats_by_case(cache)
    for r in rows:
        r['features'].update(stats.get(r['case'], {}))
    return rows


def _plain(value):
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    raise TypeError(f'{type(value).__name__} is not JSON serializable')


def write(rows, path: Path) -> None:
    with gzip.GzipFile(path, 'wb', mtime=0) as f:
        f.write(''.join(json.dumps(r, default=_plain) + '\n' for r in rows).encode())


def load(path: Path, sources=None) -> list[dict]:
    rows = []
    with gzip.open(path, 'rt') as f:
        for line in f:
            r = json.loads(line)
            if sources is None or r['source'] in sources:
                rows.append(dict(r, group=tuple(r['group'])))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    rows = build(args.cache.resolve())
    write(rows, args.dest)
    if load(args.dest) != rows:
        raise SystemExit(f'{args.dest} does not read back equal to the rows written')
    print(f'wrote {args.dest}: {len(rows)} rows')


if __name__ == '__main__':
    main()
