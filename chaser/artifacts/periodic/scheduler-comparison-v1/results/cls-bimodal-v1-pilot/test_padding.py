"""Specification of hot-cold load padding in the 4d03b93 + C2 + padding code copy."""

import pytest

from chaser.periodic import patterns
from chaser.periodic.measurement import make_plan


def task(**extra):
    return dict(task_id='t00', pattern='hot-cold', distinct=6, hot_distinct=2, hot_repeats=3,
                cold_repeats=1, stride=32, sweeps=2, core=0, period_ticks=20, data_size=192, **extra)


def brute_force(rounds, state=patterns.PAD_SEED):
    for _ in range(rounds):
        state = (state ^ 1) * patterns.PAD_PRIME & 0xFFFFFFFF
    return state


@pytest.mark.parametrize('rounds', [0, 1, 2, 3, 7, 64, 255, 1000, 4097])
@pytest.mark.parametrize('state', [patterns.PAD_SEED, 12, 0xFFFFFFFF])
def test_closed_form_padding_state_matches_round_by_round_mixing(rounds, state):
    assert patterns.pad_final(rounds, state) == brute_force(rounds, state)


def test_unpadded_hot_cold_kernel_keeps_the_legacy_source():
    assert patterns.kernel_body(task()) == [
        '    for (int r = 0; r < 3; ++r)', '        for (int i = 0; i < 64; i += 32)',
        '            sum += data_t00[i];',
        '    for (int r = 0; r < 1; ++r)', '        for (int i = 64; i < 192; i += 32)',
        '            sum += data_t00[i];']


def test_padded_kernel_mixes_each_loaded_value_and_compares_the_known_final_state():
    body = patterns.kernel_body(task(pad_rounds=5))
    assert body[0] == f'    uint32_t pad = {patterns.PAD_SEED}U;'
    assert sum('uint32_t v = data_t00[i];' in line for line in body) == 2
    assert sum('for (int k = 0; k < 5; ++k)' in line for line in body) == 2
    # Every padding loop is preceded by the no-unroll pragma.
    assert [body[i - 1] for i, line in enumerate(body) if 'for (int k' in line] == [patterns.UNROLL_NONE] * 2
    # Each kernel call loads 2 * 3 hot + 4 cold elements and mixes each 5 times.
    assert body[-1] == f'    sum += pad != {patterns.pad_final(5 * (2 * 3 + 4))}U;'


def test_tail_starts_from_the_loaded_sum_and_its_rounds_enter_the_final_state():
    body = patterns.kernel_body(task(pad_tail=7))
    assert body[-5:-1] == ['    pad ^= sum;', patterns.UNROLL_NONE, '    for (int k = 0; k < 7; ++k)',
                           f'        pad = (pad ^ 1U) * {patterns.PAD_PRIME}U;']
    assert body[-1] == f'    sum += pad != {brute_force(7, patterns.PAD_SEED ^ 10)}U;'
    both = patterns.kernel_body(task(pad_rounds=5, pad_tail=7))
    assert both[-1] == f'    sum += pad != {brute_force(7, brute_force(5 * 10) ^ 10)}U;'


def test_padding_keeps_the_access_count_checksum_and_adds_padding_loop_trips():
    padded = make_plan(dict(workload_id='w', family_id='f', policy_id='p', horizon_ticks=40,
                            warmup_ticks=20, u_repeats=1, tasks=[task(pad_rounds=5, pad_tail=7)]),
                       2)['tasks'][0]
    assert padded['expected_checksum'] == 2 * (2 * 3 + 4)
    assert patterns.loop_iterations(padded) == patterns.loop_iterations(task()) + 2 * 10 * 5 + 2 * 7


@pytest.mark.parametrize('key,bad', [
    ('pad_rounds', -1), ('pad_rounds', 1.5), ('pad_rounds', patterns.MAX_PAD_ROUNDS + 1),
    ('pad_tail', -1), ('pad_tail', patterns.MAX_PAD_TAIL + 1)])
def test_invalid_padding_rounds_are_rejected(key, bad):
    with pytest.raises(ValueError, match=key):
        patterns.validate_pattern(task(**{key: bad}))


def test_padding_is_rejected_outside_hot_cold():
    cyclic = dict(task_id='t00', distinct=4, stride=32, sweeps=1, pad_rounds=1)
    with pytest.raises(ValueError, match='only valid for hot-cold'):
        patterns.validate_pattern(cyclic)
