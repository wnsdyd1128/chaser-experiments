"""Select the baseline job retained in one ELF; perform no RD analysis."""

import argparse
import json
from pathlib import Path


def select(data, case):
    function = 'chaser_' + case
    functions = [entry for entry in data['functions'] if entry['function'] == function]
    if len(functions) != 1:
        raise ValueError(f'Expected exactly one LAT function: {function}')
    object_id = 'global::' + case
    return {**data, 'functions': functions,
            'metadata': {**data['metadata'],
                         'objects': {object_id: data['metadata']['objects'][object_id]}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('case', choices=('packed', 'spread', 'conflict'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(select(json.loads(args.input.read_bytes()), args.case),
                                     sort_keys=True, indent=2) + '\n')
