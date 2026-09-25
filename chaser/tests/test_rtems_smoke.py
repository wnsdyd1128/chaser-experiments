import json
from pathlib import Path

import pytest

from chaser.periodic.smoke import make_plan, parse_log
from tools.rtems_smoke import check_inputs, prepare, run, write_editor_database

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    return {'kind': 'ca-csrd', 'threshold': 0.5, 'alpha': None,
            'isolated': [0], 'non_isolated': [1, 2, 3],
            'utilization': {'packed': 0.2, 'spread': 0.2, 'conflict': 0.2},
            'utilization_source': 'synthetic'}


def plan():
    cases = json.loads((ROOT / 'exports/locality.json').read_text())['cases']
    return make_plan(cases, configuration())


def log_for(p):
    rows = [f'SMOKE,version=1,cpus=4,mapping_hash={p["mapping_hash"]},release_ns=100']
    for task, core in p['mapping'].items():
        rows.append(f'JOB,task={task},core={core},start_core={core},end_core={core},'
                    'affinity_ok=1,cpu_ns=20,start_ns=110,completion_ns=150,check=1')
    return '\n'.join([*rows, 'CHASER SMOKE PASS'])


def test_plan_uses_allocator_and_keeps_mapping_identity():
    p = plan()
    assert p['mapping'] == {'conflict': 0, 'packed': 1, 'spread': 2}
    assert p['measurement_protocol'] == 'singleton-common-release-smoke-v1'
    assert len(p['mapping_hash']) == 64
    assert p == plan()


def test_invalid_or_incomplete_mapping_is_not_executable():
    cases = json.loads((ROOT / 'exports/locality.json').read_text())['cases']
    for changes in ({'isolated': [4]}, {'utilization': {'packed': 0.2}},
                    {'utilization': dict.fromkeys(('packed', 'spread', 'conflict'), 1.1)},
                    {'utilization_source': 'measured'}):
        with pytest.raises(ValueError):
            make_plan(cases, {**configuration(), **changes})


def test_log_reports_measured_metrics_without_training_labels():
    p = plan()
    result = parse_log(log_for(p), p)
    assert result['sum_job_cpu_ns'] == 60
    assert result['makespan_ns'] == 50
    assert result['sum_response_ns'] == 150
    assert not {'tet', 'tat', 'label', 'architecture'} & result.keys()


@pytest.mark.parametrize('mutation', [
    lambda log: log.replace('CHASER SMOKE PASS', ''),
    lambda log: log.replace('affinity_ok=1', 'affinity_ok=0', 1),
    lambda log: log.replace('start_core=0', 'start_core=3', 1),
    lambda log: log.replace('check=1', 'check=0', 1),
    lambda log: log.replace('cpu_ns=20', 'cpu_ns=0', 1),
    lambda log: log.replace('completion_ns=150', 'completion_ns=90', 1),
    lambda log: log.replace('cpus=4', 'cpus=1'),
    lambda log: log + '\n' + log.splitlines()[1],
    lambda log: log.replace('JOB,task=packed', 'JOB,task=unknown'),
    lambda log: log.replace('mapping_hash=', 'mapping_hash=x'),
])
def test_bad_or_partial_execution_is_rejected(mutation):
    p = plan()
    with pytest.raises(ValueError):
        parse_log(mutation(log_for(p)), p)


@pytest.fixture
def prepared(tmp_path):
    output = tmp_path / 'prepared'
    prepare(configuration(), json.loads((ROOT / 'exports/locality.json').read_text()), output)
    return output


def fake_simulator(tmp_path, body):
    path = tmp_path / 'simulator'
    path.write_text('#!/bin/sh\n' + body + '\n')
    path.chmod(0o755)
    return path


def test_preparation_builds_sparc_and_refuses_overwrite_or_changed_inputs(prepared):
    elf = (prepared / 'workload.exe').read_bytes()
    assert elf[:6] == b'\x7fELF\x01\x02'
    assert int.from_bytes(elf[18:20], 'big') == 2
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    with pytest.raises(FileExistsError):
        prepare(configuration(), json.loads((ROOT / 'exports/locality.json').read_text()), prepared)
    (prepared / 'config.h').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        run(prepared, runs=1, timeout=1)
    assert not (prepared / 'runs').exists()


def test_build_uses_the_recorded_compiler_despite_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv('RTEMS_ROOT', str(tmp_path / 'unrelated-toolchain'))
    monkeypatch.setenv('CC', '/nonexistent/cc')
    output = tmp_path / 'prepared'
    prepare(configuration(), json.loads((ROOT / 'exports/locality.json').read_text()), output)
    manifest = json.loads((output / 'manifest.json').read_text())
    assert 'waf' in manifest['build_command']
    assert '--rtems-root=/opt/rtems/6' in manifest['build_command']
    assert manifest['compiler'] in (output / 'build.log').read_text()
    database = json.loads((output / 'build/compile_commands.json').read_text())
    assert len(database) == 2
    assert all(row['arguments'][0] == manifest['compiler'] for row in database)


def test_editor_database_uses_real_config_for_workspace_source(prepared, tmp_path):
    destination = tmp_path / 'compile_commands.json'
    write_editor_database(prepared, destination)
    rows = json.loads(destination.read_text())
    assert len(rows) == 1
    row = rows[0]
    assert row['file'] == str(ROOT / 'rtems/smoke/init.c')
    assert row['file'] in row['arguments']
    assert Path(row['directory']).is_dir()
    assert (Path(row['directory']) / '../config.h').resolve() == prepared / 'config.h'
    (prepared / 'config.h').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        write_editor_database(prepared, destination)


def test_runner_starts_fresh_processes_and_retains_raw_logs(prepared, tmp_path):
    log = log_for(json.loads((prepared / 'plan.json').read_text()))
    simulator = fake_simulator(tmp_path, 'printf "PID=%s\\n" "$$"\n'
                               + "cat <<'LOG'\n" + log + '\nLOG')
    records = run(prepared, runs=2, timeout=3, simulator=simulator)
    assert [row['execution_status'] for row in records] == ['ok', 'ok']
    pids = [(prepared / 'runs' / row['log']).read_text().splitlines()[0] for row in records]
    assert pids[0] != pids[1]
    assert all(row['log_hash'] and row['sum_job_cpu_ns'] == 60 for row in records)
    with pytest.raises(FileExistsError):
        run(prepared, runs=1, timeout=3, simulator=simulator)


@pytest.mark.parametrize('body', ['exit 2', 'echo CHASER SMOKE PASS', 'sleep 10'])
def test_runner_preserves_failures_and_timeout_without_metrics(prepared, tmp_path, body):
    simulator = fake_simulator(tmp_path, body)
    records = run(prepared, runs=1, timeout=0.1, simulator=simulator)
    assert records[0]['execution_status'] == 'failed'
    assert 'makespan_ns' not in records[0]
    assert len((prepared / 'runs/measurements.jsonl').read_text().splitlines()) == 1
    assert (prepared / 'runs/0.log').exists()
