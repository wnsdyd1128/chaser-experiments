"""Execute generated C against an independent dense matrix oracle."""

import ctypes
import subprocess
import pytest
from chaser.periodic.measurement import make_plan
from chaser.periodic.build import workload_source


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('overflow', [False, True])
def test_nonuniform_padded_offset_gemm_preserves_inputs_and_padding(config, tmp_path, optimization, overflow):
    for a, length, initial in zip(config['arrays'], (14, 17, 12), (1, 2, 99)):
        a.update(length=length, initial_value=initial)
    t = config['tasks'][0]
    t.update(m=2, n=2, k=3, lda=5, ldb=4, ldc=4, sweeps=3)
    for role, offset in zip(('A','B','C'), (2, 3, 1)):
        t['arrays'][role]['offset_elements'] = offset
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
    a[2:5], a[7:10] = aa[0], aa[1]
    b[3:5], b[7:9], b[11:13] = bb[0], bb[1], bb[2]
    before_a, before_b = list(a), list(b)
    dense = [[sum(x*y for x, y in zip(row, col)) % 2**32 for col in zip(*bb)] for row in aa]
    expected = [99]*12
    expected[1:3], expected[5:7] = dense[0], dense[1]
    checksum = 2166136261
    for row in dense:
        for value in row:
            checksum = ((checksum ^ value)*16777619) % 2**32
    lib.task_job_gemm0.restype = ctypes.c_uint32
    for _ in range(3):
        assert lib.task_job_gemm0() == checksum
        assert list(c) == expected
        assert list(a) == before_a and list(b) == before_b
