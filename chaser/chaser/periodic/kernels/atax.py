"""Shape-based uint32 adaptation of PolyBench/C ATAX, y = A^T (A x).

The C template fixes volatile load order and resets scratch/output per sweep.
Constant initialization permits a closed-form checksum; arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, NoParameters, ReferenceEvent, TaskSpec


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    """Require one rank-2 matrix and three matching rank-1 uint32 views."""
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2:
        raise ValueError('ATAX requires a rank-2 A shape')
    m, n = matrix.shape
    for role, shape in (('A', (m, n)), ('x', (n,)), ('tmp', (m,)), ('y', (n,))):
        binding = task.arrays[role]
        array = registry[binding.array_id]
        if array.element_type != 'uint32_t' or array.shape != shape:
            raise ValueError(f'ATAX {role} requires uint32_t with shape {shape}')
        extent = 1 + sum((d-1)*s for d, s in zip(shape, array.strides_elements))
        if binding.offset_elements + extent > array.length:
            raise ValueError(f'ATAX {role} view exceeds array bounds')
    loads = task.sweeps*6*m*n + n
    stores = task.sweeps*(n+m+2*m*n)
    if loads + stores > 10_000_000:
        raise ValueError('Job exceeds 10000000 source accesses')
    value = (m*n*matrix.initial_value**2 * registry[task.arrays['x'].array_id].initial_value) % 2**32
    checksum = 2166136261
    for _ in range(n):
        checksum = ((checksum ^ value)*16777619) % 2**32
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=checksum,
        checksum_kind='u32-word-fnv1a-output-v1',
        loop_iterations=task.sweeps*(1+n+m+2*m*n)+n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    """Include zero stores, both row passes and the final logical-y hash loads."""
    m, n = registry[task.arrays['A'].array_id].shape

    def event(role, *indices, operation='load'):
        binding = task.arrays[role]
        array = registry[binding.array_id]
        offset = binding.offset_elements + sum(i*s for i, s in zip(indices, array.strides_elements))
        return ReferenceEvent(array_id=array.array_id, offset_bytes=4*offset,
                              access_size_bytes=4, operation=operation)

    for _ in range(task.sweeps):
        for j in range(n):
            yield event('y', j, operation='store')
        for i in range(m):
            yield event('tmp', i, operation='store')
            for j in range(n):
                yield event('tmp', i)
                yield event('A', i, j)
                yield event('x', j)
                yield event('tmp', i, operation='store')
            for j in range(n):
                yield event('y', j)
                yield event('A', i, j)
                yield event('tmp', i)
                yield event('y', j, operation='store')
    for j in range(n):
        yield event('y', j)


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    """Bind validated view dimensions and strides to the user-editable C loop."""
    matrix = registry[task.arrays['A'].array_id]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry,
        m=matrix.shape[0], n=matrix.shape[1],
        A_row=matrix.strides_elements[0], A_col=matrix.strides_elements[1],
        x_step=registry[task.arrays['x'].array_id].strides_elements[0],
        tmp_step=registry[task.arrays['tmp'].array_id].strides_elements[0],
        y_step=registry[task.arrays['y'].array_id].strides_elements[0])
