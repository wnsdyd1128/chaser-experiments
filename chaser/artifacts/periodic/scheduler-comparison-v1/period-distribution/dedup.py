"""Drop task sets that quantization made identical, then rerun the cell statistics.

Different seeds can round to the same periods and placement; such sets are one
sample measured several times. The lowest set id of each identical group is
kept. Writes results-dedup.jsonl, duplicates.json, stats-dedup.json/.md.
"""

import argparse
import json
from pathlib import Path

import stats


def task_key(output, row):
    path = output / f"m{row['mean']:03d}/cv{round(row['cv'] * 100):02d}/s{row['set_id']:02d}/configuration.json"
    tasks = json.loads(path.read_text())['tasks']
    return tuple(sorted((t['period_ticks'], t['core'], t['sweeps']) for t in tasks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = sorted(stats.load(args.output / 'results.jsonl'),
                  key=lambda r: (r['mean'], r['cv'], r['set_id']))
    kept, duplicates = {}, {}
    for row in rows:
        key = (row['mean'], row['cv'], task_key(args.output, row))
        if key in kept:
            duplicates.setdefault(f"m{row['mean']}/cv{row['cv']}/s{kept[key]['set_id']:02d}", []).append(row['set_id'])
        else:
            kept[key] = row
    unique = list(kept.values())
    with (args.output / 'results-dedup.jsonl').open('w') as stream:
        for row in unique:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    (args.output / 'duplicates.json').write_text(json.dumps(duplicates, indent=2, sort_keys=True) + '\n')
    cells = stats.cell_tests(unique)
    report = dict(alpha=stats.ALPHA, bootstrap=stats.BOOTSTRAP, task_sets=len(unique),
                  removed_duplicates=len(rows) - len(unique), cells=cells,
                  factors=stats.factor_tests(unique))
    (args.output / 'stats-dedup.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    (args.output / 'stats-dedup.md').write_text(stats.markdown(cells))
    print(f'{len(rows)} task sets -> {len(unique)} distinct ({len(rows) - len(unique)} duplicates removed)')


if __name__ == '__main__':
    main()
