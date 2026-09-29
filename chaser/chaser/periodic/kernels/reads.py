"""Explicit cyclic and alternating paired reads of typed immutable objects."""

from pathlib import Path
from collections.abc import Iterator

from chaser.periodic.arrays import integer
from chaser.periodic.workload import (ArrayRegistry, TaskSpec, KernelMetrics, MemoryFootprint,
    ReferenceEvent, ReadParameters)
from chaser.periodic.kernels.templates import render_template


def validate(task: TaskSpec[ReadParameters], registry: ArrayRegistry) -> KernelMetrics:
    """Validate typed strides and exclusive last-access bounds."""
    integer(task.parameters.distinct, 'distinct', 1, 131072)
    integer(task.parameters.stride_bytes, 'stride_bytes', 1, 4096)
    sizes = set()
    for binding in task.arrays.values():
        array = registry[binding.array_id]
        size = array.itemsize
        sizes.add(size)
        end = binding.offset_elements*size + (task.parameters.distinct-1)*task.parameters.stride_bytes + size
        if task.parameters.stride_bytes % size or end > array.size_bytes:
            raise ValueError('Typed stride or array bounds invalid')
    if len(sizes) != 1:
        raise ValueError('Paired arrays must have the same element type')
    loads = task.sweeps * task.parameters.distinct * len(task.arrays)
    checksum = task.sweeps * task.parameters.distinct * sum(
        registry[b.array_id].initial_value for b in task.arrays.values())
    return KernelMetrics(source_loads=loads, source_stores=0, expected_checksum=checksum % 2**32,
                checksum_kind='u32-load-sum-v1',
                loop_iterations=task.sweeps*(1+task.parameters.distinct))


def events(task: TaskSpec[ReadParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    """Yield A then B at each location, preserving object identity."""
    for _ in range(task.sweeps):
        for index in range(task.parameters.distinct):
            for binding in task.arrays.values():
                size = registry[binding.array_id].itemsize
                yield ReferenceEvent(array_id=binding.array_id, access_size_bytes=size, operation='load',
                           offset_bytes=binding.offset_elements*size+index*task.parameters.stride_bytes)


def source(task: TaskSpec[ReadParameters], registry: ArrayRegistry) -> list[str]:
    """Emit separate volatile statements to specify read evaluation order."""
    bindings = list(task.arrays.values())
    values = dict(paired=int(len(bindings) == 2))
    for role, binding in zip(('read_a', 'read_b'), (bindings[0], bindings[-1])):
        array = registry[binding.array_id]
        values[role] = array.symbol
        values[role + '_offset'] = binding.offset_elements
        values[role + '_step'] = task.parameters.stride_bytes // array.itemsize
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, **values)


def footprint(task: TaskSpec[ReadParameters], registry: ArrayRegistry) -> MemoryFootprint:
    """Count typed linear accesses without expanding repeated sweeps."""
    allocated = accessed = lines = 0
    for binding in task.arrays.values():
        array = registry[binding.array_id]
        size, offset = array.itemsize, binding.offset_elements*array.itemsize
        count, stride = task.parameters.distinct, task.parameters.stride_bytes
        allocated += array.size_bytes
        accessed += count*size
        lines += (count if stride >= 32 else
                  (offset + (count-1)*stride)//32 - offset//32 + 1)
    return MemoryFootprint(allocation_bytes=allocated, unique_accessed_bytes=accessed, unique_cache_lines=lines)
