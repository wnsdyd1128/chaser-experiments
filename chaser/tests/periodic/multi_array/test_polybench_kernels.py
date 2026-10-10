"""uint32 PolyBench/C adaptations (BICG, MVT, GESUMMV, JACOBI-1D, JACOBI-2D, 2MM, SYRK, TRMM, DOITGEN): counts,
native oracles, real streams."""

import ctypes
import json
import random
import subprocess

import pytest

from chaser.periodic.build import prepare, workload_source
from chaser.periodic.kernels import reference_events, task_from_plan
from chaser.periodic.kernels.polybench_views import fnv
from chaser.periodic.measurement import make_plan
from chaser.periodic.workload import ArraySpec, MemoryFootprint

M32 = 2**32
# pattern -> (role -> shape, live-out roles in hash order)
SHAPES = {
    'polybench-bicg-u32': (dict(A=[3, 4], s=[4], q=[3], p=[4], r=[3]), ('s', 'q')),
    'polybench-mvt-u32': (dict(A=[4, 4], x1=[4], x2=[4], y1=[4], y2=[4]), ('x1', 'x2')),
    'polybench-gesummv-u32': (dict(A=[3, 3], B=[3, 3], tmp=[3], x=[3], y=[3]), ('y',)),
    'polybench-jacobi1d-u32': (dict(A=[6], B=[6]), ('A',)),
    'polybench-jacobi2d-u32': (dict(A=[5, 5], B=[5, 5]), ('A',)),
    'polybench-2mm-u32': (dict(A=[3, 3], B=[3, 3], tmp=[3, 3], C=[3, 3], D=[3, 3]), ('D',)),
    'polybench-syrk-u32': (dict(A=[4, 4], C=[4, 4]), ('C',)),
    'polybench-trmm-u32': (dict(A=[4, 4], B=[4, 4]), ('B',)),
    'polybench-doitgen-u32': (dict(A=[9, 3], C4=[3, 3], sum=[3]), ('A',)),
}
SCRATCH = ('tmp', 'sum')  # written but not hashed
# In-place outputs each job first resets to the array's initial value, so every job computes the same result.
RESET = {'polybench-2mm-u32': 'D', 'polybench-syrk-u32': 'C', 'polybench-trmm-u32': 'B', 'polybench-doitgen-u32': 'A'}


def config(patterns=tuple(SHAPES), sweeps=2, initial=None, optimization='O0'):
    arrays, tasks = [], []
    for k, pattern in enumerate(patterns):
        shapes, _ = SHAPES[pattern]
        same = pattern.startswith('polybench-jacobi')
        for r, (role, shape) in enumerate(shapes.items()):
            value = initial if initial is not None else (3 if same else r + 2)
            arrays.append(dict(array_id=f'{role.lower()}{k}', element_type='uint32_t', shape=shape,
                               alignment_bytes=32, initial_value=value))
        tasks.append(dict(task_id=f'k{k}', pattern=pattern, sweeps=sweeps, core=k % 4, period_ticks=2000,
                          arrays={role: dict(array_id=f'{role.lower()}{k}') for role in shapes}))
    return dict(schema_version=2, workload_id='polybench-kernels-test', family_id='polybench-kernels-test',
                policy_id='explicit-core-map-v1', measurement_contract_id='chaser-periodic-measurement-v3',
                horizon_ticks=4000, warmup_ticks=2000, u_repeats=1, workload_optimization=optimization,
                arrays=arrays, tasks=tasks)


def compile_lib(plan, tmp_path, optimization='O0'):
    (tmp_path / 'workload.h').write_text('#include <stdint.h>\n')
    (tmp_path / 'workload.c').write_text(workload_source(plan['tasks'], arrays=plan['arrays']))
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-' + optimization, '-shared', '-fPIC',
                    str(tmp_path / 'workload.c'), '-o', str(tmp_path / 'workload.so')], check=True)
    lib = ctypes.CDLL(str(tmp_path / 'workload.so'))
    lib.workload_prepare()
    return lib


def view(lib, plan, task, role):
    binding = task['arrays'][role]
    spec = next(a for a in plan['arrays'] if a['array_id'] == binding['array_id'])
    return (ctypes.c_uint32 * spec['length']).in_dll(lib, 'data_' + spec['array_id'])


