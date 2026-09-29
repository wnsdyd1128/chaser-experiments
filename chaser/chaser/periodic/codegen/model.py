"""C-generation data for typed explicit-array kernels."""

from dataclasses import dataclass

from chaser.periodic.workload import ArraySpec


@dataclass(frozen=True)
class ArrayDeclaration:
    """Validated storage fields needed for a flat C declaration and initializer.

    Placement and logical shape stay in ArraySpec; this projection contains only
    what the source renderer needs.

    Attributes:
        symbol: C identifier of the allocated array.
        element_type: C element type used in the declaration.
        length: Physical element count, including internal padding.
        alignment_bytes: Alignment requested by the generated C declaration.
        initial_value: Value written to each element once before workers start.
    """
    symbol: str
    element_type: str
    length: int
    alignment_bytes: int
    initial_value: int

    @classmethod
    def from_array(cls, array: ArraySpec) -> 'ArrayDeclaration':
        """Project an allocated object onto its C storage declaration."""
        return cls(array.symbol, array.element_type, array.length,
                   array.alignment_bytes, array.initial_value)


@dataclass(frozen=True)
class JobDefinition:
    """A complete C job and the values needed to register it in the harness.

    Attributes:
        task_id: Identifier used in the task_job_<task_id> C function name.
        expected_checksum: Expected uint32_t job return value emitted into the
            workload checksum table for runtime result validation.
        source: Complete C job definition and any required helpers, rendered
            from normalized kernel inputs.
    """
    task_id: str
    expected_checksum: int
    source: str


@dataclass(frozen=True)
class TaskSchedule:
    """Per-task scheduling constants emitted into config.h.

    Attributes:
        period_ticks: Release period in RTEMS clock ticks.
        job_count: Total jobs in the experiment horizon, including warmup jobs.
        core: Logical core used to choose placement under the selected policy.
    """
    period_ticks: int
    job_count: int
    core: int


@dataclass(frozen=True)
class PolicyHeader:
    """One policy's header data, independent of the persisted plan dict.

    Attributes:
        architecture: Scheduler layout: 0 for global (G), 1 for clustered (C),
            or 2 for partitioned (P).
        contract_id: Measurement contract identifier embedded in runtime output.
        plan_hash: Canonical plan identity used to bind runtime data to its plan.
        tasks: Scheduling records in worker-index order, matching the generated
            job function and expected-checksum tables.
    """
    architecture: int
    contract_id: str
    plan_hash: str
    tasks: tuple[TaskSchedule, ...]

    @classmethod
    def from_plan(cls, plan: dict) -> 'PolicyHeader':
        """Read only the fields needed by the RTEMS configuration header."""
        return cls(plan['architecture'], plan['contract_id'], plan['plan_hash'], tuple(
            TaskSchedule(t['period_ticks'], t['job_count'], t['core']) for t in plan['tasks']))
