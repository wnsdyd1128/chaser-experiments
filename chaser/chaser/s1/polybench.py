"""Count Cachegrind demand misses for trace-validated global-array kernels."""

from chaser.locality.cache_reference import FirstHits
from chaser.s1.trace import parse_lackey


EVENTS = 'Ir I1mr ILmr Dr D1mr DLmr Dw D1mw DLmw'.split()


def selected_array_accesses(stream, *, function, arrays, max_references):
    """Select one leaf invocation and require every selected access to name an array."""
    if not arrays or any(size <= 0 for _, size in arrays):
        raise ValueError('Nonempty array ranges required')
    ordered = sorted(arrays)
    if any(a + size > b for (a, size), (b, _) in zip(ordered, ordered[1:])):
        raise ValueError('Overlapping named arrays')
    lower = ordered[0][0]
    upper = max(base + size for base, size in ordered)
    # Valgrind 3.18.1 reports DWARF-5 decoding warnings outside Lackey records.
    records = (line for line in stream
               if not line.startswith('### unhandled dwarf2 abbrev form code '))
    accesses, stats = parse_lackey(records, function=function,
                                   array=(lower, upper - lower),
                                   max_references=max_references)
    for _, address, size in accesses:
        if sum(base <= address and address + size <= base + length
               for base, length in ordered) != 1:
            raise ValueError('Selected access outside named arrays')
    return accesses, stats


def read_cachegrind_counts(text, source, function, excluded_lines, expected_accesses):
    """Aggregate function statistics, optionally omitting audited source rows.

    Cachegrind simulates all traffic before attributing events to source lines.
    Line zero must remain because it can contain real array accesses. Supply an
    expected population only when comparing the same access stream with YARDA.
    """
    columns = None
    filename = current_function = None
    selected = dict.fromkeys(EVENTS, 0)
    excluded = dict.fromkeys(EVENTS, 0)
    seen_excluded = set()
    summary = None
    for line in text.splitlines():
        if line.startswith('events:'):
            if columns is not None or line.split()[1:] != EVENTS:
                raise ValueError('Unsupported Cachegrind events')
            columns = EVENTS
        elif line.startswith('fl='):
            filename = line[3:]
        elif line.startswith('fn='):
            current_function = line[3:]
        elif line.startswith('summary:'):
            fields = line.split()[1:]
            if summary is not None or columns is None or len(fields) != len(EVENTS):
                raise ValueError('Incomplete Cachegrind summary')
            summary = dict(zip(EVENTS, map(int, fields)))
        elif not line or line.startswith(('desc:', 'cmd:')):
            continue
        else:
            fields = line.split()
            if (columns is None or len(fields) != len(EVENTS) + 1 or
                    not all(value.isdecimal() for value in fields)):
                raise ValueError('Unsupported Cachegrind position or record')
            if filename != source or current_function != function:
                continue
            position = int(fields[0])
            values = dict(zip(EVENTS, map(int, fields[1:])))
            target = excluded if position in excluded_lines else selected
            if target is excluded:
                seen_excluded.add(position)
            for name in EVENTS:
                target[name] += values[name]
    if summary is None or seen_excluded != set(excluded_lines):
        raise ValueError('Missing summary or excluded rows')
    accesses = selected['Dr'] + selected['Dw']
    if expected_accesses is not None and accesses != expected_accesses:
        raise ValueError('Cachegrind selected population differs from array stream')
    for accesses_key, l1_key, ll_key in (('Dr', 'D1mr', 'DLmr'),
                                         ('Dw', 'D1mw', 'DLmw')):
        if not 0 <= selected[ll_key] <= selected[l1_key] <= selected[accesses_key]:
            raise ValueError('Cachegrind misses do not conserve accesses')
    l1_miss = selected['D1mr'] + selected['D1mw']
    ll_miss = selected['DLmr'] + selected['DLmw']
    counts = [accesses - l1_miss, l1_miss - ll_miss, ll_miss]
    return dict(counts=counts, ratios=FirstHits(*counts).ratios,
                selected_events=selected, excluded_events=excluded,
                summary_events=summary, excluded_lines=sorted(excluded_lines))
