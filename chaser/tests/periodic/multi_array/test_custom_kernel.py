"""A user-defined C job uses the public kernel contract without GEMM branches."""

from copy import deepcopy
from dataclasses import dataclass, replace
from types import SimpleNamespace
import ctypes
import subprocess

import pytest

from chaser.periodic import kernels
from chaser.periodic.workload import KernelMetrics, ReferenceEvent
from chaser.periodic.arrays import integer
from chaser.periodic.build import workload_source
from chaser.periodic.measurement import make_plan


@dataclass
class CopyParameters:
    count: int
    increment: int = 0


@pytest.fixture
def custom_kernel(monkeypatch, tmp_path):
    template = tmp_path / 'copy.c.in'
    template.write_text('''/** @brief Copy one logical pair per sweep. @return Sum of stored values. */
ANALYZE uint32_t task_job_${task_id}(void) {
    uint32_t sum = 0;
    for (int s = 0; s < ${sweeps}; ++s) {
        for (int i = 0; i < ${count}; ++i) {
            uint32_t value = ${input}[i];
            value += ${increment}U;
            ${output}[i] = value;
            sum += value;
        }
    }
    return sum;
}
''')

    def validate(task, registry):
        integer(task.parameters.count, 'count')
        integer(task.parameters.increment, 'increment', 0)
        for binding in task.arrays.values():
            a = registry[binding.array_id]
            if a.element_type != 'uint32_t' or a.length < task.parameters.count or binding.offset_elements:
                raise ValueError('copy requires two uint32 elements at offset zero')
        count = task.parameters.count*task.sweeps
        value = registry[task.arrays['input'].array_id].initial_value + task.parameters.increment
        return KernelMetrics(source_loads=count, source_stores=count,
                    expected_checksum=count*value % 2**32,
                    checksum_kind='copy-sum-v1', loop_iterations=(1+task.parameters.count)*task.sweeps)

    def events(task, registry):
        for _ in range(task.sweeps):
            for i in range(task.parameters.count):
                for role, operation in (('input', 'load'), ('output', 'store')):
                    yield ReferenceEvent(array_id=task.arrays[role].array_id, offset_bytes=i*4,
                               access_size_bytes=4, operation=operation)

    def source(task, registry):
        return kernels.render_template(template, task, registry)

    module = SimpleNamespace(validate=validate, events=events, source=source)
    monkeypatch.setitem(kernels.KERNELS, 'user-copy', kernels.Kernel(
        module=module, roles=('input', 'output'), parameter_type=CopyParameters, write_roles=('output',)))
    return module


def copy_config(config):
    config['arrays'] = [dict(array_id='x', element_type='uint32_t', shape=[2], initial_value=7),
                        dict(array_id='y', element_type='uint32_t', shape=[2], initial_value=99)]
    config['tasks'] = [dict(task_id='copy', pattern='user-copy', arrays={
        'input': {'array_id': 'x'}, 'output': {'array_id': 'y'}},
        count=2, sweeps=3, core=0, period_ticks=10)]
    return config


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('increment', [0, 3])
def test_registered_c_kernel_executes_with_reference_counts_and_footprint(custom_kernel, config, tmp_path, optimization, increment):
    config = copy_config(config)
    if increment:
        config['tasks'][0]['increment'] = increment
    plan = make_plan(config, 2)
    task = plan['tasks'][0]
    assert (task['source_loads'], task['source_stores']) == (6, 6)
    assert (task['unique_accessed_bytes'], task['unique_cache_lines']) == (16, 2)
    (tmp_path / 'workload.h').write_text('#include <stdint.h>\n')
    (tmp_path / 'workload.c').write_text(workload_source(plan['tasks'], arrays=plan['arrays']))
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-'+optimization,
                    '-shared', '-fPIC', str(tmp_path / 'workload.c'), '-o', str(tmp_path / 'workload.so')], check=True)
    lib = ctypes.CDLL(str(tmp_path / 'workload.so'))
    lib.workload_prepare()
    lib.task_job_copy.restype = ctypes.c_uint32
    assert task['increment'] == increment
    assert lib.task_job_copy() == task['expected_checksum'] == 6*(7+increment)
    assert list((ctypes.c_uint32*2).in_dll(lib, 'data_y')) == [7+increment]*2


def test_parameter_dataclass_controls_required_and_unknown_json_fields(custom_kernel, config):
    config = copy_config(config)
    del config['tasks'][0]['count']
    with pytest.raises(ValueError, match='required'): make_plan(config, 2)
    config['tasks'][0].update(count=2, typo=3)
    with pytest.raises(ValueError, match='fields'): make_plan(config, 2)


def test_registered_kernel_write_roles_enforce_exclusive_ownership(custom_kernel, config):
    config = copy_config(config)
    other = deepcopy(config['tasks'][0])
    other['task_id'] = 'other'
    config['tasks'].append(other)
    with pytest.raises(ValueError, match='exclusive'): make_plan(config, 2)


@pytest.mark.parametrize('change', ['counts', 'out_of_bounds', 'undeclared_write'])
def test_custom_reference_contract_is_validated(custom_kernel, config, change):
    original = custom_kernel.events
    def broken(task, registry):
        for e in original(task, registry):
            if change == 'out_of_bounds': e = replace(e, offset_bytes=8)
            if change == 'undeclared_write': e = replace(e, array_id=task.arrays['input'].array_id)
            yield e
            if change == 'counts': break
    custom_kernel.events = broken
    with pytest.raises(ValueError): make_plan(copy_config(config), 2)


def test_new_c_kernel_without_helper_has_real_ape_stream(custom_kernel, config, tmp_path):
    from chaser.periodic.build import prepare
    from chaser.periodic.analysis import analyze
    prepared = tmp_path / 'prepared'
    prepare(copy_config(config), prepared)
    result = analyze(prepared)
    assert result['cases']['copy']['modeled_accesses'] == 12
    assert result['dataset_eligible'] is False


def test_actual_c_store_must_match_declared_reference(custom_kernel, config, tmp_path):
    from chaser.periodic.build import prepare
    from chaser.periodic.analysis import analyze
    template = tmp_path / 'copy.c.in'
    template.write_text(template.read_text().replace('${output}[i] = value;', '${input}[i] = value;'))
    prepared = tmp_path / 'wrong-store'
    prepare(copy_config(config), prepared)
    with pytest.raises(ValueError, match='order/address/kind'): analyze(prepared)
