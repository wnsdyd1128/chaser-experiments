"""Compose declarations, complete kernels and the common workload wrapper."""

from pathlib import Path
from string import Template

from chaser.periodic.kernels import RESUME, kernel_source, segment_tasks, task_from_plan
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
    segments = [segment_tasks(t, registry) for t in workloads]
    jobs = [JobDefinition(t.task_id, t.metrics.expected_checksum,
                          '\n'.join(line for s in parts for line in kernel_source(s, registry)))
            for t, parts in zip(workloads, segments)]
    definitions = []
    for i, array in enumerate(storage):
        definitions.append(
            f'volatile {array.element_type} {array.symbol}[{array.length}] '
            f'__attribute__((aligned({array.alignment_bytes}), section(".chaser_data.{i:02d}")));')
    definitions.extend(job.source for job in jobs)
    initializers = [f'    for (int i = 0; i < {a.length}; ++i) '
                    f'{a.symbol}[i] = {a.initial_value}U;' for a in storage]
    source = Template((TEMPLATES / 'workload.c.in').read_text()).substitute(
        definitions='\n'.join(definitions), initializers='\n'.join(initializers),
        jobs='\n'.join(f'    task_job_{job.task_id},' for job in jobs),
        checksums=', '.join(str(job.expected_checksum) + 'U' for job in jobs))
    if any(t.suspend_ticks for t in workloads):
        # Read by init.c under CHASER_SUSPENDS: the resumed segment per task (0 if the job does not
        # suspend) and the first segment's expected checksum. Absent otherwise, so sources are unchanged.
        source += ('uint32_t (*const workload_resume_jobs[])(void) = {\n'
                   + ''.join(f'    task_job_{RESUME}{t.task_id},\n' if t.suspend_ticks else '    0,\n' for t in workloads)
                   + '};\nconst uint32_t workload_suspend_expected[] = {'
                   + ', '.join(f'{p[0].metrics.expected_checksum if len(p) > 1 else 0}U' for p in segments) + '};\n')
    return source
