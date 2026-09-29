"""Register explicit-array kernels with typed source and reference contracts."""

from dataclasses import MISSING, dataclass, fields as dataclass_fields
from copy import deepcopy
from collections.abc import Iterator
from typing import Protocol

from chaser.periodic.arrays import fields, integer, normalize_bindings
from chaser.periodic.workload import (ArrayRegistry, GemmParameters, KernelMetrics,
    MemoryFootprint, NoParameters, ReadParameters, ReferenceEvent, TaskSpec)
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.kernels import gemm, reads


class KernelImplementation(Protocol):
    """Structural interface implemented by each trusted kernel module."""

    def validate(self, task: TaskSpec, registry: ArrayRegistry) -> KernelMetrics: ...
    def events(self, task: TaskSpec, registry: ArrayRegistry) -> Iterator[ReferenceEvent]: ...
    def source(self, task: TaskSpec, registry: ArrayRegistry) -> list[str]: ...


@dataclass(frozen=True)
class Kernel:
    """Select a module and its parameter dataclass for a JSON pattern.

    validate(TaskSpec, ArrayRegistry) returns KernelMetrics and may normalize
    task.parameters. events yields ReferenceEvent; source returns C lines.
    Optional footprint returns MemoryFootprint. write_roles requires exclusive
    ownership of every object the kernel may write.

    Attributes:
        module: Trusted implementation supplying validation, ordered reference
            events and C source; it may also supply an optimized footprint.
        roles: Required array-binding names in their normalization order.
        parameter_type: Dataclass defining accepted kernel-specific JSON fields;
            fields without defaults are required. NoParameters accepts none.
        write_roles: Subset of roles that may store to their bound objects;
            workload validation enforces exclusive ownership of those objects.
    """
    module: KernelImplementation
    roles: tuple[str, ...]
    parameter_type: type = NoParameters
    write_roles: tuple[str, ...] = ()

    @property
    def parameters(self) -> tuple[str, ...]:
        """Derive accepted JSON fields from the parameter dataclass."""
        return tuple(f.name for f in dataclass_fields(self.parameter_type))

    @property
    def required_parameters(self) -> tuple[str, ...]:
        """Fields without defaults are mandatory in the input JSON."""
        return tuple(f.name for f in dataclass_fields(self.parameter_type)
                     if f.default is MISSING and f.default_factory is MISSING)


KERNELS = {
    'cyclic': Kernel(reads, ('input',), ReadParameters),
    'paired-read': Kernel(reads, ('a', 'b'), ReadParameters),
    'gemm-u32': Kernel(gemm, ('A', 'B', 'C'), GemmParameters, write_roles=('C',)),
}


def kernel_for(pattern: str) -> Kernel:
    """Resolve an explicitly registered pattern; JSON cannot import Python."""
    if not isinstance(pattern, str) or pattern not in KERNELS:
        raise ValueError('Unknown schema v2 pattern')
    return KERNELS[pattern]


def task_from_plan(value: dict | TaskSpec) -> TaskSpec:
    """Convert a persisted plan task once before entering typed kernel code."""
    if isinstance(value, TaskSpec):
        return value
    return TaskSpec.from_dict(value, kernel_for(value['pattern']).parameter_type)


def normalize_task(value: dict, registry: ArrayRegistry) -> TaskSpec:
    """Validate JSON once, then derive a typed kernel workload."""
    if not isinstance(value, dict):
        raise ValueError('Task must be an object')
    kernel = kernel_for(value.get('pattern'))
    common = ('task_id', 'pattern', 'arrays', 'sweeps', 'core', 'period_ticks')
    fields(value, common + kernel.parameters, common + kernel.required_parameters)
    parameters = {name: deepcopy(value[name]) for name in kernel.parameters if name in value}
    # None denotes an omitted, inferable GEMM dimension, not an accepted JSON value.
    if kernel.parameter_type is GemmParameters and any(v is None for v in parameters.values()):
        raise ValueError('Explicit GEMM parameters must be integers')
    task = TaskSpec(task_id=value['task_id'], pattern=value['pattern'],
                    arrays=normalize_bindings(value['arrays'], kernel.roles, registry),
                    sweeps=integer(value['sweeps'], 'sweeps', 1, 1_000_000),
                    core=value['core'], period_ticks=value['period_ticks'],
                    parameters=kernel.parameter_type(**parameters))
    task.metrics = kernel.module.validate(task, registry)
    if not isinstance(task.metrics, KernelMetrics):
        raise ValueError('Kernel validate must return KernelMetrics')
    for name in ('source_loads', 'source_stores', 'expected_checksum', 'loop_iterations'):
        integer(getattr(task.metrics, name), name, 0)
    if not isinstance(task.metrics.checksum_kind, str) or not task.metrics.checksum_kind:
        raise ValueError('Kernel must declare checksum_kind')
    if not 1 <= task.metrics.source_accesses <= 10_000_000:
        raise ValueError('Job must have 1 to 10000000 source accesses')
    if hasattr(kernel.module, 'footprint'):
        task.footprint = kernel.module.footprint(task, registry)
    else:
        words, lines = set(), set()
        for event in reference_events(task, registry):
            words.add((event.array_id, event.offset_bytes))
            lines.add((event.array_id, event.offset_bytes//32))
        task.footprint = MemoryFootprint(
            allocation_bytes=sum(registry[b.array_id].size_bytes for b in task.arrays.values()),
            unique_accessed_bytes=sum(registry[name].itemsize for name, _ in words),
            unique_cache_lines=len(lines))
    if not isinstance(task.footprint, MemoryFootprint):
        raise ValueError('Kernel footprint must return MemoryFootprint')
    return task


def reference_events(task: TaskSpec, registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    """Check each typed reference and the full-job declared load/store totals."""
    if task.metrics is None:
        raise ValueError('Task metrics must be validated before reference events')
    kernel = kernel_for(task.pattern)
    allowed = {b.array_id for b in task.arrays.values()}
    writable = {task.arrays[r].array_id for r in kernel.write_roles}
    loads = stores = 0
    for event in kernel.module.events(task, registry):
        if not isinstance(event, ReferenceEvent):
            raise ValueError('Kernel events must yield ReferenceEvent')
        name, operation = event.array_id, event.operation
        if name not in allowed or operation not in ('load', 'store') or (operation == 'store' and name not in writable):
            raise ValueError('Invalid reference object or undeclared write')
        array = registry[name]
        offset = integer(event.offset_bytes, 'reference offset', 0)
        if (type(event.access_size_bytes) is not int or event.access_size_bytes != array.itemsize
                or offset % array.itemsize or offset + array.itemsize > array.size_bytes):
            raise ValueError('Invalid typed reference bounds')
        if operation == 'load':
            loads += 1
        else:
            stores += 1
        if loads > task.metrics.source_loads or stores > task.metrics.source_stores:
            raise ValueError('Reference stream exceeds declared counts')
        yield event
    if (loads, stores) != (task.metrics.source_loads, task.metrics.source_stores):
        raise ValueError('Reference stream differs from declared counts')


def kernel_source(task: TaskSpec, registry: ArrayRegistry) -> list[str]:
    """Return complete C for a normalized task's kernel strategy."""
    return kernel_for(task.pattern).module.source(task, registry)
