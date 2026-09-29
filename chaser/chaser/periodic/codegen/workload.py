"""Compose declarations, complete kernels and the common workload wrapper."""

from pathlib import Path
from string import Template

from chaser.periodic.kernels import kernel_source, task_from_plan
from chaser.periodic.codegen.model import ArrayDeclaration, JobDefinition
from chaser.periodic.workload import ArraySpec, TaskSpec

TEMPLATES = Path(__file__).parent


def workload_source(tasks: list[dict] | list[TaskSpec], *,
                    arrays: list[dict] | list[ArraySpec] | None = None) -> str:
    """Render validated storage and kernel strategies into one C translation unit.

    Only this composition boundary joins C sections. Kernel parameters carry
    scalar data; each kernel owns its complete C implementation.

    .. deprecated:: 2
       Private-array generation without an explicit arrays registry was removed.
    """
    if arrays is None:
        raise ValueError('Legacy source generation is deprecated; provide schema_version: 2 arrays')
    objects = [a if isinstance(a, ArraySpec) else ArraySpec.from_dict(a) for a in arrays]
    registry = {a.array_id: a for a in objects}
    workloads = [task_from_plan(t) for t in tasks]
    storage = [ArrayDeclaration.from_array(a) for a in objects]
    jobs = [JobDefinition(t.task_id, t.metrics.expected_checksum,
                          '\n'.join(kernel_source(t, registry))) for t in workloads]
    definitions = []
    for i, array in enumerate(storage):
        definitions.append(
            f'volatile {array.element_type} {array.symbol}[{array.length}] '
            f'__attribute__((aligned({array.alignment_bytes}), section(".chaser_data.{i:02d}")));')
    definitions.extend(job.source for job in jobs)
    initializers = [f'    for (int i = 0; i < {a.length}; ++i) '
                    f'{a.symbol}[i] = {a.initial_value}U;' for a in storage]
    return Template((TEMPLATES / 'workload.c.in').read_text()).substitute(
        definitions='\n'.join(definitions), initializers='\n'.join(initializers),
        jobs='\n'.join(f'    task_job_{job.task_id},' for job in jobs),
        checksums=', '.join(str(job.expected_checksum) + 'U' for job in jobs))
