"""Extract and replay the input freeze in a fresh directory."""

import argparse
import json
from pathlib import Path
import tarfile

from tools.rtems_periodic_freeze import verify
from tools.rtems_smoke import check_inputs, write_json


def revalidate(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    check_inputs(root, json.loads((root / 'manifest.json').read_text()))
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(root / 'frozen-inputs.tar.gz') as archive:
        members = archive.getmembers()
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or path.parts[0] != 'frozen'
                    or not (member.isfile() or member.isdir())):
                raise ValueError('Unexpected archive member')
        archive.extractall(output, members=members)
    frozen = output / 'frozen'
    report = verify(frozen)
    for name in ('split.json', 'population.json', 'summary.json'):
        if (frozen / name).read_bytes() != (root / name).read_bytes():
            raise ValueError('Published metadata differs from archive')
    if (report['candidate_workloads'] != 207 or report['plans_validated'] != 621 or
            report['workload_counts'] != dict(train=126, validation=41, test=40)):
        raise ValueError('Frozen population changed')
    result = dict(status='PASS', **report)
    write_json(output / 'revalidation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(revalidate(parser.parse_args().output), indent=2, sort_keys=True))
