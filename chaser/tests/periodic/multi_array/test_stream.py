from copy import deepcopy
import pytest
from chaser.periodic.analysis import check_stream
from chaser.periodic.measurement import make_plan
from chaser.periodic.kernels import reference_events, task_from_plan
from chaser.periodic.workload import ArraySpec


def test_gemm_literal_stream_includes_stores_and_final_hash(config):
    plan = make_plan(config, 2)
    task = plan['tasks'][0]
    registry = {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}
    events = list(reference_events(task_from_plan(task), registry))
    assert [(e.array_id, e.offset_bytes, e.operation) for e in events[:7]] == [
        ('a0', 0, 'load'), ('b0', 0, 'load'), ('a0', 4, 'load'),
        ('b0', 8, 'load'), ('a0', 8, 'load'), ('b0', 16, 'load'), ('c0', 0, 'store')]
    assert [(e.array_id, e.offset_bytes, e.operation) for e in events[-4:]] == [
        ('c0', i, 'load') for i in (0, 4, 8, 12)]
    assert len(events) == 60
    exported = [dict(object_id='global::'+registry[e.array_id].symbol,
                     linked_address=registry[e.array_id].address+e.offset_bytes,
                     access_size=e.access_size_bytes, operation=e.operation) for e in events]
    addresses = {a['symbol']: a['address'] for a in plan['arrays']}
    check_stream(task, exported, addresses, arrays=plan['arrays'])
    for field, value in [('object_id', 'global::data_b0'), ('operation', 'load'),
                         ('access_size', 1), ('linked_address', 0)]:
        wrong = deepcopy(exported)
        wrong[6][field] = value
        with pytest.raises(ValueError): check_stream(task, wrong, addresses, arrays=plan['arrays'])
    with pytest.raises(ValueError): check_stream(task, exported[:-1], addresses, arrays=plan['arrays'])


def test_paired_typed_offsets_and_checksum(config):
    config['arrays'] = config['arrays'][:2]
    config['tasks'] = [dict(task_id='pair', pattern='paired-read', arrays={
        'a': dict(array_id='a0', offset_elements=1), 'b': dict(array_id='b0', offset_elements=1)},
        distinct=3, stride_bytes=8, sweeps=2, core=0, period_ticks=10)]
    plan = make_plan(config, 2)
    task = plan['tasks'][0]
    assert task['expected_checksum'] == 18
    assert [(e.array_id, e.offset_bytes) for e in reference_events(
        task_from_plan(task), {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']})] == [
        (name, offset) for offset in (4, 12, 20, 4, 12, 20) for name in ('a0', 'b0')]
    config['tasks'][0]['arrays']['a']['offset_elements'] = 2
    with pytest.raises(ValueError): make_plan(config, 2)
