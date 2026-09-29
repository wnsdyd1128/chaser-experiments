"""Original-source plans preserve scheduling validation and dataset isolation."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from chaser.periodic.measurement import make_plan
from chaser.periodic.dataset import to_measurement
from chaser.periodic.polybench.sources import benchmarks

CONFIGS = Path(__file__).resolve().parents[3] / 'configs/periodic-polybench'


@pytest.mark.parametrize('benchmark', benchmarks(), ids=lambda b: b.name)
def test_published_medium_config_uses_original_type_and_dimensions(benchmark):
    config = json.loads((CONFIGS / (benchmark.name + '-medium.json')).read_text())
    for architecture in range(3):
        plan = make_plan(config, architecture)
        assert plan['polybench']['dimensions'] == benchmark.dimensions
        assert plan['polybench']['element_type'] == benchmark.element_type
        assert plan['tasks'][0]['job_count'] == 2
        assert plan['tasks'][0]['warmup_jobs'] == 1
        assert plan['input_schema_version'] == 3
        assert plan['dataset_eligible'] is False
        with pytest.raises(ValueError, match='qualification'):
            to_measurement(plan, {})


@pytest.mark.parametrize('change', [
    {'polybench': {'benchmark': 'atax', 'dataset': 'MINI'}},
    {'polybench': {'benchmark': '../atax', 'dataset': 'MEDIUM'}},
    {'polybench': {'benchmark': 'atax', 'dataset': 'MEDIUM', 'element_type': 'uint32_t'}},
    {'period_ticks': True}, {'core': 4}, {'workload_optimization': 'O2'},
    {'horizon_ticks': 5}, {'warmup_ticks': 0}, {'u_repeats': 0},
])
def test_invalid_source_or_schedule_is_rejected(change):
    config = json.loads((CONFIGS / 'atax-medium.json').read_text())
    config.update(deepcopy(change))
    with pytest.raises(ValueError):
        make_plan(config, 2)
