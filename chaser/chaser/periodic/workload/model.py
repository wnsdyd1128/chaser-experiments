"""Normalized workload records; JSON conversion stays at the plan boundary."""

from dataclasses import asdict, dataclass, fields
from copy import deepcopy
from typing import Generic, Literal, TypeVar


@dataclass(frozen=True)
class ArrayShape:
    """Logical layout resolved by array normalization, without allocating memory.

    Attributes:
        shape: Positive logical extent of each axis, from outermost to innermost.
        strides_elements: Positive per-axis strides in elements, with the same
            rank as shape. Outer strides include any row or plane padding.
        length: Physical element capacity, including padding; must cover every
            logical index, but may exceed the minimum required span.
    """
    shape: tuple[int, ...]
    strides_elements: tuple[int, ...]
    length: int


@dataclass(frozen=True)
class ArraySpec:
    """Normalized storage and placement for an object shared by kernel roles.

    Construction alone does not validate these values; array normalization owns
    validation. Logical shape metadata does not change the flat C allocation.

    Attributes:
        array_id: Unique object identifier used by bindings and reference events.
        symbol: C storage symbol used by generated code and ELF layout checks.
        element_type: C element type, currently uint8_t or uint32_t.
        itemsize: Bytes per element of element_type.
        length: Physical element count, including internal padding.
        size_bytes: length * itemsize, excluding gaps between allocated objects.
        alignment_bytes: Required address alignment in bytes.
        initial_value: Value assigned to every element before workers start;
            storage is not reinitialized between jobs.
        address: Planned byte address, checked against the built ELF symbol.
        shape: Logical axis extents, or None for a flat declaration.
        strides_elements: Per-axis strides in elements, or None when shape is
            absent. These are not byte offsets.
    """
    array_id: str
    symbol: str
    element_type: str
    itemsize: int
    length: int
    size_bytes: int
    alignment_bytes: int
    initial_value: int
    address: int
    shape: tuple[int, ...] | None = None
    strides_elements: tuple[int, ...] | None = None

    @classmethod
    def from_dict(cls, value: dict) -> 'ArraySpec':
        """Read a normalized plan array, preserving absent shape metadata."""
        data = dict(value)
        for name in ('shape', 'strides_elements'):
            if name in data:
                data[name] = tuple(data[name])
        return cls(**data)

    def to_dict(self) -> dict:
        """Serialize the existing plan schema without introducing null fields."""
        value = asdict(self)
        for name in ('shape', 'strides_elements'):
            if value[name] is None:
                del value[name]
            else:
                value[name] = list(value[name])
        return value


@dataclass(frozen=True)
class ArrayBinding:
    """Bind a kernel role to a view within a registered storage object.

    Attributes:
        array_id: Identifier resolved through the workload's array registry.
        offset_elements: Starting offset from the object's base in elements of
            its declared type; kernel validation checks the accessed bounds.
    """
    array_id: str
    offset_elements: int = 0


@dataclass(frozen=True)
class KernelMetrics:
    """Reference counts and result contract returned by kernel validation.

    Counts cover one complete job, including all sweeps and checksum reads.
    They describe source-level accesses, not cache misses or CPU instructions.

    Attributes:
        source_loads: Number of load references in the job's event stream.
        source_stores: Number of store references in the job's event stream.
        expected_checksum: Expected uint32_t job return value, compared by the
            runtime harness after execution.
        checksum_kind: Name describing the kernel's checksum algorithm/coverage.
        loop_iterations: Iteration bound used for analysis expansion limits;
            this is neither an access count nor an execution-time estimate.
    """
    source_loads: int
    source_stores: int
    expected_checksum: int
    checksum_kind: str
    loop_iterations: int

    @property
    def source_accesses(self) -> int:
        """Count both loads and stores, including checksum reads."""
        return self.source_loads + self.source_stores


@dataclass(frozen=True)
class MemoryFootprint:
    """Storage and distinct access coverage for one task's complete job.

    Repeated sweeps do not multiply distinct coverage. Shared storage may appear
    in several tasks' footprints, so task totals are not a task-set union.

    Attributes:
        allocation_bytes: Size of bound storage, including internal padding but
            excluding alignment gaps between objects.
        unique_accessed_bytes: Bytes touched at least once by the job, including
            checksum accesses.
        unique_cache_lines: Number of distinct 32-byte cache lines touched,
            independent of how often each line is accessed or misses the cache.
    """
    allocation_bytes: int
    unique_accessed_bytes: int
    unique_cache_lines: int


