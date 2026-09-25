import json
from pathlib import Path
import subprocess

import pytest

from chaser.locality.analyzer import analyze_task

ROOT = Path(__file__).resolve().parents[1]


def run(tmp_path, **kwargs):
    return analyze_task('chaser_packed', ape=ROOT / 'rtems/baseline/build/packed.ape.json',
                        elf=ROOT / 'rtems/baseline/build/packed.exe',
                        cache=ROOT / 'rtems/baseline/cache.yaml',
                        source=ROOT / 'rtems/baseline/workload.c',
                        executable=ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp',
                        output_dir=tmp_path / 'analysis', max_cumulative_loop_iterations=2000000,
                        max_source_accesses=1100000, **kwargs)


def test_actual_cpp_analysis_has_matching_values_and_provenance(tmp_path):
    result = run(tmp_path)
    baseline = json.loads((ROOT / 'exports/locality.json').read_text())['cases']['packed']
    for key in ('ca_caas_element', 'ca_global_line', 'ca_csrd_l1', 'clp', 'cls'):
        assert result['case'][key] == baseline[key]
    assert len(result['provenance']['runs']) == 3
    assert all(r['wall_seconds'] >= 0 and r['started_at'] for r in result['provenance']['runs'])
    assert len(result['provenance']['analyzer_binary_hash']) == 64
    assert result['provenance']['analyzer_commit'] in baseline['provenance']['tool_version']


def test_failure_never_writes_success_artifact(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(2, args[0])
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        run(tmp_path)
    assert not (tmp_path / 'analysis/analysis.json').exists()


def test_global_program_profile_not_block_histogram_is_used(tmp_path, monkeypatch):
    actual = subprocess.run
    def alter(argv, **kwargs):
        result = actual(argv, **kwargs)
        if '--granularity' in argv:
            output = Path(argv[-1])
            data = json.loads(output.read_text())
            data['program']['histogram'] = {'3': 2}
            output.write_text(json.dumps(data))
        return result
    monkeypatch.setattr(subprocess, 'run', alter)
    result = run(tmp_path)
    assert result['case']['ca_caas_element'] == 0.25
    assert result['case']['ca_global_line'] == 0.25


@pytest.mark.parametrize('mismatch', ['task', 'hash'])
def test_mismatched_result_is_rejected(tmp_path, monkeypatch, mismatch):
    actual = subprocess.run
    def alter(argv, **kwargs):
        result = actual(argv, **kwargs)
        if '--analysis' in argv:
            output = Path(argv[-1])
            data = json.loads(output.read_text())
            if mismatch == 'task':
                data['tasks'][0]['task_id'] = 'different'
            else:
                data['inputs']['elf_sha256'] = 'different'
            output.write_text(json.dumps(data))
        return result
    monkeypatch.setattr(subprocess, 'run', alter)
    with pytest.raises(ValueError, match='matching result task|input hashes'):
        run(tmp_path)
    assert not (tmp_path / 'analysis/analysis.json').exists()


def test_multifunction_ape_is_rejected_before_execution(tmp_path, monkeypatch):
    actual = Path.read_text
    def read(path, *args, **kwargs):
        value = actual(path, *args, **kwargs)
        if path.name == 'packed.ape.json':
            data = json.loads(value)
            data['functions'] *= 2
            return json.dumps(data)
        return value
    monkeypatch.setattr(Path, 'read_text', read)
    with pytest.raises(ValueError, match='one matching APE'):
        run(tmp_path)
    assert not (tmp_path / 'analysis').exists()
