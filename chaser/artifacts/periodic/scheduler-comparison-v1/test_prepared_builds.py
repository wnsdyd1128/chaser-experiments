"""Specification tests for prepared_builds.py (no RTEMS toolchain: a fake waf writes fixed outputs)."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepared_builds as pb

OUTPUTS = {'build/g.exe': b'elf-g', 'build/source/init.c.1.o': b'object-1'}
FAKE_WAF = '''import pathlib, sys
outputs = {outputs!r}
if 'build' in sys.argv:
    for name, data in outputs.items():
        path = pathlib.Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_prepared(root: Path, outputs=OUTPUTS, tool: Path | None = None, configured_in: Path | None = None) -> Path:
    prepared = root / 'case' / 'wfd' / 'prepared'
    prepared.mkdir(parents=True)
    (prepared / 'waf').write_text(FAKE_WAF.format(outputs=outputs))
    (prepared / '.lock-waf_linux_build').write_text(
        f"argv = ['waf']\ntop_dir = '{(configured_in or prepared).resolve()}'\n")
    (prepared / 'build.log').write_text('original log\n')
    (prepared / 'build').mkdir()
    (prepared / 'build' / 'compile_commands.json').write_text('[]')
    for name, data in outputs.items():
        (prepared / name).parent.mkdir(parents=True, exist_ok=True)
        (prepared / name).write_bytes(data)
    files = {name: sha((prepared / name).read_bytes())
             for name in ('build.log', 'build/compile_commands.json', *outputs)}
    tools = {str(tool): sha(tool.read_bytes())} if tool else {}
    (prepared / 'manifest.json').write_text(json.dumps(dict(
        schema_version=1, build_command=[sys.executable, 'waf', 'configure', 'build', '-v'],
        tools=tools, files=files)))
    return prepared


def test_find_prepared_lists_dirs_with_a_manifest_only(tmp_path):
    prepared = make_prepared(tmp_path)
    (tmp_path / 'other' / 'prepared').mkdir(parents=True)
    assert pb.find_prepared([tmp_path]) == [prepared]


def test_intact_dir_is_complete(tmp_path):
    assert pb.status(make_prepared(tmp_path)) == 'complete'


def test_prune_removes_only_manifest_listed_executables_and_objects(tmp_path):
    prepared = make_prepared(tmp_path)
    freed = pb.prune(prepared)
    assert freed == sum(len(v) for v in OUTPUTS.values())
    assert not any((prepared / name).exists() for name in OUTPUTS)
    assert (prepared / 'build.log').read_text() == 'original log\n'
    assert (prepared / 'build/compile_commands.json').exists()
    assert pb.status(prepared) == 'pruned'


def test_prune_refuses_a_dir_whose_files_differ_from_the_manifest(tmp_path):
    prepared = make_prepared(tmp_path)
    (prepared / 'build/g.exe').write_bytes(b'changed')
    with pytest.raises(ValueError):
        pb.prune(prepared)
    assert (prepared / 'build/source/init.c.1.o').exists()


def test_restore_rebuilds_byte_identical_outputs_and_keeps_the_build_log(tmp_path):
    prepared = make_prepared(tmp_path)
    pb.prune(prepared)
    pb.restore(prepared)
    assert pb.status(prepared) == 'complete'
    assert (prepared / 'build.log').read_text() == 'original log\n'


def test_a_copy_configured_in_another_directory_is_reported_and_never_pruned(tmp_path):
    prepared = make_prepared(tmp_path, configured_in=tmp_path / 'original' / 'prepared')
    assert pb.status(prepared) == 'copied'
    with pytest.raises(ValueError, match='another directory'):
        pb.prune(prepared)
    assert all((prepared / name).exists() for name in OUTPUTS)


def test_restore_of_a_complete_dir_does_nothing(tmp_path):
    prepared = make_prepared(tmp_path)
    assert pb.restore(prepared) is False


def test_restore_refuses_when_a_recorded_tool_changed(tmp_path):
    tool = tmp_path / 'gcc'
    tool.write_bytes(b'gcc 13.3')
    prepared = make_prepared(tmp_path, tool=tool)
    pb.prune(prepared)
    tool.write_bytes(b'gcc 14')
    with pytest.raises(RuntimeError, match='tool'):
        pb.restore(prepared)


def test_restore_reports_a_rebuild_that_differs_from_the_manifest(tmp_path):
    prepared = make_prepared(tmp_path)
    pb.prune(prepared)
    (prepared / 'waf').write_text(FAKE_WAF.format(outputs={**OUTPUTS, 'build/g.exe': b'other'}))
    with pytest.raises(RuntimeError, match='g.exe'):
        pb.restore(prepared)
