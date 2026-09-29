"""Render user-owned C templates after kernel input validation."""

from pathlib import Path
from dataclasses import asdict
import re
from string import Template

from chaser.periodic.workload import ArrayRegistry, TaskSpec


def render_template(path: Path, task: TaskSpec, registry: ArrayRegistry, **substitutions) -> list[str]:
    """Render C from integer constants and identifiers, never C fragments.

    Templates are trusted project source, never a JSON-injected C expression.
    `${role}` names the backing symbol and `${role_offset}` counts elements;
    Extra substitutions must also be integers or identifiers. Operators,
    subscripts, statements and control flow belong to the template itself.
    The caller owns validation and must provide task_job_${task_id}(void).
    """
    values = dict(task_id=task.task_id, pattern=task.pattern, sweeps=task.sweeps,
                  core=task.core, period_ticks=task.period_ticks, **asdict(task.parameters))
    if task.metrics is not None:
        values.update(asdict(task.metrics), source_accesses=task.metrics.source_accesses)
    for role, binding in task.arrays.items():
        values[role] = registry[binding.array_id].symbol
        values[role + '_offset'] = binding.offset_elements
    values.update(substitutions)
    template = Template(Path(path).read_text())
    for match in template.pattern.finditer(template.template):
        name = match.group('named') or match.group('braced')
        if name is not None:
            value = values[name]
            if type(value) is not int and not (isinstance(value, str) and
                    re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value)):
                raise ValueError(f'Template parameter {name} must be an integer or C identifier')
    return template.substitute(values).splitlines()
