"""Build fresh inputs and staged-recipe reference fixtures without runtime labels."""

import argparse
import json
from pathlib import Path

from chaser.periodic_analysis import analyze
from chaser.periodic_build import prepare
from tools.rtems_periodic_pool import initialize
from tools.rtems_smoke import file_hash, write_json


LITERALS = {
    'butterfly-twiddle': [4,5,2,3,0,1],
    'butterfly-scale': [4,5,2,3,0,1,0,1,2,3],
    'triangular-solve': [4,5,2,6,7,3,6,1,8,0],
    'triangular-solve-transposed': [4,5,1,6,7,3,6,2,8,0],
}


def reference(pattern: str, n: int) -> list[int]:
    """Independent array-role reference; does not call generator/index helpers."""
    if n == 2:
        return LITERALS[pattern]
    result = []
    if pattern.startswith('butterfly'):
        coefficient = 2*n
        for stage in range(n.bit_length()-1):
            span = 2**(stage+1)
            for lane in range(span//2):
                result.extend([coefficient, coefficient+1])
                coefficient += 2
                for start in range(lane, n, span):
                    result.extend([2*start+span, 2*start+span+1, 2*start, 2*start+1])
            if pattern == 'butterfly-scale':
                result.extend(range(2*n))
    else:
        matrix = [list(range(r*n, (r+1)*n)) for r in range(n)]
        if pattern.endswith('transposed'):
            matrix = list(zip(*matrix))
        rhs = list(range(n*n, n*n+n))
        y = list(range(n*n+n, n*n+2*n))
        x = [None, *range(n*n+2*n, n*n+3*n-1)]
        for r in range(n):
            result.append(rhs[r])
            for col, value in zip(matrix[r][:r], y[:r]):
                result.extend([col, value])
        for r in range(n-1, -1, -1):
            result.append(y[r])
            for col, value in zip(matrix[r][r+1:], x[r+1:]):
                result.extend([col, value])
            result.append(matrix[r][r])
    return result


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    initialize(output / 'pool', version=3)
    correctness = output / 'correctness'
    correctness.mkdir()
    tasks, references = [], {}
    for width in (2, 8):
        for pattern in LITERALS:
            name = f't{len(tasks)}'
            trace = reference(pattern, width)
            size = max(trace)+1
            assert set(trace) == set(range(size))
            references[name] = [32*(i+b*size) for b in range(2) for i in trace]*2
            tasks.append(dict(task_id=name, pattern=pattern, width=width,
                distinct=2*size, stride=32, sweeps=2, core=len(tasks) % 4, period_ticks=20))
    config = dict(workload_id='staged-correctness', family_id='correctness-only',
        policy_id='correctness-only', horizon_ticks=40, eligible_for_training=False,
        test_eligible=False, tasks=tasks)
    snapshot = correctness / 'snapshot'
    prepare(config, snapshot)
    analyze(snapshot)
    layouts = json.loads((snapshot / 'layout.json').read_text())
    for arch in ('g', 'c', 'p'):
        for task in tasks:
            name = task['task_id']
            address = next(r['address'] for r in layouts[arch] if r['symbol'] == 'data_' + name)
            events = json.loads((snapshot / 'analysis' / arch / name / 'events.json').read_text())['events']
            assert [e['linked_address']-address for e in events] == references[name]
    write_json(correctness / 'reference-traces.json', references)
    write_json(correctness / 'manifest.json', dict(files={
        str(p.relative_to(correctness)): file_hash(p) for p in correctness.rglob('*') if p.is_file()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
