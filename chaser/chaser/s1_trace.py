"""Parse independent Lackey accesses for one invocation of a generated leaf function."""

from hashlib import sha256
from itertools import zip_longest
import json
import re

_RECORD = re.compile(r'\s*([ILSM])\s+([0-9a-fA-F]+),(\d+)\n')
_METADATA = re.compile(r'==\d+==.*\n')


def parse_lackey(stream, *, function, array, max_references):
    """Filter instruction-PC and object ranges before any cache simulation.

    This deliberately supports one contiguous leaf-function invocation, with
    explicit entry and exit instruction records. Calls/recursion are rejected.
    M denotes a load followed by a store, not one source memory operation.
    """
    for base, size in (function, array):
        if (type(base) is not int or type(size) is not int or base < 0 or
                size <= 0 or base + size > 2 ** 64):
            raise ValueError('Invalid symbol interval')
    if type(max_references) is not int or max_references <= 0:
        raise ValueError('Positive reference limit required')
    fbase, fsize = function
    abase, asize = array
    pc, inside, entered, exited = None, False, False, False
    accesses = []
    stats = dict(instructions=0, roi_instructions=0, excluded_outside_roi=0,
                 excluded_outside_array=0, selected_accesses=0)
    for number, line in enumerate(stream, 1):
        if _METADATA.fullmatch(line):
            continue
        match = _RECORD.fullmatch(line)
        if not match:
            raise ValueError(f'Malformed Lackey record at line {number}')
        op, address, size = match.groups()
        address, size = int(address, 16), int(size)
        if size <= 0 or address + size > 2 ** 64:
            raise ValueError('Invalid trace access extent')
        if op == 'I':
            pc = address
            current = fbase <= pc < fbase + fsize
            if current:
                if pc + size > fbase + fsize or exited:
                    raise ValueError('Instruction crosses or re-enters function boundary')
                if not inside:
                    if entered or pc != fbase:
                        raise ValueError('Expected one entry at function start')
                    entered = True
                stats['roi_instructions'] += 1
            elif inside:
                exited = True
            inside = current
            stats['instructions'] += 1
            continue
        if pc is None:
            raise ValueError('Memory record precedes instruction')
        operations = ('load', 'store') if op == 'M' else ('load' if op == 'L' else 'store',)
        if not inside:
            stats['excluded_outside_roi'] += len(operations)
        elif address < abase + asize and address + size > abase:
            if address < abase or address + size > abase + asize:
                raise ValueError('Access partially overlaps array boundary')
            if len(accesses) + len(operations) > max_references:
                raise ValueError('Selected reference limit exceeded')
            accesses.extend((operation, address, size) for operation in operations)
        else:
            stats['excluded_outside_array'] += len(operations)
    if not entered or not exited:
        raise ValueError('Trace requires one complete function entry and exit')
    stats['selected_accesses'] = len(accesses)
    return accesses, stats


def cache_lines(accesses, line_bytes):
    """Expand each runtime source access exactly once into absolute cache lines."""
    if type(line_bytes) is not int or line_bytes <= 0:
        raise ValueError('Positive line size required')
    for _, address, size in accesses:
        yield from range(address // line_bytes, (address + size - 1) // line_bytes + 1)


def compare_accesses(expected, observed):
    """Compare source order/address/size/operation, independently of cache results."""
    def digest(rows):
        h = sha256()
        for row in rows:
            h.update((json.dumps(row, separators=(',', ':')) + '\n').encode())
        return h.hexdigest()

    first = next(({'ordinal': i, 'expected': a, 'observed': b}
                  for i, (a, b) in enumerate(zip_longest(expected, observed)) if a != b), None)
    return dict(equal=first is None, expected_count=len(expected), observed_count=len(observed),
                expected_sha256=digest(expected), observed_sha256=digest(observed),
                first_mismatch=first)
