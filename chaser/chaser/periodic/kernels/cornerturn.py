"""Corner turn of planar complex data: Br = Ar^T and Bi = Ai^T in one naive loop (radar/SAR range-azimuth turn).

Real and imaginary parts are separate uint32 matrices (split-complex layout); Ar and Ai are R x n, Br and Bi n x R.
for i < R: for j < n: re = Ar[i][j]; im = Ai[i][j]; Br[j][i] = re; Bi[j][i] = im. As in the transpose kernel, a large
power-of-two R maps the column stores onto a few L1 sets. The job hashes the first columns of Br and Bi (2n words);
the oracle tests check the whole outputs. Every sweep overwrites Br and Bi, so every job returns the same checksum.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec

ROLES = ('Ar', 'Ai', 'Br', 'Bi')


def _shapes(task, registry):
    matrix = registry[task.arrays['Ar'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2:
        raise ValueError('Corner turn requires a rank-2 Ar shape')
    rows, cols = matrix.shape
    return dict(Ar=(rows, cols), Ai=(rows, cols), Br=(cols, rows), Bi=(cols, rows))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'Corner turn')
    rows, cols = shapes['Ar']
    loads, stores = task.sweeps*2*rows*cols + 2*cols, task.sweeps*2*rows*cols
    pv.check_budget(loads, stores)
    expected = [pv.initial(task, registry, 'Ar')]*cols + [pv.initial(task, registry, 'Ai')]*cols
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv(expected),
                         checksum_kind='u32-word-fnv1a-first-column-v1',
                         loop_iterations=task.sweeps*(1 + rows + rows*cols) + 2*cols)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    rows, cols = registry[task.arrays['Ar'].array_id].shape
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for i in range(rows):
            for j in range(cols):
                yield e('Ar', i, j)
                yield e('Ai', i, j)
                yield e('Br', j, i, operation='store')
                yield e('Bi', j, i, operation='store')
    for role in ('Br', 'Bi'):
        for j in range(cols):
            yield e(role, j, 0)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    rows, cols = registry[task.arrays['Ar'].array_id].shape
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, rows=rows, cols=cols,
                           **{k: v for role in ROLES for k, v in pv.steps(task, registry, role).items()})
