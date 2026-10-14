"""Transpose B = A^T of a uint32 matrix (a corner turn of real-valued data), written as the common naive loop.

A is R x n and B is n x R. The loop reads A along its rows and writes B along its columns:
for i < R: for j < n: B[j][i] = A[i][j]. When B's row (R words) is a large power of two, its column stride maps the
stores onto a few L1 sets, so most stores miss L1; this is the low-locality access pattern the kernel stands for.
The job hashes only B's first column (n words): a whole-output hash would add a row-major pass as large as the
kernel. The oracle tests check all of B. Every sweep overwrites all of B, so every job returns the same checksum.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2:
        raise ValueError('Transpose requires a rank-2 A shape')
    rows, cols = matrix.shape
    return dict(A=(rows, cols), B=(cols, rows))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'Transpose')
    rows, cols = shapes['A']
    loads, stores = task.sweeps*rows*cols + cols, task.sweeps*rows*cols
    pv.check_budget(loads, stores)
    return KernelMetrics(source_loads=loads, source_stores=stores,
                         expected_checksum=pv.fnv([pv.initial(task, registry, 'A')]*cols),
                         checksum_kind='u32-word-fnv1a-first-column-v1',
                         loop_iterations=task.sweeps*(1 + rows + rows*cols) + cols)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    rows, cols = registry[task.arrays['A'].array_id].shape
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for i in range(rows):
            for j in range(cols):
                yield e('A', i, j)
                yield e('B', j, i, operation='store')
    for j in range(cols):
        yield e('B', j, 0)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    rows, cols = registry[task.arrays['A'].array_id].shape
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, rows=rows, cols=cols,
                           **{k: v for role in ('A', 'B') for k, v in pv.steps(task, registry, role).items()})
