"""Validate periodic batches before independent U or architecture labeling."""

from collections import Counter
import json
from math import isfinite
from pathlib import Path
from statistics import median

from chaser.locality.features import build_features
from chaser.dataset.labeling import Measurement
from chaser.periodic.measurement import CONTRACT, digest, parse_log
from chaser.dataset.splits import taskset_signature, validate_taskset_split
from tools.rtems_smoke import check_inputs, file_hash


def verify_frozen_inputs(directory: Path) -> dict:
    """Verify frozen data and membership without regenerating candidate inputs."""
    manifest = json.loads((directory / 'manifest.json').read_text())
    check_inputs(directory, manifest)
    population = json.loads((directory / 'population.json').read_text())
    split = json.loads((directory / 'split.json').read_text())
    summary = json.loads((directory / 'summary.json').read_text())
    members = population['workloads']
    names = [row['workload_id'] for row in members]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate frozen workload identity')
    validate_taskset_split(split, {row['workload_id']: row['family_id'] for row in members},
                           {row['workload_id']: row['input_signature'] for row in members})
    for row in members:
        relative = 'source/configs/' + row['workload_id'] + '.json'
        if relative not in manifest['files']:
            raise ValueError('Frozen configuration is missing from manifest')
        config = json.loads((directory / relative).read_text())
        if (digest(config) != row['configuration_hash']
                or taskset_signature(config) != row['input_signature']
                or row['split_group'] != split['assignments'][row['workload_id']]):
            raise ValueError('Frozen configuration or membership differs')
    originals = {row['workload_id']: row for row in members}
    for alias in population.get('excluded_duplicates', ()):
        original = originals[alias['duplicate_of']]
        if (alias['input_signature'] != original['input_signature']
                or alias['split_group'] != original['split_group']):
            raise ValueError('Frozen duplicate alias differs from its original')
    if (summary['candidate_workloads'] != len(members)
            or summary['workload_counts'] != dict(Counter(split['assignments'].values()))
            or summary.get('split_hash', digest(split)) != digest(split)
            or summary.get('population_hash', digest(population)) != digest(population)):
        raise ValueError('Frozen population summary differs')
    return summary


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
        if (plan['contract_id'] != CONTRACT
                or row.get('contract_id') != CONTRACT
                or protocol.get('contract_id') != CONTRACT):
            raise ValueError('Measurement contract mismatch')
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
            if any(row[k] != parsed[k] for k in
                    ('mean_elapsed_ns', 'max_elapsed_ns', 'header', 'task_records')):
                raise ValueError('Stored public measurement differs from raw evidence')
            if any(row[k] != parsed[k] for k in
                    ('response_sum_ns', 'cohorts', 'warmup_jobs', 'measured_jobs',
                     'cohort_response_sum_ns', 'cohort_start_delay_sum_ns',
                     'run_release_span_ns', 'run_execution_span_ns')):
                raise ValueError('Stored measurement differs from raw evidence')
    return records


def characterize(plan: dict, batches: list[list[dict]]) -> dict:
    """Use measured jobs from each independent P run, then median run means."""
    if plan['architecture'] != 2 or len(batches) != len(plan['tasks']):
        raise ValueError('Independent characterization requires the P task list')
    utilization, evidence, elf_hashes = {}, {}, set()
    repeats = plan['u_repeats']
    for i, (task, rows) in enumerate(zip(plan['tasks'], batches)):
        if len(rows) != repeats or {r['run_id'] for r in rows} != {
                str(run) for run in range(repeats)}:
            raise ValueError('Distinct planned characterization runs are required')
        means = []
        for row in sorted(rows, key=lambda row: int(row['run_id'])):
            if (row['execution_status'] != 'ok' or row['plan_hash'] != plan['plan_hash']
                    or row['mode'] != i + 1 or row['trace'] or row['empty']):
                raise ValueError('Invalid independent characterization run')
            elf_hashes.add(row['elf_hash'])
            jobs = row['jobs']
            if Counter((job['task'], job['job']) for job in jobs) != Counter(
                    {(i, job): 1 for job in range(task['job_count'])}):
                raise ValueError('Incomplete characterization jobs')
            cpu_sum = 0
            for job in jobs:
                before, after = job['cpu_before_ns'], job['cpu_after_ns']
                if type(before) is not int or type(after) is not int or not 0 <= before <= after:
                    raise ValueError('Invalid CPU accounting')
                if job['job'] >= task['warmup_jobs']:
                    cpu_sum += after - before
            means.append(cpu_sum / (task['job_count'] - task['warmup_jobs']))
        median_mean = median(means)
        utilization[task['task_id']] = median_mean / (task['period_ticks'] * plan['tick_ns'])
        evidence[task['task_id']] = dict(run_mean_cpu_ns=means, median_mean_cpu_ns=median_mean,
            measured_jobs_per_run=task['job_count'] - task['warmup_jobs'],
            warmup_jobs_per_run=task['warmup_jobs'],
            log_hashes=[row['log_hash'] for row in sorted(rows, key=lambda row: int(row['run_id']))])
    if len(elf_hashes) != 1:
        raise ValueError('Characterization must use the same P executable')
    result = dict(utilization=utilization, utilization_source='measured-run-median-v3',
                  utilization_rule_id='isolated-measured-run-mean-median-v3',
                  u_repeats=repeats, tasks=evidence, elf_hash=next(iter(elf_hashes)),
                  plan_hash=plan['plan_hash'])
    result['characterization_id'] = digest(result)
    return result


def feature_record(member: dict, locality: dict, utilization: dict) -> dict:
    """Join independent U with locality; preserve undefined features and bounds."""
    values = utilization['utilization']
    if set(values) != set(locality['cases']):
        raise ValueError('Locality and independent U task IDs differ')
    reasons = []
    if any(value is None or not isfinite(value) or not 0 < value <= 1
           for value in values.values()):
        reasons.append('task_u_outside_0_1')
    tasks = [dict(locality['cases'][key], utilization=value) for key, value in values.items()]
    features, undefined = {}, {}
    for kind in ('caas-ca', 'ca-csrd', 'cls', 'clp'):
        try:
            features[kind] = build_features(tasks, kind, alpha=0.5 if kind == 'cls' else None)
        except ValueError as error:
            undefined[kind] = str(error)
    return dict(member, characterization_id=utilization['characterization_id'],
                utilization=values, features=features, undefined_features=undefined,
                cls_alpha=0.5, within_u_bounds=not reasons, exclusion_reasons=reasons,
                dataset_stage='characterized', feature_eligible=not reasons and not undefined,
                utilization_source=utilization['utilization_source'],
                utilization_rule_id=utilization['utilization_rule_id'])


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
