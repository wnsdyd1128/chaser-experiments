"""Source-informed read-side recipes; contracts live in rtems/periodic/RECIPES.md.

Each block has disjoint array roles and all blocks are visited per sweep. Width
changes and role variants stay in one conservative lineage, never new families.
These synthetic byte loads do not reproduce benchmark arithmetic or stores.
"""

from collections.abc import Iterator

from chaser.periodic import staged_recipes as staged


RECIPES = {
    'window-coeff': 'window-coefficient',
    'window-bank': 'window-coefficient',
    'paired-pass': 'multi-array-reuse',
    'matrix-reuse': 'multi-array-reuse',
    'row-column': 'block-phase',
    'row-column-mirrored': 'block-phase',
    **staged.RECIPES,
}


def block_size(pattern: str, width: int) -> int:
    """Return distinct byte positions in one complete block, before stride."""
    if pattern in staged.RECIPES:
        return staged.block_size(pattern, width)
    return {'window-coeff': 3*width, 'window-bank': 4*width,
            'paired-pass': 2*width, 'matrix-reuse': 2*width*width,
            'row-column': width*width, 'row-column-mirrored': width*width}[pattern]


def validate_recipe(task: dict) -> None:
    """Require a bounded even width and complete, nonempty blocks."""
    if task['pattern'] in staged.RECIPES:
        staged.validate_recipe(task)
        return
    width = task.get('width')
    if type(width) is not int or not 2 <= width <= 32 or width % 2:
        raise ValueError('Invalid recipe width: require an even integer in [2, 32]')
    if task['distinct'] % block_size(task['pattern'], width):
        raise ValueError('Invalid recipe distinct: require complete blocks')
    if any(k in task for k in ('hot_distinct', 'hot_repeats', 'cold_repeats')):
        raise ValueError('Legacy region parameters are not valid for a recipe')


def sweep_counts(task: dict) -> tuple[int, int]:
    """Count loads and all dynamic loop trips, excluding the job sweep loop."""
    if task['pattern'] in staged.RECIPES:
        return staged.sweep_counts(task)
    n, p = task['width'], task['pattern']
    blocks = task['distinct'] // block_size(p, n)
    loads, trips = {
        'window-coeff': (2*n*(n+1), 1+(n+1)+n*(n+1)),
        'window-bank': (4*n*(n+1), 1+3*(n+1)+2*n*(n+1)),
        'paired-pass': (6*n, 1+4+5*n),
        'matrix-reuse': (2*n**3, 1+n+n*n+n**3),
        'row-column': (2*n*n, 1+2*n+2*n*n),
        'row-column-mirrored': (2*n*n, 1+2*n+n*n),
    }[p]
    return blocks*loads, blocks*trips


def sweep_indices(task: dict) -> Iterator[int]:
    """Specify array roles and phase ordering independently of emitted C."""
    if task['pattern'] in staged.RECIPES:
        yield from staged.sweep_indices(task)
        return
    n, p = task['width'], task['pattern']
    size = block_size(p, n)
    for base in range(0, task['distinct'], size):
        if p in ('window-coeff', 'window-bank'):
            for start in range(n+1):
                for bank in range(1 if p == 'window-coeff' else 2):
                    for i in range(n):
                        yield base+start+i
                        yield base+2*n+bank*n+i
        elif p == 'paired-pass':
            for region in (0, n):
                for _ in range(2):
                    yield from range(base+region, base+region+n)
            for i in range(n):
                yield base+i
                yield base+n+i
        elif p == 'matrix-reuse':
            for col in range(n):
                for row in range(n):
                    for i in range(n):
                        yield base+row*n+i
                        yield base+n*n+col*n+i
        elif p == 'row-column':
            yield from range(base, base+n*n)
            for col in range(n):
                for row in range(n):
                    yield base+row*n+col
        else:
            for row in range(n):
                for i in range(n//2):
                    yield base+row*n+i
                    yield base+row*n+n-1-i
            for col in range(n):
                for i in range(n//2):
                    yield base+i*n+col
                    yield base+(n-1-i)*n+col


def recipe_body(task: dict) -> list[str]:
    """Emit ordered volatile byte loads and literal affine loop bounds."""
    if task['pattern'] in staged.RECIPES:
        return staged.recipe_body(task)
    n, p = task['width'], task['pattern']
    size = block_size(p, n)

    def load(index):
        return f'sum += data_{task["task_id"]}[(b * {size} + {index}) * {task["stride"]}];'

    def loop(var, bound):
        return f'for (int {var} = 0; {var} < {bound}; ++{var})'

    lines = [loop('b', task['distinct'] // size) + ' {']
    if p in ('window-coeff', 'window-bank'):
        lines.append('    ' + loop('w', n+1))
        if p == 'window-bank':
            lines.append('        ' + loop('bank', 2))
        indent = '            ' if p == 'window-bank' else '        '
        coeff = f'{2*n} + bank * {n} + i' if p == 'window-bank' else f'{2*n} + i'
        lines.extend([indent + loop('i', n) + ' {',
                      indent + '    ' + load('w + i'),
                      indent + '    ' + load(coeff), indent + '}'])
    elif p == 'paired-pass':
        for region in (0, n):
            lines.extend(['    ' + loop('r', 2), '        ' + loop('i', n),
                          '            ' + load(f'{region} + i')])
        lines.extend(['    ' + loop('i', n) + ' {', '        ' + load('i'),
                      '        ' + load(f'{n} + i'), '    }'])
    elif p == 'matrix-reuse':
        lines.extend(['    ' + loop('c', n), '        ' + loop('r', n),
                      '            ' + loop('i', n) + ' {',
                      '                ' + load(f'r * {n} + i'),
                      '                ' + load(f'{n*n} + c * {n} + i'), '            }'])
    elif p == 'row-column':
        lines.extend(['    ' + loop('r', n), '        ' + loop('c', n),
                      '            ' + load(f'r * {n} + c'),
                      '    ' + loop('c', n), '        ' + loop('r', n),
                      '            ' + load(f'r * {n} + c')])
    else:
        lines.extend(['    ' + loop('r', n), '        ' + loop('i', n//2) + ' {',
                      '            ' + load(f'r * {n} + i'),
                      '            ' + load(f'r * {n} + {n-1} - i'), '        }',
                      '    ' + loop('c', n), '        ' + loop('i', n//2) + ' {',
                      '            ' + load(f'i * {n} + c'),
                      '            ' + load(f'({n-1} - i) * {n} + c'), '        }'])
    lines.append('}')
    return ['    ' + line for line in lines]
