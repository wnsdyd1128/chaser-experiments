"""Specification of the C2 (0, 1, 2, 2) topology in the patched code copy.

Run with PYTHONPATH set to the patched copy. The unpatched copy is expected next
to it without the -c2 suffix; the plan comparison is skipped when it is absent.
"""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from chaser.periodic import measurement
from chaser.periodic.build import topology_header
from chaser.periodic.measurement import make_plan
import taskset

CODE = Path(measurement.__file__).resolve().parents[2]
BASELINE = CODE.with_name(CODE.name.removesuffix('-c2'))


def config():
    return taskset.configuration(20, 0.3, 0)


def test_c2_domains_follow_p_cores_zero_one_and_two_three():
    plan = make_plan(config(), 3)
    assert plan['topology_id'] == 'c2-edfsmp-1-1-2-v1'
    expected = {0: [0], 1: [1], 2: [2, 3], 3: [2, 3]}
    assert all(task['domain'] == expected[task['core']] for task in plan['tasks'])


def test_c2_header_assigns_processors_to_three_edf_schedulers():
    header = topology_header(3)
    assert header.count('RTEMS_SCHEDULER_EDF_SMP(') == 3
    assignments = [line for line in header.splitlines() if 'RTEMS_SCHEDULER_ASSIGN(' in line]
    assert [line.split('(')[1].split(',')[0] for line in assignments] == ['0', '1', '2', '2']


@pytest.mark.skipif(BASELINE == CODE or not BASELINE.exists(), reason='unpatched copy not found')
def test_existing_architectures_keep_the_unpatched_plans():
    script = ('import json, sys; from chaser.periodic.measurement import make_plan; '
              'c = json.load(sys.stdin); print(json.dumps([make_plan(c, a) for a in range(3)]))')
    baseline = subprocess.run([sys.executable, '-c', script], input=json.dumps(config()), text=True,
                              capture_output=True, check=True, cwd=BASELINE,
                              env={'PYTHONPATH': str(BASELINE)})
    assert [make_plan(config(), a) for a in range(3)] == json.loads(baseline.stdout)


def test_init_source_maps_c2_tasks_by_p_core():
    source = (CODE / 'rtems/periodic/init.c').read_text()
    assert 'if (ARCHITECTURE == 3) return cores[i] < 2 ? cores[i] : 2;' in source
