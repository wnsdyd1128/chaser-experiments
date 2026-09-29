"""Compare unmodified upstream live-outs with the source adapter, including reset."""

import shutil

import pytest

from chaser.periodic.polybench.native import write_sources, verify_native
from chaser.periodic.polybench.sources import benchmark_named


@pytest.mark.skipif(shutil.which('clang-14') is None, reason='requires clang-14')
@pytest.mark.parametrize('name', ['atax', 'deriche', 'nussinov', 'cholesky'])
def test_original_medium_outputs_and_repeated_jobs_match(name, tmp_path):
    benchmark = benchmark_named(name)
    write_sources(benchmark, tmp_path / 'source')
    result = verify_native(tmp_path, benchmark)
    assert result['status'] == 'passed'
    assert 0 <= result['expected_checksum'] <= 2**32 - 1
    assert (tmp_path / 'original.dump').stat().st_size > 0
