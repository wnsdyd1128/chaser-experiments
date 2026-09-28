"""Typed storage declarations and exclusive ownership for periodic schema v2."""

import re

TYPES = {'uint8_t': 1, 'uint32_t': 4}


def integer(value, name, low=1, high=2**32 - 1):
    """Validate literal unsigned bounds without accepting bool or coercion."""
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {name}')
    return value


def fields(value, allowed, required=()):
    """Reject missing and unknown fields in a schema v2 object."""
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError(f'Invalid fields; allowed: {sorted(allowed)}; required: {sorted(required)}')


def identifier(value):
    """Require an identifier safe to suffix generated C symbols."""
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('IDs must be C identifiers')
    return value


def normalize_arrays(values):
    """Lay out unique typed objects within the reserved 16 MiB, in input order."""
    if not isinstance(values, list) or not 1 <= len(values) <= 96:
        raise ValueError('Between 1 and 96 arrays are supported')
    result, seen, cursor = [], set(), 0x01000000
    for value in values:
        fields(value, ('array_id', 'element_type', 'length', 'alignment_bytes', 'initial_value'),
               ('array_id', 'element_type', 'length'))
        name = identifier(value['array_id'])
        if name in seen:
            raise ValueError('Duplicate array ID')
        seen.add(name)
        dtype = value['element_type']
        if not isinstance(dtype, str) or dtype not in TYPES:
            raise ValueError('Unknown element_type')
        size = TYPES[dtype]
        length = integer(value['length'], 'length')
        alignment = integer(value.get('alignment_bytes', 4096), 'alignment_bytes')
        if alignment not in (32, 4096):
            raise ValueError('Array alignment must be 32 or 4096 bytes')
        initial = integer(value.get('initial_value', 1), 'initial_value', 0, 2**(8*size)-1)
        address = (cursor + alignment - 1) // alignment * alignment
        cursor = address + length * size
        if cursor > 0x02000000:
            raise ValueError('Workload data exceeds the reserved 16 MiB')
        result.append(dict(array_id=name, symbol='data_' + name, element_type=dtype,
                           itemsize=size, length=length, size_bytes=length*size,
                           alignment_bytes=alignment, initial_value=initial, address=address))
    return result


def normalize_bindings(value, roles, registry):
    """Resolve roles to distinct objects; bounds are checked by each kernel."""
    fields(value, roles, roles)
    result = {}
    for role in roles:
        binding = value[role]
        fields(binding, ('array_id', 'offset_elements'), ('array_id',))
        name = identifier(binding['array_id'])
        if name not in registry:
            raise ValueError('Unknown array ID')
        result[role] = dict(array_id=name, offset_elements=integer(
            binding.get('offset_elements', 0), 'offset_elements', 0))
    if len({b['array_id'] for b in result.values()}) != len(roles):
        raise ValueError('Array aliases within a task are unsupported')
    return result


def validate_ownership(tasks, arrays):
    """Allow immutable sharing, but require each output object to be exclusive."""
    users, writers = {}, set()
    for task in tasks:
        for role, binding in task['arrays'].items():
            name = binding['array_id']
            users.setdefault(name, []).append(task['task_id'])
            if task['pattern'] == 'gemm-u32' and role == 'C':
                writers.add(name)
    if set(users) != {a['array_id'] for a in arrays}:
        raise ValueError('Unused arrays are unsupported')
    if any(len(users[name]) != 1 for name in writers):
        raise ValueError('Output arrays must be exclusive to one task')


def footprint(task, registry):
    """Count allocation, distinct bytes and 32-byte lines without expanding jobs.

    Roles cannot alias and each object starts on a line boundary. Matrix rows
    are disjoint in elements but can share their first/last cache lines.
    """
    allocated = accessed = lines = 0
    for role, binding in task['arrays'].items():
        array = registry[binding['array_id']]
        size, offset = array['itemsize'], binding['offset_elements'] * array['itemsize']
        allocated += array['size_bytes']
        if task['pattern'] != 'gemm-u32':
            count, stride = task['distinct'], task['stride_bytes']
            accessed += count * size
            lines += (count if stride >= 32 else
                      (offset + (count-1)*stride)//32 - offset//32 + 1)
        else:
            rows, cols, ld = {'A': (task['m'], task['k'], task['lda']),
                              'B': (task['k'], task['n'], task['ldb']),
                              'C': (task['m'], task['n'], task['ldc'])}[role]
            accessed += rows * cols * size
            previous = -1
            for row in range(rows):
                first = (offset + row*ld*size)//32
                last = (offset + (row*ld+cols)*size-1)//32
                lines += last - max(first, previous+1) + 1
                previous = last
    return dict(allocation_bytes=allocated, unique_accessed_bytes=accessed, unique_cache_lines=lines)
