"""CAAS normalization shared by Global RD and L1 CSRD."""


def ca_from_histogram(histogram):
    """Exclude cold accesses; counts already include all loop repetitions."""
    reuses = sum(histogram.values())
    weighted = sum(int(rd) * count for rd, count in histogram.items())
    return reuses / (reuses + weighted) if reuses else None


def ca_caas(block):
    """Compute CA from one Global-RD export block."""
    return ca_from_histogram(block['profile']['histogram'])


def ca_csrd(task):
    """Use only L1 CSRD; LLC's miss-stream population is not combined."""
    return ca_from_histogram(task['l1']['csrd_histogram'])
