import json
from pathlib import Path

import pytest

from chaser.allocator import CoreGroups, allocate


def records(**scalars):
    return {task: {'ca_caas_element': value, 'ca_csrd_l1': value}
            for task, value in scalars.items()}


def test_exported_representation_changes_group_without_changing_utilization():
    cases = json.loads(Path('exports/locality.json').read_text())['cases']
    workload = {'spread': 0.6, 'conflict': 0.3}
    cores = CoreGroups((0,), (1, 2, 3))
    caas = allocate(cases, workload, cores, kind='caas-ca', threshold=0.5)
    csrd = allocate(cases, workload, cores, kind='ca-csrd', threshold=0.5)
    assert caas.mapping == {'spread': 0, 'conflict': 0}
    assert csrd.mapping == {'spread': 1, 'conflict': 0}
    assert sum(caas.residual.values()) == pytest.approx(sum(csrd.residual.values()))
    assert caas.infeasible == csrd.infeasible == []


@pytest.mark.parametrize('scalar, cores', [
    (0.1, CoreGroups((2, 0), (1,))),
    (0.5, CoreGroups((1,), (2, 0))),
])
def test_descending_utilization_worst_fit_and_stable_ties(scalar, cores):
    cases = records(a=scalar, b=scalar, c=scalar, d=scalar)
    workload = {'d': 0.2, 'c': 0.3, 'b': 0.6, 'a': 0.6}
    result = allocate(cases, workload, cores, kind='ca-csrd', threshold=0.5)
    assert result.mapping == {'a': 0, 'b': 2, 'c': 0, 'd': 2}
    assert result.residual == pytest.approx({0: 0.1, 1: 1.0, 2: 0.2})
    reversed_cores = CoreGroups(tuple(reversed(cores.isolated)),
                               tuple(reversed(cores.non_isolated)))
    assert allocate(cases, dict(reversed(list(workload.items()))), reversed_cores,
                    kind='ca-csrd', threshold=0.5) == result


@pytest.mark.parametrize('scalar', [0.1, 0.9])
def test_full_group_does_not_spill_and_failure_does_not_stop_allocation(scalar):
    cases = records(large=scalar, first=scalar, fail=scalar, last=scalar)
    result = allocate(cases, {'last': 0.1, 'fail': 0.4, 'first': 0.7, 'large': 1.1},
                      CoreGroups((0,), (1,)), kind='ca-csrd', threshold=0.5)
    core = 0 if scalar < 0.5 else 1
    assert result.mapping == {'first': core, 'last': core}
    assert result.infeasible == ['large', 'fail']
    assert result.residual[core] == pytest.approx(0.2)
    assert result.residual[1 - core] == 1.0


def test_exact_capacity_and_empty_workload():
    cores = CoreGroups((0,), ())
    cases = records(a=0.1, b=0.1, c=0.1)
    result = allocate(cases, {'a': 0.6, 'b': 0.3, 'c': 0.1}, cores,
                      kind='ca-csrd', threshold=0.5)
    assert result.infeasible == []
    assert result.residual == {0: 0.0}
    empty = allocate({}, {}, cores, kind='ca-csrd', threshold=0.5)
    assert empty.mapping == {} and empty.infeasible == []
    assert empty.residual == {0: 1.0}


def test_empty_selected_group_is_infeasible():
    result = allocate(records(a=1.0), {'a': 0.1}, CoreGroups((0,), ()),
                      kind='ca-csrd', threshold=0.5)
    assert result.infeasible == ['a']
    assert result.mapping == {}


@pytest.mark.parametrize('kind, alpha, expected_core', [
    ('ca-line', None, 1), ('cls', 0.0, 1), ('cls', 1.0, 0),
])
def test_control_representation_and_precomputed_cls_alpha(kind, alpha, expected_core):
    cases = {'a': {'ca_global_line': 0.8, 'cls': {'0.0': 0.9, '1.0': 0.1}}}
    result = allocate(cases, {'a': 0.2}, CoreGroups((0,), (1,)),
                      kind=kind, alpha=alpha, threshold=0.5)
    assert result.mapping == {'a': expected_core}


@pytest.mark.parametrize('cores', [CoreGroups((0,), (0,)), CoreGroups((0, 0), (1,)),
                                   CoreGroups((), ()), CoreGroups((-1,), (0,))])
def test_invalid_core_groups_are_rejected(cores):
    with pytest.raises(ValueError):
        allocate({}, {}, cores, kind='ca-csrd', threshold=0.5)


@pytest.mark.parametrize('value', [None, -0.1, float('nan'), float('inf')])
def test_invalid_utilization_is_rejected(value):
    with pytest.raises(ValueError):
        allocate(records(a=0.5), {'a': value}, CoreGroups((0,), (1,)),
                 kind='ca-csrd', threshold=0.5)


@pytest.mark.parametrize('case', [{}, {'ca_csrd_l1': None}, {'ca_csrd_l1': 1.1}])
def test_missing_or_invalid_locality_is_rejected(case):
    with pytest.raises(ValueError):
        allocate({'a': case}, {'a': 0.1}, CoreGroups((0,), (1,)),
                 kind='ca-csrd', threshold=0.5)


def test_missing_task_and_nonfinite_threshold_are_rejected():
    with pytest.raises(ValueError):
        allocate({}, {'a': 0.1}, CoreGroups((0,), (1,)),
                 kind='ca-csrd', threshold=0.5)
    with pytest.raises(ValueError):
        allocate({}, {}, CoreGroups((0,), (1,)),
                 kind='ca-csrd', threshold=float('nan'))
