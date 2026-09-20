"""Validate periodic batches before independent U or architecture labeling."""

from collections import Counter
import json
from pathlib import Path

from chaser.labeling import Measurement
from chaser.periodic import digest, parse_log
from tools.rtems_smoke import check_inputs, file_hash


def load_batch(prepared: Path, directory: Path) -> list[dict]:
    """Recheck raw logs and immutable inputs rather than trusting stored totals."""
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    protocol = json.loads((directory / 'protocol.json').read_text())
    if (file_hash(prepared / 'manifest.json') != protocol['manifest_hash']
            or file_hash(directory / 'boot.batch') != protocol['boot_hash']):
        raise ValueError('Batch provenance mismatch')
    for name, expected in protocol['implementation_hashes'].items():
        if file_hash(directory / name) != expected:
            raise ValueError('Measurement implementation snapshot changed')
    records = [json.loads(line) for line in (directory / 'measurements.jsonl').read_text().splitlines()]
    if (len(records) != protocol['runs']
            or {r['run_id'] for r in records} != {str(i) for i in range(protocol['runs'])}):
        raise ValueError('Missing or duplicate planned runs')
    for row in records:
        plan = json.loads((prepared / ('g', 'c', 'p')[row['architecture']] / 'plan.json').read_text())
        elf = prepared / 'build' / (('g', 'c', 'p')[row['architecture']] + '.exe')
        if (row['elf_hash'] != file_hash(elf) or row['elf_hash'] != protocol['elf_hash']
                or row['plan_hash'] != plan['plan_hash'] or row['plan_hash'] != protocol['plan_hash']
                or any(row[k] != protocol[k] for k in ('mode', 'trace', 'empty'))):
            raise ValueError('Run identity mismatch')
        path = directory / row['log']
        if file_hash(path) != row['log_hash']:
            raise ValueError('Raw measurement log changed')
        try:
            parsed = parse_log(path.read_text(errors='replace'), plan, mode=row['mode'],
                               trace=row['trace'], empty=row['empty'])
        except ValueError:
            if row['execution_status'] == 'ok':
                raise ValueError('Malformed raw evidence was marked successful')
            continue
        if row['execution_status'] == 'ok':
            if row['returncode'] or parsed['execution_status'] != 'ok':
                raise ValueError('Failed raw evidence was marked successful')
            if any(row[k] != parsed[k] for k in ('tet_ns', 'tat_ns', 'makespan_ns', 'jobs')):
                raise ValueError('Stored measurement differs from raw evidence')
    return records


def characterize(plan: dict, batches: list[list[dict]]) -> dict:
    """Use every job in ten fresh independent P runs per task; never trim U."""
    if plan['architecture'] != 2 or len(batches) != len(plan['tasks']):
        raise ValueError('Independent characterization requires the P task list')
    utilization, evidence, elf_hashes = {}, {}, set()
    for i, (task, rows) in enumerate(zip(plan['tasks'], batches)):
        if len(rows) != 10 or len({r['run_id'] for r in rows}) != 10:
            raise ValueError('Ten distinct planned characterization runs are required')
        total = 0
        for row in rows:
            if (row['execution_status'] != 'ok' or row['plan_hash'] != plan['plan_hash']
                    or row['mode'] != i + 1 or row['trace'] or row['empty']):
                raise ValueError('Invalid independent characterization run')
            elf_hashes.add(row['elf_hash'])
            if Counter((j['task'], j['job']) for j in row['jobs']) != Counter(
                    {(i, j): 1 for j in range(task['job_count'])}):
                raise ValueError('Incomplete characterization jobs')
            for job in row['jobs']:
                before, after = job['cpu_before_ns'], job['cpu_after_ns']
                if type(before) is not int or type(after) is not int or not 0 <= before <= after:
                    raise ValueError('Invalid CPU accounting')
                total += after - before
        count = 10 * task['job_count']
        mean = total / count
        utilization[task['task_id']] = mean / (task['period_ticks'] * plan['tick_ns'])
        evidence[task['task_id']] = dict(cpu_sum_ns=total, job_count=count, mean_cpu_ns=mean,
            log_hashes=[r['log_hash'] for r in rows])
    if len(elf_hashes) != 1:
        raise ValueError('Characterization must use the same P executable')
    result = dict(utilization=utilization, utilization_source='measured-mean',
                  tasks=evidence, elf_hash=next(iter(elf_hashes)), plan_hash=plan['plan_hash'])
    result['characterization_id'] = digest(result)
    return result


def to_measurement(plan: dict, row: dict) -> Measurement:
    """Convert only normal timing runs; keep failed attempts in the population."""
    if row['mode'] or row['trace'] or row['empty'] or row['plan_hash'] != plan['plan_hash']:
        raise ValueError('Only matching normal timing runs can enter the dataset')
    ok = row['execution_status'] == 'ok'
    return Measurement(workload_id=plan['workload_id'], architecture=plan['architecture'],
        topology_id=plan['topology_id'], allocator_id=plan['policy_id'],
        mapping_hash=plan['mapping_hash'], run_id=row['run_id'],
        tet=row['tet_ns'] if ok else None, tat=row['tat_ns'] if ok else None,
        execution_status=row['execution_status'], measurement_source='measured', time_unit='ns')
