"""Seed contract shared by the register-bound kernels (alu-u32, fpu-f64).

Each sweep loads one uint32 seed (role seed) from a volatile array, so the compiler can neither hoist the chain out of
the sweep loop nor fold it at build time, then runs iterations dependent register operations. Every sweep starts from
the same seed, so every sweep and every job returns the same value; the job returns the sum of its sweeps.
"""

from collections.abc import Iterator

from chaser.periodic.arrays import integer
from chaser.periodic.workload import ArrayRegistry, ComputeParameters, KernelMetrics, ReferenceEvent, TaskSpec


def seed(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> int:
    """Validate iterations and the seed binding; return the seed value."""
    integer(task.parameters.iterations, 'iterations', 1, 1_000_000)
    binding = task.arrays['seed']
    array = registry[binding.array_id]
    if array.element_type != 'uint32_t':
        raise ValueError('The seed array must hold uint32_t elements')
    if (binding.offset_elements + 1) * array.itemsize > array.size_bytes:
        raise ValueError('Seed offset outside its array')
    return array.initial_value


def metrics(task: TaskSpec[ComputeParameters], value: int, kind: str) -> KernelMetrics:
    """One load per sweep; value is one sweep's result."""
    return KernelMetrics(source_loads=task.sweeps, source_stores=0, expected_checksum=task.sweeps * value % 2**32,
                         checksum_kind=kind, loop_iterations=task.sweeps * (1 + task.parameters.iterations))


def events(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    binding = task.arrays['seed']
    size = registry[binding.array_id].itemsize
    for _ in range(task.sweeps):
        yield ReferenceEvent(array_id=binding.array_id, offset_bytes=binding.offset_elements * size,
                             access_size_bytes=size, operation='load')
