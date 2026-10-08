"""Shared view checks, references, footprints and hashes of the uint32 PolyBench/C 4.2.1 adaptations.

Every adapted kernel binds fixed-shape uint32 views (shape, row-major or padded strides, element offset) and
hashes its live-out arrays word by word with FNV-1a inside the measured job.
"""

from chaser.periodic.workload import ArrayRegistry, MemoryFootprint, ReferenceEvent, TaskSpec

FNV_OFFSET, FNV_PRIME = 2166136261, 16777619
JOB_ACCESS_LIMIT = 10_000_000


def check_views(task: TaskSpec, registry: ArrayRegistry, shapes: dict, name: str) -> None:
    """Require each role to be a uint32 view of the given shape inside its array."""
    for role, shape in shapes.items():
        binding = task.arrays[role]
        array = registry[binding.array_id]
        if array.element_type != 'uint32_t' or array.shape != shape:
            raise ValueError(f'{name} {role} requires uint32_t with shape {shape}')
        extent = 1 + sum((d-1)*s for d, s in zip(shape, array.strides_elements))
        if binding.offset_elements + extent > array.length:
            raise ValueError(f'{name} {role} view exceeds array bounds')


def check_budget(loads: int, stores: int) -> None:
    if loads + stores > JOB_ACCESS_LIMIT:
        raise ValueError(f'Job exceeds {JOB_ACCESS_LIMIT} source accesses')


def element(task: TaskSpec, registry: ArrayRegistry, role: str, *indices) -> int:
    binding = task.arrays[role]
    strides = registry[binding.array_id].strides_elements
    return binding.offset_elements + sum(i*s for i, s in zip(indices, strides))


def event(task: TaskSpec, registry: ArrayRegistry, role: str, *indices, operation='load') -> ReferenceEvent:
    return ReferenceEvent(array_id=task.arrays[role].array_id, offset_bytes=4*element(task, registry, role, *indices),
                          access_size_bytes=4, operation=operation)


def initial(task: TaskSpec, registry: ArrayRegistry, role: str) -> int:
    return registry[task.arrays[role].array_id].initial_value


def fnv(values) -> int:
    h = FNV_OFFSET
    for v in values:
        h = ((h ^ (v % 2**32)) * FNV_PRIME) % 2**32
    return h


def steps(task: TaskSpec, registry: ArrayRegistry, role: str) -> dict:
    """Template substitutions <role>_row/<role>_col (rank 2) or <role>_step (rank 1)."""
    strides = registry[task.arrays[role].array_id].strides_elements
    return {f'{role}_row': strides[0], f'{role}_col': strides[1]} if len(strides) == 2 else {f'{role}_step': strides[0]}


def footprint(task: TaskSpec, registry: ArrayRegistry, shapes: dict, skip=None) -> MemoryFootprint:
    """Every element of every view is accessed except the indices skip(role, index) names."""
    words, lines = set(), set()
    for role, shape in shapes.items():
        array_id = task.arrays[role].array_id
        indices = [(i,) for i in range(shape[0])] if len(shape) == 1 else \
            [(i, j) for i in range(shape[0]) for j in range(shape[1])]
        for index in indices:
            if skip is not None and skip(role, index):
                continue
            offset = 4*element(task, registry, role, *index)
            words.add((array_id, offset))
            lines.add((array_id, (registry[array_id].address + offset)//32))
    return MemoryFootprint(allocation_bytes=sum(registry[b.array_id].size_bytes for b in task.arrays.values()),
                           unique_accessed_bytes=4*len(words), unique_cache_lines=len(lines))
