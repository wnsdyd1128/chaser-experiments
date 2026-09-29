"""Typed workload records preserve the public JSON and generated source."""

from copy import deepcopy
from dataclasses import is_dataclass

from chaser.periodic.arrays import normalize_arrays
from chaser.periodic.kernels import normalize_task, reference_events, task_from_plan
from chaser.periodic.build import workload_source
from chaser.periodic.measurement import make_plan


def test_normalized_arrays_and_tasks_are_dataclasses(shaped_config):
    original = deepcopy(shaped_config)
    arrays = normalize_arrays(shaped_config['arrays'])
    assert all(is_dataclass(a) for a in arrays)
    registry = {a.array_id: a for a in arrays}
    task = normalize_task(shaped_config['tasks'][0], registry)
    assert is_dataclass(task) and is_dataclass(task.parameters)
    assert is_dataclass(task.arrays['A'])
    assert is_dataclass(task.metrics) and is_dataclass(task.footprint)
    assert (task.parameters.m, task.parameters.k, task.parameters.n) == (2, 3, 2)
    assert task.metrics.source_accesses == 60
    assert all(is_dataclass(event) for event in reference_events(task, registry))
    assert shaped_config == original


def test_typed_storage_roundtrip_omits_absent_shape(config):
    from chaser.periodic.workload import ArraySpec
    arrays = normalize_arrays(config['arrays'])
    for array in arrays:
        value = array.to_dict()
        assert 'shape' not in value and 'strides_elements' not in value
        assert ArraySpec.from_dict(value) == array


def test_typed_shape_serialization_does_not_alias_input(shaped_config):
    arrays = normalize_arrays(shaped_config['arrays'])
    value = arrays[0].to_dict()
    value['shape'][0] = 99
    assert arrays[0].shape == (2, 3)
    assert shaped_config['arrays'][0]['shape'] == [2, 3]


def test_typed_and_json_workloads_generate_identical_c(shaped_config):
    arrays = normalize_arrays(shaped_config['arrays'])
    task = normalize_task(shaped_config['tasks'][0], {a.array_id: a for a in arrays})
    plan = make_plan(shaped_config, 2)
    restored = task_from_plan(plan['tasks'][0])
    assert restored == task
    assert restored.to_dict() == task.to_dict()
    assert workload_source([task], arrays=arrays) == workload_source(plan['tasks'], arrays=plan['arrays'])
