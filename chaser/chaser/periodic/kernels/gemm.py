"""Row-major uint32 GEMM with overwrite stores and a final word-wise hash."""

from pathlib import Path
from collections.abc import Iterator

from chaser.periodic.arrays import integer
from chaser.periodic.workload import (ArrayRegistry, TaskSpec, KernelMetrics, MemoryFootprint,
    ReferenceEvent, GemmParameters)
from chaser.periodic.kernels.templates import render_template


def validate(task: TaskSpec[GemmParameters], registry: ArrayRegistry) -> KernelMetrics:
    """Check padded matrix extents before calculating bounded work counts."""
    for role, dimensions, ld in (('A', ('m', 'k'), 'lda'), ('B', ('k', 'n'), 'ldb'),
                                 ('C', ('m', 'n'), 'ldc')):
        array = registry[task.arrays[role].array_id]
        if array.shape is None:
            continue
        if len(array.shape) != 2:
            raise ValueError('GEMM requires rank-2 shapes')
        expected = dict(zip(dimensions, array.shape))
        expected[ld] = array.strides_elements[0]
        for key, value in expected.items():
            current = getattr(task.parameters, key)
            if current is not None and (type(current) is not int or current != value):
                raise ValueError(f'GEMM {key} conflicts with array shape or strides')
            setattr(task.parameters, key, value)
    for key in ('m', 'n', 'k', 'lda', 'ldb', 'ldc'):
        integer(getattr(task.parameters, key), key)
    m, n, k = task.parameters.m, task.parameters.n, task.parameters.k
    for role, rows, cols, ld in (('A', m, k, task.parameters.lda), ('B', k, n, task.parameters.ldb),
                                 ('C', m, n, task.parameters.ldc)):
        binding = task.arrays[role]
        array = registry[binding.array_id]
        step = (array.strides_elements or (ld, 1))[1]
        if (array.element_type != 'uint32_t' or ld < (cols-1)*step+1
                or binding.offset_elements + (rows-1)*ld + (cols-1)*step+1 > array.length):
            raise ValueError('Invalid GEMM type, leading dimension, or bounds')
    loads = task.sweeps*2*m*n*k + m*n
    stores = task.sweeps*m*n
    # Budget validation precedes the checksum loop, even for oversized inputs.
    if loads + stores > 10_000_000:
        raise ValueError('Job exceeds 10000000 source accesses')
    value = (k * registry[task.arrays['A'].array_id].initial_value *
             registry[task.arrays['B'].array_id].initial_value) % 2**32
    checksum = 2166136261
    for _ in range(m*n):
        checksum = ((checksum ^ value) * 16777619) % 2**32
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=checksum,
                checksum_kind='u32-word-fnv1a-output-v1',
                loop_iterations=task.sweeps*(1+m+m*n+m*n*k)+m+m*n)


def events(task: TaskSpec[GemmParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    """Specify the complete job stream, including final output hash loads."""
    steps = {role: (registry[binding.array_id].strides_elements or (1, 1))[1]
             for role, binding in task.arrays.items()}
    def event(role, index, operation='load'):
        binding = task.arrays[role]
        return ReferenceEvent(array_id=binding.array_id, offset_bytes=4*(binding.offset_elements+index),
                    access_size_bytes=4, operation=operation)
    for _ in range(task.sweeps):
        for i in range(task.parameters.m):
            for j in range(task.parameters.n):
                for k in range(task.parameters.k):
                    yield event('A', i*task.parameters.lda+k*steps['A'])
                    yield event('B', k*task.parameters.ldb+j*steps['B'])
                yield event('C', i*task.parameters.ldc+j*steps['C'], 'store')
    for i in range(task.parameters.m):
        for j in range(task.parameters.n):
            yield event('C', i*task.parameters.ldc+j*steps['C'])


def source(task: TaskSpec[GemmParameters], registry: ArrayRegistry) -> list[str]:
    """Emit scalar i/j/k multiplication; hash logical output only once per job."""
    strides = {role + '_step': (registry[binding.array_id].strides_elements or (1, 1))[1]
               for role, binding in task.arrays.items()}
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, **strides)


def footprint(task: TaskSpec[GemmParameters], registry: ArrayRegistry) -> MemoryFootprint:
    """Count disjoint logical matrix elements and their shared boundary lines."""
    allocated = accessed = lines = 0
    for role, rows, cols, ld in (('A', task.parameters.m, task.parameters.k, task.parameters.lda),
                                ('B', task.parameters.k, task.parameters.n, task.parameters.ldb),
                                ('C', task.parameters.m, task.parameters.n, task.parameters.ldc)):
        binding = task.arrays[role]
        array = registry[binding.array_id]
        size, offset = array.itemsize, binding.offset_elements*array.itemsize
        step = (array.strides_elements or (ld, 1))[1]
        allocated += array.size_bytes
        accessed += rows*cols*size
        previous = -1
        for row in range(rows):
            first = (offset + row*ld*size)//32
            last = (offset + (row*ld+(cols-1)*step)*size)//32
            lines += (cols - (first == previous) if step*size >= 32 else
                      last - max(first, previous+1) + 1)
            previous = last
    return MemoryFootprint(allocation_bytes=allocated, unique_accessed_bytes=accessed, unique_cache_lines=lines)
