"""Read-side FFT stages and triangular substitution; see STAGED-RECIPES.md.

Stage and row bounds are expanded at generation time. Generated C retains
literal affine loops; neither data-dependent paths nor stores are substituted.
"""

from collections.abc import Iterator


RECIPES = {
    'butterfly-twiddle': 'staged-butterfly',
    'butterfly-scale': 'staged-butterfly',
    'triangular-solve': 'triangular-solve',
    'triangular-solve-transposed': 'triangular-solve',
}


def block_size(pattern: str, width: int) -> int:
    """Count fully visited positions, including disjoint array roles."""
    return 4*width-2 if pattern.startswith('butterfly') else width*width+3*width-1


def validate_recipe(task: dict) -> None:
    """Require complete blocks; butterfly stages need power-of-two widths."""
    n = task.get('width')
    if type(n) is not int or not 2 <= n <= 32:
        raise ValueError('Invalid staged recipe width: require an integer in [2, 32]')
    if task['pattern'].startswith('butterfly') and n & (n-1):
        raise ValueError('Butterfly recipe width must be a power of two')
    if task['distinct'] % block_size(task['pattern'], n):
        raise ValueError('Invalid staged recipe distinct: require complete blocks')
    if any(k in task for k in ('hot_distinct', 'hot_repeats', 'cold_repeats')):
        raise ValueError('Legacy region parameters are not valid for a staged recipe')


def sweep_counts(task: dict) -> tuple[int, int]:
    """Return loads and dynamic trips of emitted loops, including block loops."""
    n, p = task['width'], task['pattern']
    blocks = task['distinct'] // block_size(p, n)
    if p.startswith('butterfly'):
        stages = n.bit_length()-1
        scan = p == 'butterfly-scale'
        loads = 2*(n-1) + 2*n*stages*(1+scan)
        trips = 1 + n-1 + (n//2)*stages + scan*2*n*stages
    else:
        loads = 2*n*n+n
        trips = 1+n*(n-1)
    return blocks*loads, blocks*trips


def sweep_indices(task: dict) -> Iterator[int]:
    """Specify coefficient placement, stage order and triangular array roles."""
    n, p = task['width'], task['pattern']
    size = block_size(p, n)
    for base in range(0, task['distinct'], size):
        if p.startswith('butterfly'):
            half = 1
            while half < n:
                for lane in range(half):
                    yield base+2*n+2*(half-1+lane)
                    yield base+2*n+2*(half-1+lane)+1
                    for group in range(n//(2*half)):
                        first = 2*(2*half*group+lane)
                        yield base+first+2*half
                        yield base+first+2*half+1
                        yield base+first
                        yield base+first+1
                if p == 'butterfly-scale':
                    yield from range(base, base+2*n)
                half *= 2
        else:
            transposed = p == 'triangular-solve-transposed'
            for row in range(n):
                yield base+n*n+row
                for col in range(row):
                    yield base+(col*n+row if transposed else row*n+col)
                    yield base+n*n+n+col
            for row in reversed(range(n)):
                yield base+n*n+n+row
                for col in range(row+1, n):
                    yield base+(col*n+row if transposed else row*n+col)
                    yield base+n*n+2*n+col-1
                yield base+row*n+row


def recipe_body(task: dict) -> list[str]:
    """Emit volatile loads; expand only stages/rows with nonliteral bounds."""
    n, p = task['width'], task['pattern']
    size = block_size(p, n)

    def load(index):
        return f'sum += data_{task["task_id"]}[(b * {size} + {index}) * {task["stride"]}];'

    lines = [f'for (int b = 0; b < {task["distinct"] // size}; ++b) {{']
    if p.startswith('butterfly'):
        half = 1
        while half < n:
            lines.extend([f'    for (int lane = 0; lane < {half}; ++lane) {{',
                '        ' + load(f'{2*n+2*(half-1)} + 2 * lane'),
                '        ' + load(f'{2*n+2*(half-1)+1} + 2 * lane'),
                f'        for (int g = 0; g < {n//(2*half)}; ++g) {{'])
            for offset in (2*half, 2*half+1, 0, 1):
                lines.append('            ' + load(f'{4*half} * g + 2 * lane + {offset}'))
            lines.extend(['        }', '    }'])
            if p == 'butterfly-scale':
                lines.extend([f'    for (int i = 0; i < {2*n}; ++i)', '        ' + load('i')])
            half *= 2
    else:
        transposed = p == 'triangular-solve-transposed'
        for row in range(n):
            lines.append('    ' + load(str(n*n+row)))
            if row:
                address = f'j * {n} + {row}' if transposed else f'{row*n} + j'
                lines.extend([f'    for (int j = 0; j < {row}; ++j) {{',
                    '        ' + load(address), '        ' + load(f'{n*n+n} + j'), '    }'])
        for row in reversed(range(n)):
            lines.append('    ' + load(str(n*n+n+row)))
            if row < n-1:
                address = f'j * {n} + {row}' if transposed else f'{row*n} + j'
                lines.extend([f'    for (int j = {row+1}; j < {n}; ++j) {{',
                    '        ' + load(address), '        ' + load(f'{n*n+2*n-1} + j'), '    }'])
            lines.append('    ' + load(str(row*n+row)))
    lines.append('}')
    return ['    ' + line for line in lines]
