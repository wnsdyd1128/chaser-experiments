"""Register-bound integer job (alu-u32): per sweep, a uint32 xorshift step and a multiply, iterations times
(IU shifts, xors and the hardware multiplier). See kernels.compute for the seed and checksum contract."""

from pathlib import Path

from chaser.periodic.kernels import compute
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, ComputeParameters, KernelMetrics, TaskSpec

MULTIPLIER = 2654435761  # the multiply in alu.c.in
MASK = 2**32 - 1


def chain(seed: int, iterations: int) -> int:
    """One sweep's result, as alu.c.in computes it in uint32 arithmetic."""
    x = seed & MASK
    for _ in range(iterations):
        x ^= (x << 13) & MASK
        x ^= x >> 17
        x ^= (x << 5) & MASK
        x = x * MULTIPLIER & MASK
    return x


def validate(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> KernelMetrics:
    value = chain(compute.seed(task, registry), task.parameters.iterations)
    return compute.metrics(task, value, 'u32-sum-xorshift-multiply-v1')


events = compute.events


def source(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> list[str]:
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry)
