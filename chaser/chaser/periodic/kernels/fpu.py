"""Register-bound double-precision job (fpu-f64): per sweep, x0 = (seed mod 1000 + 1) / 1001, then the logistic map
x = 3.9 x (1 - x) iterations times (FPU multiplies and subtractions; x stays in [0.09, 0.98], so it neither settles
nor under- or overflows). The sweep returns the integer part of x * 2^32. Only correctly rounded IEEE-754 operations
in a fixed order are used, and the scaling by 2^32 is exact, so Python reproduces the target's result bit for bit
(SPARC V8 has no fused multiply-add). See kernels.compute for the seed and checksum contract."""

from pathlib import Path

from chaser.periodic.kernels import compute
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, ComputeParameters, KernelMetrics, TaskSpec


def chain(seed: int, iterations: int) -> int:
    """One sweep's result, as fpu.c.in computes it in double precision."""
    x = (seed % 1000 + 1) / 1001.0
    for _ in range(iterations):
        x = 3.9 * x * (1.0 - x)
    return int(x * 4294967296.0)


def validate(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> KernelMetrics:
    value = chain(compute.seed(task, registry), task.parameters.iterations)
    return compute.metrics(task, value, 'u32-sum-logistic-map-f64-v1')


events = compute.events


def source(task: TaskSpec[ComputeParameters], registry: ArrayRegistry) -> list[str]:
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry)
