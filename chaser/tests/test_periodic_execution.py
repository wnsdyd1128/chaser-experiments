"""Real waf/APE integration plus bounded fake-process failure checks."""

import json
from pathlib import Path
import subprocess
import pytest

from chaser.periodic import aggregate, make_plan
from chaser.periodic_analysis import analyze
from chaser.periodic_build import SDK, check_layout, prepare, read_symbols
from chaser.periodic_dataset import load_batch
from tools.rtems_periodic import run
from tools.rtems_smoke import check_inputs
from test_periodic import configuration, evidence
from test_periodic_public import public_evidence


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    output = tmp_path_factory.mktemp('periodic') / 'snapshot'
    prepare(configuration(), output)
    return output


def test_waf_builds_three_sparc_elfs_from_one_workload_object(prepared):
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    layouts = json.loads((prepared / 'layout.json').read_text())
    assert layouts['g'] == layouts['c'] == layouts['p']
    commands = json.loads((prepared / 'build/compile_commands.json').read_text())
    assert len(commands) == 7
    assert sum(Path(r['file']).name == 'workload.c' for r in commands) == 1
    assert len({r['output'] for r in commands}) == 7
    for a in ('g', 'c', 'p'):
        elf = (prepared / f'build/{a}.exe').read_bytes()
        assert elf[:6] == b'\x7fELF\x01\x02'
        assert int.from_bytes(elf[18:20], 'big') == 2
    with pytest.raises(FileExistsError):
        prepare(configuration(), prepared)


def test_moved_or_resized_workload_symbol_is_rejected(prepared):
    symbols = read_symbols(prepared / 'build/p.exe')
    tasks = make_plan(configuration(), 2)['tasks']
    address, size = symbols['data_a']
    for changed in ((address + 32, size), (address, size + 1)):
        with pytest.raises(ValueError, match='layout mismatch'):
            check_layout({**symbols, 'data_a': changed}, tasks)


def test_actual_elf_with_shifted_section_is_rejected(prepared, tmp_path):
    moved = tmp_path / 'moved.exe'
    subprocess.run([str(SDK / 'bin/sparc-rtems6-objcopy'),
                    '--change-section-address', '.chaser_data=0x01001000',
                    str(prepared / 'build/p.exe'), str(moved)], check=True, capture_output=True)
    with pytest.raises(ValueError, match='layout mismatch'):
        check_layout(read_symbols(moved), make_plan(configuration(), 2)['tasks'])


def test_cpp_expands_all_sweeps_and_matches_all_final_elfs(prepared):
    result = analyze(prepared)
    assert result['cases']['a']['modeled_accesses'] == 800
    assert result['cases']['a']['clp'] == [799 / 800, 0, 1 / 800]
    assert result['cases']['b']['clp'] == [0, 792 / 800, 8 / 800]
    assert set(result['provenance']['a']['elf_hashes']) == {'g', 'c', 'p'}
    raw = json.loads((prepared / 'analysis/workload_ape.json').read_text())
    selected = json.loads((prepared / 'analysis/a.ape.json').read_text())
    assert all(f in raw['functions'] for f in selected['functions'])
    assert {tuple(f['annotations']) for f in selected['functions']} == {
        ('ape.analyze',), ('ape.inline',)}


def simulator(tmp_path, body):
    path = tmp_path / 'fake simulator'
    path.write_text('#!/bin/sh\n' + body + '\n')
    path.chmod(0o755)
    return path


def test_fresh_processes_reparse_the_same_raw_evidence(prepared, tmp_path):
    plan, records = public_evidence()
    content = '\n'.join('PERIODIC ' + json.dumps(r) for r in records)
    fake = simulator(tmp_path, 'echo "PID=$$"\n' + "cat <<'LOG'\n" + content + '\nLOG')
    directory = tmp_path / 'runs'
    rows = run(prepared, directory, architecture=2, runs=2, timeout=3, simulator=fake)
    assert all(r['execution_status'] == 'ok' for r in rows)
    assert load_batch(prepared, directory) == rows
    assert (directory / '0.log').read_text().splitlines()[0] != (
        directory / '1.log').read_text().splitlines()[0]
    stored = directory / 'measurements.jsonl'
    original = stored.read_text()
    for field, value in (('mean_elapsed_ns', 1), ('contract_id', 'wrong')):
        changed = [dict(r) for r in rows]
        changed[0][field] = value
        stored.write_text(''.join(json.dumps(r) + '\n' for r in changed))
        with pytest.raises(ValueError, match='measurement|contract'):
            load_batch(prepared, directory)
        stored.write_text(original)
    with pytest.raises(FileExistsError):
        run(prepared, directory, architecture=2, runs=1, simulator=fake)
    (directory / '0.log').write_text('changed')
    with pytest.raises(ValueError, match='log changed'):
        load_batch(prepared, directory)


@pytest.mark.parametrize('body', ['exit 2', 'echo partial', 'sleep 10', "echo 'PERIODIC []'"])
def test_failed_process_or_timeout_is_retained(prepared, tmp_path, body):
    directory = tmp_path / 'failed'
    rows = run(prepared, directory, architecture=2, runs=1, timeout=0.1,
               simulator=simulator(tmp_path, body))
    assert rows[0]['execution_status'] == 'failed'
    assert rows[0]['tet_ns'] is None
    assert (directory / '0.log').exists()
    assert len((directory / 'measurements.jsonl').read_text().splitlines()) == 1
    assert load_batch(prepared, directory) == rows


def test_trace_detects_wrong_domain_between_valid_job_endpoints():
    plan, records = evidence()
    records[0]['trace'] = 1
    records[1]['thread'], records[2]['thread'] = 101, 102
    records.extend([dict(kind='switch', thread=101, core=0, ns=1),
                    dict(kind='switch', thread=102, core=2, ns=2),
                    dict(kind='switch', thread=101, core=3, ns=3)])
    assert 'trace_domain' in aggregate(records, plan, trace=True)['errors']


def test_trace_must_include_every_worker():
    plan, records = evidence()
    records[0]['trace'] = 1
    records[1]['thread'], records[2]['thread'] = 101, 102
    records.append(dict(kind='switch', thread=101, core=0, ns=1))
    assert 'trace_completeness' in aggregate(records, plan, trace=True)['errors']
