"""Shape-based uint32 adaptation of PolyBench/C JACOBI-1D: one time step (B from A, then A from B) per sweep.

The three-point mean is an integer division by 3 (the original multiplies by 0.33333). State carries across
sweeps, as across the original time steps. A and B must share one initial value v with 3v < 2^32, so every
element stays v and the checksum is closed-form.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec


def _shapes(task, registry):
    array = registry[task.arrays['A'].array_id]
    if array.shape is None or len(array.shape) != 1 or array.shape[0] < 3:
        raise ValueError('JACOBI-1D requires a rank-1 A shape of at least 3')
    return dict(A=array.shape, B=array.shape)


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'JACOBI-1D')
    n = shapes['A'][0]
    v = pv.initial(task, registry, 'A')
    if pv.initial(task, registry, 'B') != v or 3*v >= 2**32:
        raise ValueError('JACOBI-1D requires A and B with one initial value v, 3v < 2^32')
    loads, stores = task.sweeps*6*(n - 2) + n, task.sweeps*2*(n - 2)
    pv.check_budget(loads, stores)
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([v]*n),
                         checksum_kind='u32-word-fnv1a-output-v1', loop_iterations=task.sweeps*(1 + 2*(n - 2)) + n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for src, dst in (('A', 'B'), ('B', 'A')):
            for i in range(1, n - 1):
                yield e(src, i - 1)
                yield e(src, i)
                yield e(src, i + 1)
                yield e(dst, i, operation='store')
    for i in range(n):
        yield e('A', i)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, last=n - 1,
                           **{k: v for role in ('A', 'B') for k, v in pv.steps(task, registry, role).items()})