def reference(pattern, v, steps):
    """Independent Python oracle: live-out values per role after steps time steps (sweeps)."""
    if pattern == 'polybench-2mm-u32':
        A, B, C, D, n = v['A'], v['B'], v['C'], [list(r) for r in v['D']], len(v['A'])
        tmp = [[sum(3 * A[i][k] * B[k][j] for k in range(n)) % M32 for j in range(n)] for i in range(n)]
        for _ in range(steps):
            D = [[(2 * D[i][j] + sum(tmp[i][k] * C[k][j] for k in range(n))) % M32 for j in range(n)] for i in range(n)]
        return dict(D=D)
    if pattern == 'polybench-syrk-u32':
        A, C, n = v['A'], [list(r) for r in v['C']], len(v['A'])
        for _ in range(steps):
            C = [[(2 * C[i][j] + sum(3 * A[i][k] * A[j][k] for k in range(n))) % M32 if j <= i else C[i][j]
                  for j in range(n)] for i in range(n)]
        return dict(C=C)
    if pattern == 'polybench-trmm-u32':
        A, B, n = v['A'], [list(r) for r in v['B']], len(v['A'])
        for _ in range(steps):
            old = [list(r) for r in B]
            B = [[3 * (old[i][j] + sum(A[k][i] * old[k][j] for k in range(i + 1, n))) % M32 for j in range(n)]
                 for i in range(n)]
        return dict(B=B)
    if pattern == 'polybench-doitgen-u32':
        A, C4, n = [list(r) for r in v['A']], v['C4'], len(v['C4'])
        for _ in range(steps):
            A = [[sum(row[s] * C4[s][p] for s in range(n)) % M32 for p in range(n)] for row in A]
        return dict(A=A)
    if pattern == 'polybench-bicg-u32':
        A, p, r = v['A'], v['p'], v['r']
        return dict(s=[sum(r[i] * A[i][j] for i in range(len(A))) % M32 for j in range(len(A[0]))],
                    q=[sum(A[i][j] * p[j] for j in range(len(A[0]))) % M32 for i in range(len(A))])
    if pattern == 'polybench-mvt-u32':
        A, n = v['A'], len(v['A'])
        return dict(x1=[sum(A[i][j] * v['y1'][j] for j in range(n)) % M32 for i in range(n)],
                    x2=[sum(A[j][i] * v['y2'][j] for j in range(n)) % M32 for i in range(n)])
    if pattern == 'polybench-gesummv-u32':
        n = len(v['A'])
        tmp = [sum(v['A'][i][j] * v['x'][j] for j in range(n)) % M32 for i in range(n)]
        yy = [sum(v['B'][i][j] * v['x'][j] for j in range(n)) % M32 for i in range(n)]
        return dict(y=[(3 * t + 2 * u) % M32 for t, u in zip(tmp, yy)])
    A, B = [list(row) if isinstance(row, list) else row for row in v['A']], [list(row) if isinstance(row, list) else row for row in v['B']]
    if pattern == 'polybench-jacobi1d-u32':
        n = len(A)
        for _ in range(steps):
            for src, dst in ((A, B), (B, A)):
                for i in range(1, n - 1):
                    dst[i] = ((src[i - 1] + src[i] + src[i + 1]) % M32) // 3
        return dict(A=A)
    n = len(A)
    for _ in range(steps):
        for src, dst in ((A, B), (B, A)):
            for i in range(1, n - 1):
                for j in range(1, n - 1):
                    dst[i][j] = ((src[i][j] + src[i][j - 1] + src[i][j + 1] + src[i + 1][j] + src[i - 1][j]) % M32) // 5
    return dict(A=A)


