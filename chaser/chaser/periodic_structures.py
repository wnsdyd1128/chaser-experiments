"""Affine, load-only candidate structures with distinct reuse orders.

All shapes cover a private array, have literal loop bounds, and repeat per sweep.
Numeric variants retain the same base-task lineage; these are synthetic kernels,
not independently sourced applications. Bounds prevent degenerate tiny shapes.
"""

from collections.abc import Iterator


STRUCTURES = {
    'tile-reuse': 'Four disjoint tiles, each scanned twice before the next tile.',
    'overlap': 'Seven half-overlapping windows, each one quarter of the array.',
    'lane-scan': 'Three residue-class scans, completing one lane before the next.',
    'forward-reverse': 'Full forward scan followed by a full reverse scan.',
    'mirrored': 'Alternating elements from opposite ends, converging at the middle.',
    'hub-spoke': 'Revisit element zero between every consecutive cold element.',
    'tile-reverse': 'Forward then reverse within each of four disjoint tiles.',
    'hot-per-tile': 'Twice scan the first tile before each of three distinct cold tiles.',
    'region-cycle': 'Three disjoint regions visited in the order A B A C B C.',
    'coarse-fine': 'Scan every fourth element, then scan the entire overlapping array.',
}


def validate_structure(task: dict) -> None:
    """Use multiples of 24 so all tile/lane partitions are exact and nonempty."""
    if task['distinct'] < 24 or task['distinct'] % 24:
        raise ValueError('Candidate structure distinct must be a positive multiple of 24')
    if any(k in task for k in ('hot_distinct', 'hot_repeats', 'cold_repeats')):
        raise ValueError('Region parameters are not used by candidate structures')


def sweep_counts(task: dict) -> tuple[int, int]:
    """Return loads and cumulative loop trips for one kernel call, not one job."""
    d, p = task['distinct'], task['pattern']
    return {
        'tile-reuse': (2*d, 2*d + 12),
        'overlap': (7*d//4, 7*d//4 + 7),
        'lane-scan': (d, d + 3),
        'forward-reverse': (2*d, 2*d),
        'mirrored': (d, d//2),
        'hub-spoke': (2*(d-1), d-1),
        'tile-reverse': (2*d, 2*d + 4),
        'hot-per-tile': (9*d//4, 9*d//4 + 9),
        'region-cycle': (2*d, 2*d),
        'coarse-fine': (5*d//4, 5*d//4),
    }[p]


def sweep_indices(task: dict) -> Iterator[int]:
    """Specify one sweep's element order independently of emitted C expressions."""
    d, p = task['distinct'], task['pattern']
    tile = d // 4
    if p in ('tile-reuse', 'tile-reverse'):
        for start in range(0, d, tile):
            yield from range(start, start + tile)
            yield from (range(start, start + tile) if p == 'tile-reuse'
                        else range(start + tile - 1, start - 1, -1))
    elif p == 'overlap':
        for start in range(0, d - tile + 1, tile // 2):
            yield from range(start, start + tile)
    elif p == 'lane-scan':
        for lane in range(3):
            yield from range(lane, d, 3)
    elif p == 'forward-reverse':
        yield from range(d)
        yield from range(d - 1, -1, -1)
    elif p == 'mirrored':
        for i in range(d // 2):
            yield i
            yield d - 1 - i
    elif p == 'hub-spoke':
        for i in range(1, d):
            yield 0
            yield i
    elif p == 'hot-per-tile':
        for start in range(tile, d, tile):
            yield from range(tile)
            yield from range(tile)
            yield from range(start, start + tile)
    elif p == 'region-cycle':
        for region in (0, 1, 0, 2, 1, 2):
            yield from range(region * (d//3), (region + 1) * (d//3))
    elif p == 'coarse-fine':
        yield from range(0, d, 4)
        yield from range(d)
    else:
        raise ValueError('Unknown candidate structure')


def structure_body(task: dict) -> list[str]:
    """Emit affine loads without modulo, data-dependent branches, or shared data."""
    d, p, stride = task['distinct'], task['pattern'], task['stride']
    tile, name = d // 4, task['task_id']

    def load(index):
        return f'sum += data_{name}[({index}) * {stride}];'

    def loop(variable, count):
        return f'for (int {variable} = 0; {variable} < {count}; ++{variable})'

    if p == 'tile-reuse':
        lines = [loop('b', 4), '    ' + loop('r', 2),
                 '        ' + loop('i', tile), '            ' + load(f'b * {tile} + i')]
    elif p == 'overlap':
        lines = [loop('w', 7), '    ' + loop('i', tile),
                 '        ' + load(f'w * {tile//2} + i')]
    elif p == 'lane-scan':
        lines = [loop('lane', 3), '    ' + loop('i', d//3),
                 '        ' + load('i * 3 + lane')]
    elif p == 'forward-reverse':
        lines = [loop('i', d), '    ' + load('i'),
                 loop('i', d), '    ' + load(f'{d-1} - i')]
    elif p in ('mirrored', 'hub-spoke'):
        count = d//2 if p == 'mirrored' else d-1
        first, second = ('i', f'{d-1} - i') if p == 'mirrored' else ('0', 'i + 1')
        lines = [loop('i', count) + ' {', '    ' + load(first),
                 '    ' + load(second), '}']
    elif p == 'tile-reverse':
        lines = [loop('b', 4) + ' {', '    ' + loop('i', tile),
                 '        ' + load(f'b * {tile} + i'), '    ' + loop('i', tile),
                 '        ' + load(f'b * {tile} + {tile-1} - i'), '}']
    elif p == 'hot-per-tile':
        lines = [loop('b', 3) + ' {', '    ' + loop('r', 2),
                 '        ' + loop('i', tile), '            ' + load('i'),
                 '    ' + loop('i', tile), '        ' + load(f'(b + 1) * {tile} + i'), '}']
    elif p == 'region-cycle':
        lines = []
        for region in (0, 1, 0, 2, 1, 2):
            lines.extend([loop('i', d//3), '    ' + load(f'{region * (d//3)} + i')])
    elif p == 'coarse-fine':
        lines = [loop('i', d//4), '    ' + load('4 * i'), loop('i', d), '    ' + load('i')]
    else:
        raise ValueError('Unknown candidate structure')
    return ['    ' + line for line in lines]
