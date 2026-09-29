"""The source-suite contract keeps original types outside uint32 array schema."""

from dataclasses import dataclass

from chaser.periodic.arrays import fields, integer
from chaser.periodic.polybench.sources import REVISION, benchmark_named

CONTRACT = 'periodic-polybench-c-4.2.1-v1'


@dataclass(frozen=True)
class SourceSelection:
    """One original MEDIUM kernel per snapshot, with exclusive global storage."""

    benchmark: str
    period_ticks: int
    core: int

    @classmethod
    def from_config(cls, configuration: dict) -> 'SourceSelection':
        """Reject arbitrary source injection, type overrides and unknown fields."""
        fields(configuration, ('schema_version', 'workload_id', 'family_id', 'policy_id',
            'measurement_contract_id', 'horizon_ticks', 'warmup_ticks', 'u_repeats',
            'workload_optimization', 'polybench', 'period_ticks', 'core'),
            ('schema_version', 'workload_id', 'family_id', 'policy_id', 'horizon_ticks',
             'polybench', 'period_ticks', 'core'))
        if configuration['schema_version'] != 3:
            raise ValueError('Original PolyBench inputs require schema_version: 3')
        source = configuration['polybench']
        fields(source, ('benchmark', 'dataset'), ('benchmark', 'dataset'))
        benchmark_named(source['benchmark'])
        if source['dataset'] != 'MEDIUM':
            raise ValueError('Original PolyBench examples require MEDIUM')
        if configuration.get('workload_optimization', 'O0') != 'O0':
            raise ValueError('Original PolyBench validation currently requires O0')
        return cls(source['benchmark'], integer(configuration['period_ticks'], 'period_ticks'),
                   integer(configuration['core'], 'core', 0, 3))


def make_plan(configuration: dict, architecture: int) -> dict:
    """Build a schedule; preparation fills the independently computed checksum."""
    from chaser.periodic.measurement import digest, schedule_plan
    selection = SourceSelection.from_config(configuration)
    benchmark = benchmark_named(selection.benchmark)
    plan = schedule_plan(configuration, architecture, [dict(task_id='polybench',
        pattern=benchmark.name, core=selection.core, period_ticks=selection.period_ticks,
        sweeps=1, expected_checksum=None)])
    plan.update(input_schema_version=3, kernel_contract_id=CONTRACT,
                workload_optimization='O0', polybench=dict(benchmark=benchmark.name,
                    dataset='MEDIUM', dimensions=benchmark.dimensions,
                    element_type=benchmark.element_type, upstream_revision=REVISION),
                reset_boundary='before-workload-bracket-every-job',
                checksum_method='fnv1a32-upstream-formatted-live-outs',
                dataset_eligible=False)
    plan['plan_hash'] = digest(plan)
    return plan
