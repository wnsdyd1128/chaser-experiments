import math

import pytest

from chaser.features import FEATURE_NAMES, build_features, locality_scalar


def task(ca, utilization):
    return {'ca_caas_element': ca, 'ca_global_line': 1.0,
            'ca_csrd_l1': 0.5, 'cls': {'0.5': 0.75}, 'utilization': utilization}


def test_scalar_selection_and_undefined_values():
    row = task(None, 0.2)
    assert locality_scalar('caas-ca', row) is None
    assert locality_scalar('ca-line', row) == 1.0
    assert locality_scalar('ca-csrd', row) == 0.5
    assert locality_scalar('cls', row, alpha=0.5) == 0.75
    for kind, alpha in [('unknown', None), ('cls', None), ('cls', 0.7)]:
        with pytest.raises(ValueError):
            locality_scalar(kind, row, alpha=alpha)


def test_feature_order_and_population_standard_deviation():
    rows = [task(0.0, 0.1), task(0.5, 0.2), task(1.0, 0.6)]
    result = build_features(rows, 'caas-ca')
    assert FEATURE_NAMES == ('ca_mean', 'ca_std', 'ca_min', 'ca_max', 'ca_median',
                             'u_mean', 'u_std', 'u_min', 'u_max', 'u_median', 'u_sum')
    assert result == pytest.approx([0.5, math.sqrt(1 / 6), 0, 1, 0.5,
                                   0.3, math.sqrt(0.14 / 3), 0.1, 0.6, 0.2, 0.9])
    assert build_features(list(reversed(rows)), 'caas-ca') == result
    assert build_features(rows, 'ca-csrd')[5:] == result[5:]
    assert build_features(rows, 'cls', alpha=0.5)[:5] == [0.75, 0, 0.75, 0.75, 0.75]


def test_single_task_and_even_median():
    assert build_features([task(0.5, 0.2)], 'caas-ca') == [
        0.5, 0, 0.5, 0.5, 0.5, 0.2, 0, 0.2, 0.2, 0.2, 0.2]
    assert build_features([task(0, 0), task(1, 1)], 'caas-ca')[4] == 0.5


@pytest.mark.parametrize('rows', [[], [task(None, 0.2)], [task(0.5, None)],
                                 [task(float('nan'), 0.2)], [task(0.5, float('inf'))],
                                 [task(-0.1, 0.2)], [task(0.5, -1)]])
def test_invalid_samples_are_rejected(rows):
    with pytest.raises(ValueError):
        build_features(rows, 'caas-ca')
