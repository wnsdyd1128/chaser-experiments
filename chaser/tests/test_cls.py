import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from chaser.cls import cls, level_weights
from chaser.allocator import CoreGroups, allocate
from chaser.features import build_features
from chaser.rf import fit_rf
from tools.export_locality import summary

ALPHAS = (0.0, 0.3, 0.5, 0.7, 1.0)
CACHE = {'l1_capacity': 16384, 'llc_capacity': 2097152}


def profile(l1, llc, miss):
    return {'modeled_accesses': 100, 'l1_first_hit_ratio': l1,
            'llc_first_hit_ratio': llc, 'all_cache_miss_ratio': miss}


@pytest.mark.parametrize('ratios', [(1, 0, 0), (0, 1, 0), (0, 0, 1),
                                    (0.2, 0.7, 0.1)])
def test_cls_invariants(ratios):
    row = profile(*ratios)
    values = [cls(row, CACHE, alpha) for alpha in ALPHAS]
    assert all(0 <= value <= 1 for value in values)
    assert values[0] == pytest.approx(1 - ratios[2])
    assert values == sorted(values, reverse=True)
    if ratios[1] > 0:
        assert all(a > b for a, b in zip(values, values[1:]))


def test_weights_use_capacity_and_match_gr740():
    expected = [1, 0.2332582479, 0.08838834765, 0.0334929207, 0.0078125]
    for alpha, weight in zip(ALPHAS, expected):
        assert level_weights(CACHE, alpha) == pytest.approx({'L1': 1, 'LLC': weight})
    assert level_weights({'l1_capacity': 100, 'llc_capacity': 400}, 0.5)['LLC'] == 0.5


def test_empty_profile_is_undefined():
    row = {**profile(None, None, None), 'modeled_accesses': 0}
    assert cls(row, CACHE, 0.5) is None


@pytest.mark.parametrize('alpha', [-1, float('nan'), float('inf')])
def test_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        cls(profile(1, 0, 0), CACHE, alpha)


@pytest.mark.parametrize('cache', [{'l1_capacity': 0, 'llc_capacity': 100},
                                   {'l1_capacity': 200, 'llc_capacity': 100},
                                   {'l1_capacity': 1, 'llc_capacity': float('inf')}])
def test_invalid_capacity(cache):
    with pytest.raises(ValueError):
        level_weights(cache, 0.5)


@pytest.mark.parametrize('ratios', [(None, 0, 1), (-0.1, 0.2, 0.9),
                                    (float('nan'), 0, 1), (0.8, 0.8, 0),
                                    (0.1, 0.1, 0.1)])
def test_invalid_nonempty_profile(ratios):
    with pytest.raises(ValueError):
        cls(profile(*ratios), CACHE, 0.5)


def test_sweep_preserves_sources_and_connects_consumers(tmp_path):
    paths = [tmp_path / 'first.json', tmp_path / 'second.json']
    for path in paths:
        subprocess.run([sys.executable, '-m', 'tools.run_cls_sweep', '--alpha',
                        '0,0.3,0.5,0.7,1.0', '--output', str(path)], check=True)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    result = json.loads(paths[0].read_text())
    assert result == summary()
    cases = result['cases']
    for name, case in cases.items():
        source = Path(f'exports/{name}.csrd.json')
        raw = json.loads(source.read_text())
        assert result['source_sha256'][source.name] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert case['provenance']['tool_version'] == raw['tool_version']
        assert case['provenance']['inputs'] == raw['inputs']
        assert case['provenance']['cache_hierarchy'] == raw['cache_hierarchy']
        assert case['modeled_accesses'] == raw['tasks'][0]['modeled_accesses']
        assert set(case['cls']) == {str(a) for a in ALPHAS}
    workloads = [{'packed': 0.1}, {'spread': 0.5}, {'conflict': 0.9}]
    models = [fit_rf(cases, workloads, [0, 1, 2], 'cls', seed=42, alpha=a)
              for a in ALPHAS]
    assert len({id(m.pipeline['rf']) for m in models}) == 5
    assert len({id(m.pipeline['scale']) for m in models}) == 5
    for alpha, model in zip(ALPHAS, models):
        features = [build_features([{**cases[t], 'utilization': u}], 'cls', alpha=alpha)
                    for row in workloads for t, u in row.items()]
        assert model.predict(cases, workloads).tolist() == model.pipeline.predict(features).tolist()
        placement = allocate(cases, {'conflict': 0.2}, CoreGroups((0,), (1,)),
                             kind='cls', alpha=alpha, threshold=0.6)
        assert placement.mapping == {'conflict': 1 if alpha < 0.5 else 0}


def test_cli_exports_only_requested_alphas(tmp_path):
    output = tmp_path / 'custom.json'
    subprocess.run([sys.executable, '-m', 'tools.run_cls_sweep', '--alpha', '0,1',
                    '--output', str(output)], check=True)
    result = json.loads(output.read_text())
    assert all(set(case['cls']) == {'0.0', '1.0'} for case in result['cases'].values())


@pytest.mark.parametrize('alpha', ['nan', '-1', '', 'bad'])
def test_cli_rejects_invalid_alpha_without_overwriting_output(tmp_path, alpha):
    output = tmp_path / 'existing.json'
    output.write_text('preserve me')
    result = subprocess.run([sys.executable, '-m', 'tools.run_cls_sweep',
                             f'--alpha={alpha}', '--output', str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert output.read_text() == 'preserve me'
