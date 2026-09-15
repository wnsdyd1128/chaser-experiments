"""Check RDH from newly compiled C jobs, never a Python YARDA replay."""

import json
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1] / 'rtems/baseline'


def profiles(name):
    data = json.loads((ROOT.parents[1] / f'exports/{name}.rdh.json').read_text())
    assert data['granularity'] == ('element' if name == 'element' else 'cache-line')
    return {b['name'].split()[0]: b['profile'] for b in data['blocks']}


def test_element_rd_and_caas_closed_form():
    blocks = profiles('element')
    assert set(blocks) == {'chaser_packed', 'chaser_spread', 'chaser_conflict'}
    d, s = 8, 65537
    for profile in blocks.values():
        assert profile['histogram'] == {'0': d * s, '7': d * (s - 1)}
        assert profile['cold_misses'] == d
        reuse = profile['total_reuses']
        assert reuse == d * (2 * s - 1)
        assert reuse / (reuse + 7 * d * (s - 1)) == (2 * s - 1) / (9 * s - 8)


def test_line_grouping_control():
    line = profiles('line')
    assert line['chaser_packed']['histogram'] == {'0': 2 * 8 * 65537 - 1}
    assert line['chaser_packed']['cold_misses'] == 1
    element = profiles('element')
    for name in ('chaser_spread', 'chaser_conflict'):
        assert line[name] == element[name]


def test_default_limit_rejects_large_workload(tmp_path):
    result = subprocess.run([str(ROOT / 'build/yarda/backend/yarda_cpp'),
                             str(ROOT / 'build/workload_ape.json'), '--mode', 'unroll',
                             '--granularity', 'element', '--export', str(tmp_path / 'rdh.json')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'cumulative loop iteration count exceeds' in result.stderr


@pytest.mark.parametrize('case', ['packed', 'spread', 'conflict'])
def test_rtems_elf_is_sparc_executable(case):
    elf = ROOT / f'build/{case}.exe'
    data = elf.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x02'  # ELF32, big endian
    assert int.from_bytes(data[16:18], 'big') == 2  # ET_EXEC
    assert int.from_bytes(data[18:20], 'big') == 2  # EM_SPARC
    symbols = subprocess.check_output(['/opt/rtems/6/bin/sparc-rtems6-nm', str(elf)], text=True)
    names = {line.split()[-1] for line in symbols.splitlines() if line.split()}
    for candidate in ('packed', 'spread', 'conflict'):
        assert (f'chaser_{candidate}' in names) == (candidate == case)
        assert (f'chaser_check_{candidate}' in names) == (candidate == case)
