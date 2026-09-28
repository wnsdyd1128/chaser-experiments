"""Dispatch the three explicit-array kernels without changing legacy recipes."""

from chaser.periodic.arrays import fields, footprint, integer, normalize_bindings
from chaser.periodic.kernels import gemm, reads


def normalize_task(task, registry):
    """Validate kernel-specific fields and derive checksum and event budgets."""
    if not isinstance(task, dict):
        raise ValueError('Task must be an object')
    pattern = task.get('pattern')
    if pattern not in ('cyclic', 'paired-read', 'gemm-u32'):
        raise ValueError('Unknown schema v2 pattern')
    parameters = ('m', 'n', 'k', 'lda', 'ldb', 'ldc') if pattern == 'gemm-u32' else ('distinct', 'stride_bytes')
    common = ('task_id', 'pattern', 'arrays', 'sweeps', 'core', 'period_ticks')
    fields(task, common + parameters, common + parameters)
    task = dict(task)
    integer(task['sweeps'], 'sweeps', 1, 1_000_000)
    roles = ('A', 'B', 'C') if pattern == 'gemm-u32' else ('input',) if pattern == 'cyclic' else ('a', 'b')
    task['arrays'] = normalize_bindings(task['arrays'], roles, registry)
    task.update((gemm if pattern == 'gemm-u32' else reads).validate(task, registry))
    task['source_accesses'] = task['source_loads'] + task['source_stores']
    if task['source_accesses'] > 10_000_000:
        raise ValueError('Job exceeds 10000000 source accesses')
    task.update(footprint(task, registry))
    return task


def reference_events(task, registry):
    """Iterate full-job typed references without allocating a trace."""
    yield from (gemm if task['pattern'] == 'gemm-u32' else reads).events(task, registry)


def kernel_source(task, registry):
    """Return the inline helper and analyzed root job source."""
    return (gemm if task['pattern'] == 'gemm-u32' else reads).source(task, registry)
