"""Finite private-array access patterns shared by periodic plans and analysis.

Hot/cold interleaves regions once per sweep; phase completes all hot sweeps
before any cold sweeps. Both execute the same number of loads for equal inputs.
Absent pattern fields retain the original cyclic plan and generated source.
"""

from collections.abc import Iterator

from chaser.periodic import recipes
from chaser.periodic.structures import (
    STRUCTURES, structure_body, sweep_counts, sweep_indices, validate_structure,
)


def validate_pattern(task: dict) -> None:
    """Reject unknown patterns, empty regions, or ignored region parameters.

    Common distinct/stride/sweeps bounds must already have been validated.
    Region sizes count accessed byte elements, not necessarily cache lines.
    """
    pattern = task.get('pattern', 'cyclic')
    if pattern in recipes.RECIPES:
        recipes.validate_recipe(task)
        return
    if 'width' in task:
        raise ValueError('Recipe width is not valid for this pattern')
    if pattern in STRUCTURES:
        validate_structure(task)
        return
    if pattern not in ('cyclic', 'hot-cold', 'phase'):
        raise ValueError('Invalid workload pattern')
    fields = ('hot_distinct', 'hot_repeats', 'cold_repeats')
    if pattern == 'cyclic':
        if any(key in task for key in fields):
            raise ValueError('Region parameters are not valid for cyclic workloads')
        return
    for key, high in zip(fields, (task['distinct'] - 1, 1_000_000, 1_000_000)):
        value = task.get(key)
        if type(value) is not int or not 1 <= value <= high:
            raise ValueError(f'Invalid {key}')


def job_access_count(task: dict) -> int:
    """Count every byte load, including region repetitions in one full job."""
    if task.get('pattern') in recipes.RECIPES:
        return task['sweeps'] * recipes.sweep_counts(task)[0]
    if task.get('pattern') in STRUCTURES:
        return task['sweeps'] * sweep_counts(task)[0]
    if task.get('pattern', 'cyclic') == 'cyclic':
        return task['sweeps'] * task['distinct']
    hot = task['hot_distinct'] * task['hot_repeats']
    cold = (task['distinct'] - task['hot_distinct']) * task['cold_repeats']
    return task['sweeps'] * (hot + cold)


def wrapper_sweeps(task: dict) -> int:
    """Phase sweeps live inside the kernel to keep all hot work before cold."""
    return 1 if task.get('pattern') == 'phase' else task['sweeps']


def loop_iterations(task: dict) -> int:
    """Count dynamic trips at every emitted loop level for YARDA's budget."""
    pattern = task.get('pattern', 'cyclic')
    if pattern in recipes.RECIPES:
        return task['sweeps'] * (1 + recipes.sweep_counts(task)[1])
    if pattern in STRUCTURES:
        return task['sweeps'] * (1 + sweep_counts(task)[1])
    overhead = task['sweeps']
    if pattern != 'cyclic':
        overhead += task['sweeps'] * (task['hot_repeats'] + task['cold_repeats'])
        if pattern == 'phase':
            overhead += task['sweeps'] + 1
    return job_access_count(task) + overhead


def access_offsets(task: dict) -> Iterator[int]:
    """Yield the specified job's byte offsets without allocating a full trace."""
    pattern = task.get('pattern', 'cyclic')
    if pattern in recipes.RECIPES:
        for _ in range(task['sweeps']):
            for index in recipes.sweep_indices(task):
                yield index * task['stride']
        return
    if pattern in STRUCTURES:
        for _ in range(task['sweeps']):
            for index in sweep_indices(task):
                yield index * task['stride']
        return
    if pattern == 'cyclic':
        for _ in range(task['sweeps']):
            yield from range(0, task['data_size'], task['stride'])
        return
    split = task['hot_distinct'] * task['stride']
    hot = range(0, split, task['stride'])
    cold = range(split, task['data_size'], task['stride'])
    if pattern == 'phase':
        for _ in range(task['sweeps'] * task['hot_repeats']):
            yield from hot
        for _ in range(task['sweeps'] * task['cold_repeats']):
            yield from cold
    else:
        for _ in range(task['sweeps']):
            for _ in range(task['hot_repeats']):
                yield from hot
            for _ in range(task['cold_repeats']):
                yield from cold


def kernel_body(task: dict) -> list[str]:
    """Emit literal-bound loads with no branch, shared data, or cache reset."""
    name, stride = task['task_id'], task['stride']
    pattern = task.get('pattern', 'cyclic')
    if pattern in recipes.RECIPES:
        return recipes.recipe_body(task)
    if pattern in STRUCTURES:
        return structure_body(task)
    if pattern == 'cyclic':
        return [f'    for (int i = 0; i < {task["data_size"]}; i += {stride})',
                f'        sum += data_{name}[i];']
    split = task['hot_distinct'] * stride
    lines = []
    for start, stop, repeats in ((0, split, task['hot_repeats']),
                                 (split, task['data_size'], task['cold_repeats'])):
        indent = '    '
        if pattern == 'phase':
            lines.append(f'    for (int s = 0; s < {task["sweeps"]}; ++s)')
            indent += '    '
        lines.extend([f'{indent}for (int r = 0; r < {repeats}; ++r)',
                      f'{indent}    for (int i = {start}; i < {stop}; i += {stride})',
                      f'{indent}        sum += data_{name}[i];'])
    return lines
