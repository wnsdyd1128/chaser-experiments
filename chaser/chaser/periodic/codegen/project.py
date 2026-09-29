"""Render the RTEMS project files from validated plans."""

from pathlib import Path
import shutil

from chaser.periodic.codegen.workload import workload_source
from chaser.periodic.codegen.model import PolicyHeader
from tools.rtems_smoke import write_json

RTEMS = Path(__file__).resolve().parents[3] / 'rtems/periodic'


def topology_header(architecture: int) -> str:
    """Configure actual EDF SMP scheduler ownership, not partial affinity masks.
        - {0,0,0,0}: Global Queue (단일 스케줄러)
        - {0,1,2,3}: 4개 독립 클러스터 (CPU0 / CPU1 / CPU2 / CPU3)
        - {0,1,2,2}: 3개 클러스터 (CPU0 / CPU1 / CPU2,3)
        - {0,0,1,1}: 2개 클러스터 (CPU0,1 / CPU2,3)
    """

    assignments = ([0, 0, 0, 0], [0, 1, 1, 1], [0, 1, 2, 3])[architecture]
    count = max(assignments) + 1
    lines = [f'RTEMS_SCHEDULER_EDF_SMP(edf{i});' for i in range(count)]
    lines.append('#define CONFIGURE_SCHEDULER_TABLE_ENTRIES \\\n' + ', \\\n'.join(
        f"RTEMS_SCHEDULER_TABLE_EDF_SMP(edf{i}, rtems_build_name('E','D','F','{i}'))"
        for i in range(count)))
    lines.append('#define CONFIGURE_SCHEDULER_ASSIGNMENTS \\\n' + ', \\\n'.join(
        f'RTEMS_SCHEDULER_ASSIGN({i}, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY)'
        for i in assignments))
    return '\n'.join(lines) + '\n'


def config_header(plan: dict | PolicyHeader) -> str:
    """Render only scheduler/job data; measurement semantics live in the plan."""
    header = plan if isinstance(plan, PolicyHeader) else PolicyHeader.from_plan(plan)
    tasks = header.tasks
    lines = [f'#define TASK_COUNT {len(tasks)}',
             f'#define MAX_JOBS {max(t.job_count for t in tasks)}',
             f'#define ARCHITECTURE {header.architecture}',
             f'#define CHASER_CONTRACT_ID "{header.contract_id}"',
             f'#define CHASER_PLAN_HASH "{header.plan_hash}"']
    for key, macro in (('period_ticks', 'PERIODS'), ('job_count', 'JOB_COUNTS'), ('core', 'CORES')):
        lines.append('#define CHASER_' + macro + ' {' + ', '.join(str(getattr(t, key)) for t in tasks) + '}')
    return '\n'.join(lines) + '\n'


def write_project(output, plans):
    """Write source and policy headers to a new prepared directory."""
    source = output / 'source'
    source.mkdir(exist_ok=True)
    for name in ('init.c', 'probe.c', 'probe.h', 'workload.h'):
        shutil.copyfile(RTEMS / name, source / name)
    plan = plans[0]
    if plan['input_schema_version'] == 2:
        (source / 'workload.c').write_text(workload_source(
            plan['tasks'], arrays=plan['arrays']))
    else:
        with (source / 'workload.h').open('a') as header:
            header.write('\n#define CHASER_WORKLOAD_LIFECYCLE 1\n'
                         '/** @brief Reset original inputs before the bracket.\n'
                         ' * @param task Sole source-suite task index (zero). @return None. */\n'
                         'void workload_reset(unsigned task);\n'
                         '/** @brief Hash live-outs after the bracket at upstream print precision.\n'
                         ' * @param task Sole source-suite task index (zero). @return FNV-1a hash. */\n'
                         'uint32_t workload_checksum(unsigned task);\n')
    for name, plan in zip(('g', 'c', 'p'), plans):
        directory = output / name
        directory.mkdir()
        write_json(directory / 'plan.json', plan)
        (directory / 'config.h').write_text(config_header(plan))
        (directory / 'topology.h').write_text(topology_header(plan['architecture']))
    for name in ('layout.ld', 'wscript'):
        shutil.copyfile(RTEMS / name, output / name)