@dataclass(frozen=True)
class ReferenceEvent:
    """One typed memory access in the exact execution order of a job.

    Attributes:
        array_id: Accessed storage object in the array registry.
        offset_bytes: Byte offset from the object's base, including any binding
            offset; this is not an element index.
        access_size_bytes: Access width in bytes, matching the object's itemsize.
        operation: Load or store, including loads used to compute the checksum.
    """
    array_id: str
    offset_bytes: int
    access_size_bytes: int
    operation: Literal['load', 'store'] = 'load'


@dataclass
class NoParameters:
    """Empty parameter record for kernels needing only common task fields.

    Registering this type accepts no kernel-specific JSON parameters; bindings,
    sweeps and scheduling inputs still belong to TaskSpec.
    """


@dataclass
class ReadParameters:
    """Access sequence repeated by each sweep of a cyclic or paired-read job.

    Attributes:
        distinct: Number of positions read per bound role in a single sweep.
        stride_bytes: Byte distance between consecutive positions; validation
            requires a positive multiple of the bound element size.
    """
    distinct: int
    stride_bytes: int


@dataclass
class GemmParameters:
    """Dimensions and row pitches for C = A @ B in a GEMM job.

    None marks an omitted input that validation must infer from array shape
    metadata. Explicit JSON null is rejected. All fields are resolved to positive
    integers before generating C or reference events.

    Attributes:
        m: Number of rows in A and C.
        n: Number of columns in B and C.
        k: Reduction dimension: columns in A and rows in B.
        lda: A's row pitch in elements, including any padding.
        ldb: B's row pitch in elements, including any padding.
        ldc: C's row pitch in elements, including any padding.
    """
    m: int | None = None
    n: int | None = None
    k: int | None = None
    lda: int | None = None
    ldb: int | None = None
    ldc: int | None = None


Parameters = TypeVar('Parameters')


@dataclass
class TaskSpec(Generic[Parameters]):
    """Kernel inputs followed by derived metrics and footprint during validation.

    Scheduling records remain in the public plan. A kernel may normalize its
    parameter dataclass; normalize_task owns setting metrics and footprint.
    Callers must normalize before generating C or iterating reference events.

    Attributes:
        task_id: Unique task identifier used to name its generated C job.
        pattern: Key selecting a registered kernel implementation.
        arrays: Kernel role names mapped to object bindings, not copied storage.
        sweeps: Repetitions within one job, separate from periodic job_count.
        core: Logical core used by policy-specific scheduling placement.
        period_ticks: Release period in RTEMS clock ticks, not milliseconds.
        parameters: Kernel-specific dataclass; validation may resolve its fields.
        metrics: Derived job contract, absent until kernel validation completes.
        footprint: Derived storage/access coverage, absent until normalization
            completes. Serialization requires both metrics and footprint.
    """
    task_id: str
    pattern: str
    arrays: dict[str, ArrayBinding]
    sweeps: int
    core: int
    period_ticks: int
    parameters: Parameters
    metrics: KernelMetrics | None = None
    footprint: MemoryFootprint | None = None

    @classmethod
    def from_dict(cls, value: dict, parameter_type: type[Parameters]) -> 'TaskSpec[Parameters]':
        """Read the kernel portion of an already normalized plan task."""
        task = cls(task_id=value['task_id'], pattern=value['pattern'],
                   arrays={role: ArrayBinding(**binding) for role, binding in value['arrays'].items()},
                   sweeps=value['sweeps'], core=value['core'], period_ticks=value['period_ticks'],
                   parameters=parameter_type(**{f.name: deepcopy(value[f.name]) for f in fields(parameter_type)}),
                   metrics=KernelMetrics(**{f.name: value[f.name] for f in fields(KernelMetrics)}),
                   footprint=MemoryFootprint(**{f.name: value[f.name] for f in fields(MemoryFootprint)}))
        if task.metrics.source_accesses != value['source_accesses']:
            raise ValueError('Plan source access count differs from kernel metrics')
        return task

    def to_dict(self) -> dict:
        """Flatten typed parameters and results into the unchanged plan schema."""
        if self.metrics is None or self.footprint is None:
            raise ValueError('Task must be normalized before serialization')
        return dict(task_id=self.task_id, pattern=self.pattern,
                    arrays={role: asdict(binding) for role, binding in self.arrays.items()},
                    sweeps=self.sweeps, core=self.core, period_ticks=self.period_ticks,
                    **asdict(self.parameters), **asdict(self.metrics),
                    source_accesses=self.metrics.source_accesses, **asdict(self.footprint))


ArrayRegistry = dict[str, ArraySpec]
