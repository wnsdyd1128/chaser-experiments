"""Compile a solver with original helper storage through the common RTEMS path."""

import json
from pathlib import Path
import shutil

import pytest

from chaser.periodic.build import SDK, prepare
from chaser.periodic.polybench.sources import ROOT


@pytest.mark.skipif(not (SDK / 'bin/sparc-rtems6-gcc').exists() or shutil.which('clang-14') is None,
                    reason='requires RTEMS SDK and clang-14')
def test_solver_storage_and_vendor_warning_flags_are_isolated(tmp_path):
    config = json.loads((ROOT / 'configs/periodic-polybench/cholesky-medium.json').read_text())
    output = tmp_path / 'prepared'
    manifest = prepare(config, output)
    layout = json.loads((output / 'layout.json').read_text())
    assert layout['g'] == layout['c'] == layout['p']
    assert {row['symbol'] for row in layout['p']} == {'A', 'B'}
    assert all(row['size'] == 400 * 400 * 8 for row in layout['p'])
    commands = json.loads((output / 'build/compile_commands.json').read_text())
    for row in commands:
        vendor_flags = '-Wno-misleading-indentation' in row['arguments']
        assert vendor_flags == (Path(row['file']).name == 'workload.c')
    assert 'source/cholesky.c' in manifest['files']
    assert 'source/cholesky.h' in manifest['files']
    assert 'native-validation.json' in manifest['files']
    plan = json.loads((output / 'p/plan.json').read_text())
    native = json.loads((output / 'native-validation.json').read_text())
    assert plan['tasks'][0]['expected_checksum'] == native['expected_checksum']
