"""The source adapter must retain the published suite, types and dimensions."""

import pytest
from chaser.periodic.polybench.sources import benchmarks, render


def test_suite_contains_all_thirty_original_benchmarks():
    suite = benchmarks()
    assert len(suite) == 30
    assert len({b.name for b in suite}) == 30
    assert {'atax', 'nussinov', 'heat-3d', 'cholesky'} <= {b.name for b in suite}


@pytest.mark.parametrize('benchmark', benchmarks(), ids=lambda b: b.name)
def test_adapter_retains_original_kernel_body(benchmark):
    rendered = render(benchmark)
    original = benchmark.source.read_text()
    assert original[original.index('#pragma scop'):original.index('#pragma endscop')] in rendered
    assert '#define MEDIUM_DATASET' in rendered
    assert 'uint32_t task_job_polybench(void)' in rendered


def test_original_atax_medium_dimensions():
    atax = next(b for b in benchmarks() if b.name == 'atax')
    assert atax.dimensions == {'M': 390, 'N': 410}
    assert atax.element_type == 'double'
