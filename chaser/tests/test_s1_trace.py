"""Execution trace scope and ordering are independent of cache outcomes."""

import io

import pytest

from chaser.s1_trace import parse_lackey, compare_accesses, cache_lines
from chaser.cache_reference import CacheLevel, simulate


def parse(text, **kwargs):
    return parse_lackey(io.StringIO(text), function=(0x100, 0x20),
                        array=(0x200, 0x40), max_references=20, **kwargs)


def test_scope_filters_before_replay_and_preserves_modify_order():
    accesses, stats = parse('I 90,1\n L 200,1\nI 100,1\n L 200,1\n'
                            'I 101,1\n S 300,1\n M 21f,2\n L 200,1\n'
                            'I 120,1\n S 200,1\n')
    assert accesses == [('load', 0x200, 1), ('load', 0x21f, 2),
                        ('store', 0x21f, 2), ('load', 0x200, 1)]
    assert list(cache_lines(accesses, 32)) == [16, 16, 17, 16, 17, 16]
    assert stats['excluded_outside_roi'] == 2
    assert stats['excluded_outside_array'] == 1
    simple, _ = parse('I 100,1\n L 200,1\n S 300,1\n L 200,1\nI 120,1\n')
    assert simulate(cache_lines(simple, 32), CacheLevel(32, 32, 1),
                    CacheLevel(32, 32, 1)).l1 == 1


@pytest.mark.parametrize('text', [
    'I 90,1\n',  # no entry
    'I 101,1\n L 200,1\nI 120,1\n',  # entry inside function
    'I 100,1\n L 200,1\n',  # all loads present, no exit
    'I 100,1\nI 120,1\nI 100,1\nI 120,1\n',
    ' L 200,1\nI 100,1\nI 120,1\n',
    'I 100,1\n L xyz,1\nI 120,1\n',
    'I 100,1\n L 200,0\nI 120,1\n',
    'I 100,1\n L ffffffffffffffff,2\nI 120,1\n',
    'I 100,1\n L 1ff,2\nI 120,1\n',
    'I 100,1\n L 23f,2\nI 120,1\n',
    'I 100,1\n L 200,1\nI 120,1',  # incomplete final line
])
def test_invalid_or_incomplete_trace_is_rejected(text):
    with pytest.raises(ValueError):
        parse(text)


def test_selected_reference_budget():
    with pytest.raises(ValueError, match='reference limit'):
        parse('I 100,1\n' + ' L 200,1\n' * 21 + 'I 120,1\n')


def test_sequence_comparison_detects_same_line_reordering_and_operations():
    expected = [('load', 512, 1), ('load', 513, 1)]
    for observed in (expected[::-1], [('store', 512, 1), expected[1]],
                     expected[:1], expected + expected[:1], [('load', 512, 2), expected[1]]):
        result = compare_accesses(expected, observed)
        assert result['equal'] is False
        assert result['first_mismatch'] is not None
    result = compare_accesses(expected, expected)
    assert result['equal'] is True
    assert result['expected_sha256'] == result['observed_sha256']
