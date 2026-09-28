"""Row-major uint32 GEMM with overwrite stores and a final word-wise hash."""

from chaser.periodic.arrays import integer


def validate(task, registry):
    """Check padded matrix extents before calculating bounded work counts."""
    for key in ('m', 'n', 'k', 'lda', 'ldb', 'ldc'):
        integer(task.get(key), key)
    m, n, k = task['m'], task['n'], task['k']
    for role, rows, cols, ld in (('A', m, k, task['lda']), ('B', k, n, task['ldb']),
                                 ('C', m, n, task['ldc'])):
        binding = task['arrays'][role]
        array = registry[binding['array_id']]
        if (array['element_type'] != 'uint32_t' or ld < cols
                or binding['offset_elements'] + (rows-1)*ld + cols > array['length']):
            raise ValueError('Invalid GEMM type, leading dimension, or bounds')
    loads = task['sweeps']*2*m*n*k + m*n
    stores = task['sweeps']*m*n
    # Budget validation precedes the checksum loop, even for oversized inputs.
    if loads + stores > 10_000_000:
        raise ValueError('Job exceeds 10000000 source accesses')
    value = (k * registry[task['arrays']['A']['array_id']]['initial_value'] *
             registry[task['arrays']['B']['array_id']]['initial_value']) % 2**32
    checksum = 2166136261
    for _ in range(m*n):
        checksum = ((checksum ^ value) * 16777619) % 2**32
    return dict(source_loads=loads, source_stores=stores, expected_checksum=checksum,
                checksum_kind='u32-word-fnv1a-output-v1',
                loop_iterations=task['sweeps']*(1+m+m*n+m*n*k)+m+m*n)


def events(task, registry):
    """Specify the complete job stream, including final output hash loads."""
    def event(role, index, operation='load'):
        binding = task['arrays'][role]
        return dict(array_id=binding['array_id'], offset_bytes=4*(binding['offset_elements']+index),
                    access_size_bytes=4, operation=operation)
    for _ in range(task['sweeps']):
        for i in range(task['m']):
            for j in range(task['n']):
                for k in range(task['k']):
                    yield event('A', i*task['lda']+k)
                    yield event('B', k*task['ldb']+j)
                yield event('C', i*task['ldc']+j, 'store')
    for i in range(task['m']):
        for j in range(task['n']):
            yield event('C', i*task['ldc']+j)


def source(task, registry):
    """Emit scalar i/j/k multiplication; hash logical output only once per job."""
    name = task['task_id']
    refs = {}
    for role, expression in (('A', f'i * {task["lda"]} + k'),
                              ('B', f'k * {task["ldb"]} + j'),
                              ('C', f'i * {task["ldc"]} + j')):
        binding = task['arrays'][role]
        refs[role] = f'{registry[binding["array_id"]]["symbol"]}[{binding["offset_elements"]} + {expression}]'
    return [f'INLINE static void kernel_{name}(void) {{',
            f'    for (int i = 0; i < {task["m"]}; ++i) {{',
            f'        for (int j = 0; j < {task["n"]}; ++j) {{',
            '            uint32_t acc = 0;',
            f'            for (int k = 0; k < {task["k"]}; ++k) {{',
            f'                uint32_t av = {refs["A"]};',
            f'                uint32_t bv = {refs["B"]};',
            '                acc += av * bv;', '            }',
            f'            {refs["C"]} = acc;', '        }', '    }', '}',
            '/** @brief Overwrite C per sweep, then hash logical output inside the job.',
            ' * @return Word-wise FNV-1a hash, modulo 2^32. */',
            f'ANALYZE uint32_t task_job_{name}(void) {{',
            f'    for (int s = 0; s < {task["sweeps"]}; ++s)', f'        kernel_{name}();',
            '    uint32_t h = 2166136261U;',
            f'    for (int i = 0; i < {task["m"]}; ++i)',
            f'        for (int j = 0; j < {task["n"]}; ++j)',
            f'            h = (h ^ {refs["C"]}) * 16777619U;', '    return h;', '}']
