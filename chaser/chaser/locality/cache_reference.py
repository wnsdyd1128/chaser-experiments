"""Independent cold LRU demand-cache reference; does not compute reuse distance."""

from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheLevel:
    size_bytes: int
    line_bytes: int
    ways: int

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 for n in
               (self.size_bytes, self.line_bytes, self.ways)):
            raise ValueError('Cache geometry requires positive integers')
        if self.size_bytes % (self.line_bytes * self.ways):
            raise ValueError('Cache capacity must contain an integral number of sets')

    @property
    def lines(self) -> int:
        return self.size_bytes // self.line_bytes

    @property
    def sets(self) -> int:
        return self.lines // self.ways


@dataclass(frozen=True)
class FirstHits:
    l1: int
    llc: int
    miss: int

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in (self.l1, self.llc, self.miss)):
            raise ValueError('First-hit counts must be nonnegative integers')

    @property
    def total(self) -> int:
        return self.l1 + self.llc + self.miss

    @property
    def ratios(self) -> tuple[float, float, float] | None:
        return tuple(n / self.total for n in (self.l1, self.llc, self.miss)) if self.total else None


def validate_hierarchy(l1: CacheLevel, llc: CacheLevel) -> None:
    if l1.line_bytes != llc.line_bytes or l1.size_bytes > llc.size_bytes:
        raise ValueError('Require equal line sizes and L1 capacity <= LLC capacity')


def simulate(lines: Iterable[int], l1: CacheLevel, llc: CacheLevel) -> FirstHits:
    """Replay absolute line IDs with allocation on all demand misses.

    LLC sees only L1 misses. Levels retain independent residency, without
    back invalidation, victim insertion, writeback traffic, or prefetching.
    Input is already expanded into line references, in source-access order.
    """
    validate_hierarchy(l1, llc)
    residents = [{}, {}]
    hits = [0, 0, 0]
    for line in lines:
        if type(line) is not int or line < 0:
            raise ValueError('Line IDs must be nonnegative integers')
        for index, level in enumerate((l1, llc)):
            cache_set = residents[index].setdefault(line % level.sets, OrderedDict())
            if line in cache_set:
                cache_set.move_to_end(line)
                hits[index] += 1
                break
            if len(cache_set) == level.ways:
                cache_set.popitem(last=False)
            cache_set[line] = None
        else:
            hits[2] += 1
    return FirstHits(*hits)
