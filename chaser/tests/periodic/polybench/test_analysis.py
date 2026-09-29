"""Analyzer execution status must not hide unsupported original C inputs."""

import json
import shutil

import pytest

from chaser.periodic.build import YARDA
from chaser.periodic.polybench.analysis import analyze_source
from chaser.periodic.polybench.native import verify_native, write_sources
from chaser.periodic.polybench.sources import ROOT, benchmark_named
from chaser.periodic.polybench.suite import execution_passed


@pytest.mark.skipif(shutil.which('clang-14') is None or not (YARDA / 'backend/yarda_cpp').exists(),
                    reason='requires clang-14 and YARDA')
def test_original_atax_medium_executes_against_native_elf(tmp_path):
    benchmark = benchmark_named('atax')
    write_sources(benchmark, tmp_path / 'source')
    verify_native(tmp_path, benchmark)
    report = analyze_source(tmp_path / 'source/workload.c', {'native': tmp_path / 'native.exe'},
                            ROOT / 'rtems/baseline/cache.yaml', tmp_path / 'analysis')
    case = report['cases']['native']
    assert case['execution_status'] == 'passed'
    assert case['modeled_accesses'] == 1_280_002
    assert case['coverage']['complete'] is True
    assert case['trace_validation'] == 'not-validated'
    assert report['dataset_eligible'] is False
    raw = json.loads((tmp_path / 'analysis/kernel.ape.json').read_text())
    assert raw['metadata']['objects']['global::A']['shape'] == [390, 410]
    assert raw['metadata']['objects']['global::A']['elem_size'] == 8


def test_partial_suite_cannot_claim_success():
    assert not execution_passed({'periodic': False, 'benchmarks': {}})
    rows = {str(i): {'native': 'passed', 'native_yarda': {'execution_status': 'passed'}}
            for i in range(30)}
    report = {'periodic': False, 'benchmarks': rows}
    assert execution_passed(report)
    rows['5']['native_yarda']['execution_status'] = 'blocked'
    assert not execution_passed(report)