@pytest.mark.parametrize('pattern', list(SHAPES))
def test_reference_stream_matches_declared_counts(pattern):
    plan = make_plan(config((pattern,)), 2)
    task = plan['tasks'][0]
    registry = {a.array_id: a for a in map(ArraySpec.from_dict, plan['arrays'])}
    events = list(reference_events(task_from_plan(task), registry))
    assert sum(e.operation == 'load' for e in events) == task['source_loads']
    assert sum(e.operation == 'store' for e in events) == task['source_stores']


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('pattern', list(SHAPES))
def test_constant_initialization_gives_the_closed_form_checksum(pattern, optimization, tmp_path):
    plan = make_plan(config((pattern,), optimization=optimization), 2)
    lib = compile_lib(plan, tmp_path, optimization)
    getattr(lib, 'task_job_k0').restype = ctypes.c_uint32
    assert getattr(lib, 'task_job_k0')() == plan['tasks'][0]['expected_checksum']


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('pattern', list(SHAPES))
def test_every_job_returns_the_closed_form_checksum(pattern, optimization, tmp_path):
    plan = make_plan(config((pattern,), optimization=optimization), 2)
    lib = compile_lib(plan, tmp_path, optimization)
    job = getattr(lib, 'task_job_k0')
    job.restype = ctypes.c_uint32
    assert [job() for _ in range(3)] == [plan['tasks'][0]['expected_checksum']] * 3


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('pattern', list(SHAPES))
def test_nonuniform_inputs_match_the_independent_oracle(pattern, optimization, tmp_path):
    plan = make_plan(config((pattern,), sweeps=2), 2)
    task = plan['tasks'][0]
    lib = compile_lib(plan, tmp_path, optimization)
    rng = random.Random(pattern)
    shapes, outs = SHAPES[pattern]
    stateful = pattern.startswith('polybench-jacobi')  # integer division: small values, B changes but is not hashed
    values = {}
    for role, shape in shapes.items():
        data = view(lib, plan, task, role)
        count = shape[0] * (shape[1] if len(shape) == 2 else 1)
        flat = [rng.randrange(1000) if stateful else rng.choice((0, 1, 7, 2**31 + 5, M32 - 1, rng.randrange(M32)))
                for _ in range(count)]
        if RESET.get(pattern) == role:  # the job overwrites it with the initial value first
            flat = [next(a for a in plan['arrays'] if a['array_id'] == task['arrays'][role]['array_id'])['initial_value']] * count
        for i, x in enumerate(flat):
            data[i] = x
        values[role] = flat if len(shape) == 1 else [flat[i * shape[1]:(i + 1) * shape[1]] for i in range(shape[0])]
    job = getattr(lib, 'task_job_k0')
    job.restype = ctypes.c_uint32
    for call in (1, 2):
        result = job()
        copy = {r: [list(x) if isinstance(x, list) else x for x in v] for r, v in values.items()}
        expected = reference(pattern, copy, task['sweeps'] * (1 if pattern in RESET else call))
        hashed = []
        for role in outs:
            want = expected[role] if len(shapes[role]) == 1 else sum(expected[role], [])
            assert list(view(lib, plan, task, role))[:len(want)] == want, (role, call)
            hashed += want
        assert result == fnv(hashed), call
        if not stateful:
            for role in set(shapes) - set(outs) - set(SCRATCH):
                flat = values[role] if len(shapes[role]) == 1 else sum(values[role], [])
                assert list(view(lib, plan, task, role))[:len(flat)] == flat, role


@pytest.mark.parametrize('pattern', list(SHAPES))
def test_footprint_formula_matches_the_reference_stream(pattern):
    plan = make_plan(config((pattern,), sweeps=1), 2)
    task = plan['tasks'][0]
    registry = {a.array_id: a for a in map(ArraySpec.from_dict, plan['arrays'])}
    words, lines = set(), set()
    for e in reference_events(task_from_plan(task), registry):
        words.add((e.array_id, e.offset_bytes))
        lines.add((e.array_id, e.offset_bytes // 32))
    assert task['unique_accessed_bytes'] == 4 * len(words)
    assert task['unique_cache_lines'] == len(lines)


@pytest.mark.parametrize('change', ['shape', 'dtype', 'jacobi_initial'])
@pytest.mark.parametrize('pattern', list(SHAPES))
def test_invalid_inputs_are_rejected(pattern, change):
    c = config((pattern,))
    if change == 'shape':
        c['arrays'][1]['shape'] = [c['arrays'][1]['shape'][0] + 1] + c['arrays'][1]['shape'][1:]
    if change == 'dtype':
        c['arrays'][0]['element_type'] = 'uint16_t'
    if change == 'jacobi_initial':
        if not pattern.startswith('polybench-jacobi'):
            pytest.skip('only the stencils require one initial value')
        c['arrays'][1]['initial_value'] = 4
    with pytest.raises(ValueError):
        make_plan(c, 2)


def test_all_kernels_in_one_real_elf_pass_the_yarda_stream_check(tmp_path):
    from chaser.periodic.analysis import analyze
    prepared = tmp_path / 'prepared'
    prepare(config(optimization='O2', sweeps=1), prepared)
    result = analyze(prepared)
    plan = json.loads((prepared / 'p/plan.json').read_text())
    for task in plan['tasks']:
        assert result['cases'][task['task_id']]['modeled_accesses'] == task['source_accesses']
