"""Execute generated C against an independent dense matrix oracle."""

import ctypes
import subprocess
import pytest
from chaser.periodic.measurement import make_plan
from chaser.periodic.build import workload_source


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('overflow', [False, True])
@pytest.mark.parametrize('layout', ['flat', 'shape', 'strided'])
def test_nonuniform_padded_offset_gemm_preserves_inputs_and_padding(config, tmp_path, optimization, overflow, layout):
    for a, length, initial in zip(config['arrays'], (14, 17, 12), (1, 2, 99)):
        a.update(length=length, initial_value=initial)
    t = config['tasks'][0]
    t.update(m=2, n=2, k=3, lda=5, ldb=4, ldc=4, sweeps=3)
    for role, offset in zip(('A','B','C'), (2, 3, 1)):
        t['arrays'][role]['offset_elements'] = offset
    if layout != 'flat':
        for a, shape, ld in zip(config['arrays'], ([2, 3], [3, 2], [2, 2]), (5, 4, 4)):
            a.update(shape=shape, strides_elements=[ld, 2 if layout == 'strided' else 1])
        for key in ('m', 'n', 'k', 'lda', 'ldb', 'ldc'): t.pop(key)
    plan = make_plan(config, 2)
    (tmp_path / 'workload.h').write_text('#include <stdint.h>\n')
    (tmp_path / 'workload.c').write_text(workload_source(plan['tasks'], arrays=plan['arrays']))
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-'+optimization,
                    '-shared', '-fPIC', str(tmp_path / 'workload.c'), '-o', str(tmp_path / 'workload.so')], check=True)
    lib = ctypes.CDLL(str(tmp_path / 'workload.so'))
    lib.workload_prepare()
    a = (ctypes.c_uint32*14).in_dll(lib, 'data_a0')
    b = (ctypes.c_uint32*17).in_dll(lib, 'data_b0')
    c = (ctypes.c_uint32*12).in_dll(lib, 'data_c0')
    # Neither dense reference nor expected addresses use the generator's index helpers.
    aa = [[2, 3, 5], [7, 11, 13]]
    bb = [[17, 19], [23, 29], [31, 37]]
    if overflow:
        aa[0][1] = 0xffffffff
        bb[1][1] = 0xfffffffe
    ai, bi, ci = (([2, 4, 6, 7, 9, 11], [3, 5, 7, 9, 11, 13], [1, 3, 5, 7])
                  if layout == 'strided' else ([2, 3, 4, 7, 8, 9], [3, 4, 7, 8, 11, 12], [1, 2, 5, 6]))
    for index, value in zip(ai, sum(aa, [])): a[index] = value
    for index, value in zip(bi, sum(bb, [])): b[index] = value
    before_a, before_b = list(a), list(b)
    dense = [[sum(x*y for x, y in zip(row, col)) % 2**32 for col in zip(*bb)] for row in aa]
    expected = [99]*12
    for index, value in zip(ci, sum(dense, [])): expected[index] = value
    checksum = 2166136261
    for row in dense:
        for value in row:
            checksum = ((checksum ^ value)*16777619) % 2**32
    lib.task_job_gemm0.restype = ctypes.c_uint32
    for _ in range(3):
        assert lib.task_job_gemm0() == checksum
        assert list(c) == expected
        assert list(a) == before_a and list(b) == before_b
