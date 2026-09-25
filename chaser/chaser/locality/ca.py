"""CAAS normalization shared by Global RD and L1 CSRD."""

from collections.abc import Mapping
from typing import TypeAlias, TypedDict


Histogram: TypeAlias = Mapping[int, int] | Mapping[str, int]


class GlobalRDProfile(TypedDict):
    histogram: Histogram


class GlobalRDBlock(TypedDict):
    profile: GlobalRDProfile


class L1Profile(TypedDict):
    csrd_histogram: Histogram


class CSRDTask(TypedDict):
    l1: L1Profile


def ca_from_histogram(histogram: Histogram) -> float | None:
    """Exclude cold accesses; counts already include all loop repetitions."""
    reuses = sum(histogram.values())
    weighted = sum(int(rd) * count for rd, count in histogram.items())
    return reuses / (reuses + weighted) if reuses else None


def ca_caas(block: GlobalRDBlock) -> float | None:
    """Compute CA from one Global-RD export block."""
    return ca_from_histogram(block['profile']['histogram'])


def ca_csrd(task: CSRDTask) -> float | None:
    """Use only L1 CSRD; LLC's miss-stream population is not combined."""
    return ca_from_histogram(task['l1']['csrd_histogram'])
