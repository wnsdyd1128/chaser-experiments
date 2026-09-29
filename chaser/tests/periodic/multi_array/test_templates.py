"""Kernel templates receive data rather than injected C expressions."""

import pytest

from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import NoParameters, TaskSpec


@pytest.mark.parametrize('value', ['data_x[0]', 'i * 4', 'x; return 0;', '"quoted"', True, 1.5])
def test_template_rejects_c_fragments_and_noninteger_parameters(tmp_path, value):
    path = tmp_path / 'job.c.in'
    path.write_text('int x = ${value};\n')
    with pytest.raises(ValueError):
        render_template(path, TaskSpec('test', 'test', {}, 1, 0, 1, NoParameters()), {}, value=value)


def test_template_accepts_only_used_identifiers_and_integer_constants(tmp_path):
    path = tmp_path / 'job.c.in'
    path.write_text('uint32_t ${name} = ${value};\n')
    assert render_template(path, TaskSpec('test', 'test', {}, 1, 0, 1, NoParameters()), {},
                           name='sum_0', value=42, unused='word-hash-v1') == ['uint32_t sum_0 = 42;']
