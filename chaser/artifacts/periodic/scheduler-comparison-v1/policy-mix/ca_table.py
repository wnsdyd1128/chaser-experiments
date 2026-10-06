"""Per-task CA-CSRD (CAAS's L1 CSRD cache affinity) of a prepared deadline run, for experiment 28.

Reads every case's yarda/<task>.json (pm_run.py's hierarchy-rd analysis of the wfd build; the
program is the same for every placement) and applies chaser.locality.ca.ca_csrd, the value the
frozen CAAS policy of calibration-v2 thresholds. Static analysis only: no run result is read.
Writes {cases: {<cell>/u<load>/s<set>: {task: ca}}, sources: {<file>: sha256}}.
Usage: python3 ca_table.py --output <deadline run output> --dest <json>
"""

import argparse
import hashlib
import json
from pathlib import Path

from chaser.locality.ca import ca_csrd


def table(output: Path) -> dict:
    cases, sources = {}, {}
    for path in sorted(output.glob('*/u0*/s*/yarda/t*.json')):
        if path.name.endswith('.ape.json'):
            continue
        task = json.loads(path.read_text())['tasks'][0]
        key = str(path.parent.parent.relative_to(output))
        cases.setdefault(key, {})[path.stem] = ca_csrd(task)  # yarda names the task by its job function
        sources[str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(cases=cases, sources=sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    result = dict(table(args.output.resolve()), run=args.output.name)
    args.dest.parent.mkdir(parents=True, exist_ok=True)
    args.dest.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    print('wrote', args.dest, len(result['cases']), 'cases')


if __name__ == '__main__':
    main()
