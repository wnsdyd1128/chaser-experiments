from dataclasses import replace

import pytest

from chaser.labeling import Measurement, label_measurements


def measurements():
    return [Measurement('w', a, 'four-core', 'allocator-v1', f'map-{a}', str(r),
                        tet, tat, 'ok', 'synthetic')
            for a, tats, tet in [(0, [1, 100, 2], 8), (1, [3, 3, 3], 2),
                                  (2, [4, 4, 4], 1)]
            for r, tat in enumerate(tats)]


def test_median_not_mean_selects_label_and_ties_are_recorded():
    rows = measurements()
    result = label_measurements(rows, expected_runs=3)
    assert result.label == 0
    assert result.medians[0] == (2, 8)
    rows = [replace(r, tat=10, tet=3 if r.architecture == 0 else 2) for r in rows]
    result = label_measurements(rows, expected_runs=3)
    assert result.label == 1
    assert result.tat_ties == (0, 1, 2)
    assert result.final_ties == (1, 2)


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'failed', 'mapping', 'allocator', 'unit'])
def test_incomparable_measurements_are_rejected(change):
    rows = measurements()
    if change == 'missing':
        rows.pop()
    elif change == 'duplicate':
        rows[-1] = rows[-2]
    else:
        field, value = {'failed': ('execution_status', 'failed'),
                        'mapping': ('mapping_hash', 'different'),
                        'allocator': ('allocator_id', 'different'),
                        'unit': ('time_unit', 'us')}[change]
        rows[-1] = replace(rows[-1], **{field: value})
    with pytest.raises(ValueError):
        label_measurements(rows, expected_runs=3)
