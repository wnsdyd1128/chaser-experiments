"""Summarize CA and CLP from the baseline's C++ exports."""

import hashlib
import json
from pathlib import Path

from chaser.ca import ca_caas, ca_csrd

ROOT = Path(__file__).resolve().parents[1]


def summary():
    sources = {}

    def read(name):
        data = (ROOT / 'exports' / name).read_bytes()
        sources[name] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    element = {b['name'].split()[0]: b for b in read('element.rdh.json')['blocks']}
    line = {b['name'].split()[0]: b for b in read('line.rdh.json')['blocks']}
    cases = {}
    for case in ('packed', 'spread', 'conflict'):
        result = read(f'{case}.csrd.json')
        task = result['tasks'][0]
        name = 'chaser_' + case
        if len(result['tasks']) != 1 or task['task_id'] != name:
            raise ValueError(f'Expected one matching task for {case}')
        cases[case] = {
            'ca_caas_element': ca_caas(element[name]),
            'ca_global_line': ca_caas(line[name]),
            'ca_csrd_l1': ca_csrd(task),
            'clp': [task[k] for k in ('l1_first_hit_ratio', 'llc_first_hit_ratio',
                                      'all_cache_miss_ratio')],
            'analysis_id': result['analysis_id'],
        }
    return {'schema_version': 1, 'csrd_level': 'L1',
            'clp_order': ['L1', 'LLC', 'memory'], 'source_sha256': sources, 'cases': cases}


if __name__ == '__main__':
    (ROOT / 'exports/locality.json').write_text(
        json.dumps(summary(), sort_keys=True, indent=2, allow_nan=False) + '\n')
