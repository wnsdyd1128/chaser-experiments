"""Typed storage declarations and exclusive ownership for periodic schema v2."""

import re

from chaser.periodic.workload import ArrayBinding, ArrayRegistry, ArrayShape, ArraySpec, TaskSpec

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


def normalize_shape(value: dict) -> ArrayShape:
    """Normalize positive row-major strides and return the occupied extent.

    Strides count elements, not bytes. Each outer step must clear the complete
    inner extent: padding is allowed, overlapping or transposed views are not.
    An omitted length reserves exactly through the final logical element.
    """
    shape = value['shape']
    if not isinstance(shape, list) or not shape:
        raise ValueError('shape must be a nonempty list')
    shape = [integer(n, 'shape dimension') for n in shape]
    strides, extent = [], 1
    if 'strides_elements' in value:
        strides = value['strides_elements']
        if not isinstance(strides, list) or len(strides) != len(shape):
            raise ValueError('strides_elements must match shape rank')
        strides = [integer(s, 'element stride') for s in strides]
    else:
        for n in reversed(shape):
            strides.append(extent)
            extent *= n
        strides.reverse()
    extent = 1
    for n, stride in reversed(list(zip(shape, strides))):
        if stride < extent:
            raise ValueError('Array strides must describe nonoverlapping row-major storage')
        extent += (n-1)*stride
    length = integer(value.get('length', extent), 'length')
    if length < extent:
        raise ValueError('Array shape exceeds length')
    return ArrayShape(tuple(shape), tuple(strides), length)


def normalize_arrays(values: list[dict]) -> list[ArraySpec]:
    """Lay out unique typed objects within the reserved 16 MiB, in input order."""
    if not isinstance(values, list) or not 1 <= len(values) <= 96:
        raise ValueError('Between 1 and 96 arrays are supported')
    result, seen, cursor = [], set(), 0x01000000
    for value in values:
        fields(value, ('array_id', 'element_type', 'length', 'shape', 'strides_elements',
                       'alignment_bytes', 'initial_value'), ('array_id', 'element_type'))
        name = identifier(value['array_id'])
        if name in seen:
            raise ValueError('Duplicate array ID')
        seen.add(name)
        dtype = value['element_type']
        if not isinstance(dtype, str) or dtype not in TYPES:
            raise ValueError('Unknown element_type')
        size = TYPES[dtype]
        if 'shape' not in value and 'strides_elements' in value:
            raise ValueError('strides_elements requires shape')
        layout = normalize_shape(value) if 'shape' in value else None
        length = layout.length if layout else integer(value.get('length'), 'length')
        alignment = integer(value.get('alignment_bytes', 4096), 'alignment_bytes')
        if alignment not in (32, 4096):
            raise ValueError('Array alignment must be 32 or 4096 bytes')
        initial = integer(value.get('initial_value', 1), 'initial_value', 0, 2**(8*size)-1)
        address = (cursor + alignment - 1) // alignment * alignment
        cursor = address + length * size
        if cursor > 0x02000000:
            raise ValueError('Workload data exceeds the reserved 16 MiB')
        result.append(ArraySpec(array_id=name, symbol='data_' + name, element_type=dtype,
                           itemsize=size, length=length, size_bytes=length*size,
                           alignment_bytes=alignment, initial_value=initial, address=address,
                           shape=layout.shape if layout else None,
                           strides_elements=layout.strides_elements if layout else None))
    return result


def normalize_bindings(value: dict, roles: tuple[str, ...], registry: ArrayRegistry) -> dict[str, ArrayBinding]:
    """Resolve roles to distinct objects; bounds are checked by each kernel."""
    fields(value, roles, roles)
    result = {}
    for role in roles:
        binding = value[role]
        fields(binding, ('array_id', 'offset_elements'), ('array_id',))
        name = identifier(binding['array_id'])
        if name not in registry:
            raise ValueError('Unknown array ID')
        result[role] = ArrayBinding(array_id=name, offset_elements=integer(
            binding.get('offset_elements', 0), 'offset_elements', 0))
    if len({b.array_id for b in result.values()}) != len(roles):
        raise ValueError('Array aliases within a task are unsupported')
    return result


def validate_ownership(tasks: list[TaskSpec], arrays: list[ArraySpec], *, write_roles: dict[str, tuple[str, ...]]):
    """Allow immutable sharing, but require each output object to be exclusive."""
    users, writers = {}, set()
    for task in tasks:
        for role, binding in task.arrays.items():
            name = binding.array_id
            users.setdefault(name, []).append(task.task_id)
            if role in write_roles[task.pattern]:
                writers.add(name)
    if set(users) != {a.array_id for a in arrays}:
        raise ValueError('Unused arrays are unsupported')
    if any(len(users[name]) != 1 for name in writers):
        raise ValueError('Output arrays must be exclusive to one task')
