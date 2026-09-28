"""Explicit cyclic and alternating paired reads of typed immutable objects."""

from chaser.periodic.arrays import integer


def validate(task, registry):
    """Validate typed strides and exclusive last-access bounds."""
    integer(task.get('distinct'), 'distinct', 1, 131072)
    integer(task.get('stride_bytes'), 'stride_bytes', 1, 4096)
    sizes = set()
    for binding in task['arrays'].values():
        array = registry[binding['array_id']]
        size = array['itemsize']
        sizes.add(size)
        end = binding['offset_elements']*size + (task['distinct']-1)*task['stride_bytes'] + size
        if task['stride_bytes'] % size or end > array['size_bytes']:
            raise ValueError('Typed stride or array bounds invalid')
    if len(sizes) != 1:
        raise ValueError('Paired arrays must have the same element type')
    loads = task['sweeps'] * task['distinct'] * len(task['arrays'])
    checksum = task['sweeps'] * task['distinct'] * sum(
        registry[b['array_id']]['initial_value'] for b in task['arrays'].values())
    return dict(source_loads=loads, source_stores=0, expected_checksum=checksum % 2**32,
                checksum_kind='u32-load-sum-v1',
                loop_iterations=task['sweeps']*(1+task['distinct']))


def events(task, registry):
    """Yield A then B at each location, preserving object identity."""
    for _ in range(task['sweeps']):
        for index in range(task['distinct']):
            for binding in task['arrays'].values():
                size = registry[binding['array_id']]['itemsize']
                yield dict(array_id=binding['array_id'], access_size_bytes=size, operation='load',
                           offset_bytes=binding['offset_elements']*size+index*task['stride_bytes'])


def source(task, registry):
    """Emit separate volatile statements to specify read evaluation order."""
    name = task['task_id']
    lines = [f'INLINE static uint32_t kernel_{name}(void) {{', '    uint32_t sum = 0;',
             f'    for (int i = 0; i < {task["distinct"]}; ++i) {{']
    for role, binding in task['arrays'].items():
        array = registry[binding['array_id']]
        lines.append(f'        uint32_t {role}_value = {array["symbol"]}'
                     f'[{binding["offset_elements"]} + i * {task["stride_bytes"] // array["itemsize"]}];')
        lines.append(f'        sum += {role}_value;')
    lines += ['    }', '    return sum;', '}',
              '/** @brief Execute one job without resetting arrays. @return Unsigned load sum. */',
              f'ANALYZE uint32_t task_job_{name}(void) {{', '    uint32_t sum = 0;',
              f'    for (int s = 0; s < {task["sweeps"]}; ++s)',
              f'        sum += kernel_{name}();', '    return sum;', '}']
    return lines
