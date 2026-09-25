"""Plans and fail-closed job accounting for the periodic measurement contract."""

from collections import Counter
from hashlib import sha256
import json
import re

from chaser.periodic.patterns import job_access_count, validate_pattern

CONTRACT = 'chaser-periodic-measurement-v3'
TOPOLOGIES = ('g-edfsmp-4-v1', 'c-edfsmp-1-3-v1', 'p-edfsmp-4x1-v1')
TICK_NS = 1_000_000


def digest(value: object) -> str:
    """Hash canonical JSON, including topology in effective mapping identities."""
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def make_plan(configuration: dict, architecture: int) -> dict:
    """Validate literal workload bounds; explicit mappings are pilot policies.

    The common horizon determines every task's job count. No utilization or
    calibrated-policy claim is inferred from the supplied core assignment.
    """
    if type(architecture) is not int or architecture not in range(3):
        raise ValueError('Architecture must be G=0, C=1, or P=2')
    for key in ('workload_id', 'family_id', 'policy_id'):
        if not isinstance(configuration[key], str) or not configuration[key]:
            raise ValueError(f'Nonempty {key} is required')
    horizon = configuration['horizon_ticks']
    if type(horizon) is not int or not 1 <= horizon <= 1_000_000:
        raise ValueError('Positive bounded horizon is required')
    if not 1 <= len(configuration['tasks']) <= 16:
        raise ValueError('Between 1 and 16 tasks are supported')
    tasks = []
    for task in configuration['tasks']:
        task = dict(task)
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', task['task_id']):
            raise ValueError('Task IDs must be C identifiers')
        for key, low, high in (('period_ticks', 1, horizon), ('core', 0, 3),
                               ('distinct', 1, 131072), ('stride', 1, 4096),
                               ('sweeps', 1, 1_000_000)):
            if type(task[key]) is not int or not low <= task[key] <= high:
                raise ValueError(f'Invalid {key}')
        if horizon % task['period_ticks']:
            raise ValueError('Every period must divide the common horizon')
        validate_pattern(task)
        task['job_count'] = horizon // task['period_ticks']
        task['data_size'] = task['distinct'] * task['stride']
        task['expected_checksum'] = job_access_count(task) % (1 << 32)
        task['domain'] = (list(range(4)) if architecture == 0 else
                          ([0] if task['core'] == 0 else [1, 2, 3]) if architecture == 1
                          else [task['core']])
        tasks.append(task)
    if len({t['task_id'] for t in tasks}) != len(tasks):
        raise ValueError('Task IDs must be unique')
    if sum(t['job_count'] for t in tasks) > 4096:
        raise ValueError('At most 4096 job records per run')
    if sum((t['data_size'] + 4095) // 4096 * 4096 for t in tasks) > 16 * 1024**2:
        raise ValueError('Workload data exceeds the reserved 16 MiB')
    if configuration.get('measurement_contract_id', CONTRACT) != CONTRACT:
        raise ValueError('Unknown measurement contract')
    warmup = configuration.get('warmup_ticks')
    repeats = configuration.get('u_repeats')
    if (type(warmup) is not int or not 0 < warmup < horizon
            or any(warmup % task['period_ticks'] for task in tasks)):
        raise ValueError('warmup_ticks must divide every task period and precede measurement')
    if type(repeats) is not int or repeats < 1:
        raise ValueError('u_repeats must be positive')
    for task in tasks:
        task['warmup_jobs'] = warmup // task['period_ticks']
    plan = {k: configuration[k] for k in ('workload_id', 'family_id', 'policy_id')}
    plan.update(contract_id=CONTRACT, architecture=architecture,
                topology_id=TOPOLOGIES[architecture], tick_ns=TICK_NS,
                horizon_ticks=horizon, tasks=tasks,
                measurement_source='measured', execution_backend='laysim-gr740',
                checksum_boundary='after-completion-before-next-period',
                locality_scope='one-cold-task-local-job',
                core_mapping_hash=digest({t['task_id']: t['core'] for t in tasks}))
    plan.update(warmup_ticks=warmup, measurement_ticks=horizon - warmup,
                warmup_jobs=sum(t['warmup_jobs'] for t in tasks),
                measurement_jobs=sum(t['job_count'] - t['warmup_jobs'] for t in tasks),
                u_repeats=repeats, cohort_rule_id='same-nominal-release-v1',
                measurement_boundary_id='public-workload-bracket-v1')
    plan['mapping_hash'] = digest({'topology': plan['topology_id'],
                                  'domains': {t['task_id']: t['domain'] for t in tasks}})
    plan['plan_hash'] = digest(plan)
    return plan


def parse_log(text: str, plan: dict, *, mode: int = 0, trace: bool = False,
              empty: bool = False, salvage_partial: bool = False) -> dict:
    """Read only prefixed JSON records; reject missing markers and malformed data."""
    records = []
    truncated = False
    for line in text.splitlines():
        if not line.startswith('PERIODIC '):
            continue
        try:
            records.append(json.loads(line.removeprefix('PERIODIC ')))
        except json.JSONDecodeError:
            if not salvage_partial:
                raise
            truncated = True
            break
    if any(not isinstance(row, dict) for row in records):
        raise ValueError('Each periodic record must be a JSON object')
    result = aggregate(records, plan, mode=mode, trace=trace, empty=empty)
    if truncated:
        result['errors'] = sorted(set(result['errors']) | {'truncated_record'})
        result['execution_status'] = 'failed'
    return result


def aggregate(records: list[dict], plan: dict, *, mode: int = 0,
              trace: bool = False, empty: bool = False) -> dict:
    """Preserve failed raw jobs and partial sums; only complete runs are ok.

    Public status call bounds constrain the accounting epoch. Private snapshots
    are required only for diagnostic traces. Dispatch times never replace nominal
    releases. Mode i+1 runs task i alone on P/core 0.
    """
    errors = set()
    jobs = [r for r in records if r.get('kind') == 'job']
    result = dict(execution_status='failed', errors=[], jobs=jobs,
                  tet_ns=None, tat_ns=None, makespan_ns=None,
                  ready_ns=None, ready_unavailable_reason='period epoch is not the scheduler ready transition')
    headers = [r for r in records if r.get('kind') == 'run']
    ends = [r for r in records if r.get('kind') == 'end']
    if len(headers) != 1 or len(ends) != 1 or ends[0].get('complete') != 1:
        result['errors'] = ['completion_marker']
        return result
    header = headers[0]
    result['header'] = header
    try:
        if plan['contract_id'] != CONTRACT:
            errors.add('contract')
        if header['contract_id'] != plan['contract_id']:
            errors.add('provenance')
        if any(type(header[k]) is not int or header[k] < 0 for k in
               ('cpus', 'tick_ns', 'mode', 'trace', 'empty', 't0_ns', 't0_tick')):
            errors.add('header_schema')
        if (header['plan_hash'] != plan['plan_hash'] or header['cpus'] != 4
                or header['tick_ns'] != plan['tick_ns'] or header['mode'] != mode
                or header['trace'] != int(trace) or header['empty'] != int(empty)):
            errors.add('provenance')
        if mode and (plan['architecture'] != 2 or not 1 <= mode <= len(plan['tasks'])):
            errors.add('characterization_mode')
        active = {i: t for i, t in enumerate(plan['tasks']) if not mode or i == mode - 1}
        expected = {(i, j) for i, t in active.items() for j in range(t['job_count'])}
        counts = Counter((r['task'], r['job']) for r in jobs)
        if set(counts) != expected or any(n != 1 for n in counts.values()):
            errors.add('job_completeness')
        task_rows = [r for r in records if r.get('kind') == 'task']
        result['task_records'] = task_rows
        if Counter(r['task'] for r in task_rows) != Counter({i: 1 for i in active}):
            errors.add('task_completeness')
        for row in task_rows:
            domain = [0] if mode else active[row['task']]['domain']
            if (row['domain_mask'] != sum(1 << c for c in domain)
                    or row['affinity_mask'] != 15 or row['scheduler_ok'] != 1):
                errors.add('domain')
            if any(type(row[k]) is not int or row[k] != header['t0_tick']
                   for k in ('arm_before_tick', 'arm_after_tick')):
                errors.add('arm_phase')
        if header['t0_ns'] != header['t0_tick'] * plan['tick_ns']:
            errors.add('release_mismatch')
        tet, tat, completions, elapsed = 0, 0, [], []
        response_sum, starts, cohorts, warmup_count = 0, [], {}, 0
        for job in jobs:
            if job['task'] not in active:
                errors.add('unknown_task')
                continue
            task = active[job['task']]
            # bool, floats, and strings must not silently participate in accounting.
            if any(type(v) is not int for k, v in job.items() if k != 'kind'):
                errors.add('job_schema')
                continue
            period_ns = task['period_ticks'] * plan['tick_ns']
            release = header['t0_ns'] + job['job'] * period_ns
            deadline = header['t0_tick'] + (job['job'] + 1) * task['period_ticks']
            if job['release_ns'] != release:
                errors.add('release_mismatch')
            _check_public_status(job, release, plan['tick_ns'], errors)
            if trace:
                if job['timer_before'] != deadline or job['timer_after'] != deadline:
                    errors.add('release_mismatch')
                if job['edf_before'] != deadline or job['edf_after'] != deadline:
                    errors.add('edf_deadline')
                if job['epoch_before_ns'] != job['epoch_after_ns']:
                    errors.add('accounting_epoch')
                if abs(job['epoch_before_ns'] - release) >= plan['tick_ns']:
                    errors.add('release_mismatch')
                if job['epoch_before_ns'] > job['start_ns']:
                    errors.add('timestamps')
            elif any(k in job for k in ('epoch_before_ns', 'epoch_after_ns',
                                       'timer_before', 'timer_after', 'edf_before', 'edf_after')):
                errors.add('unexpected_probe')
            if not release <= job['start_ns'] <= job['completion_ns']:
                errors.add('timestamps')
            if job['completion_ns'] > release + period_ns:
                errors.add('deadline_miss')
            cpu = job['cpu_after_ns'] - job['cpu_before_ns']
            if cpu < 0 or job['cpu_before_ns'] < 0 or cpu > job['completion_ns'] - job['start_ns']:
                errors.add('cpu_accounting')
            if job['state_before'] != 1 or job['state_after'] != 1:
                errors.add('period_state')
            if job['postponed_before'] or job['postponed_after']:
                errors.add('postponed_job')
            if job['period_status']:
                errors.add('period_status')
            if job['checksum'] != (0 if empty else task['expected_checksum']):
                errors.add('checksum')
            domain = [0] if mode else task['domain']
            if job['start_core'] not in domain or job['end_core'] not in domain:
                errors.add('domain')
            if job['job'] < task['warmup_jobs']:
                warmup_count += 1
                continue
            tet += cpu
            response_sum += job['completion_ns'] - release
            completions.append(job['completion_ns'])
            starts.append(job['start_ns'])
            elapsed.append(job['completion_ns'] - job['start_ns'])
            cohorts.setdefault(release, []).append(job)
        switches = [r for r in records if r.get('kind') == 'switch']
        if trace:
            result['switches'] = switches
            threads = {r['thread']: r['task'] for r in task_rows}
            seen = set()
            last = {}
            for row in switches:
                if row['core'] not in range(4) or row['ns'] < last.get(row['core'], 0):
                    errors.add('trace_order')
                last[row['core']] = row['ns']
                if row['thread'] in threads:
                    i = threads[row['thread']]
                    seen.add(i)
                    if row['core'] not in ([0] if mode else active[i]['domain']):
                        errors.add('trace_domain')
            if seen != set(active):
                errors.add('trace_completeness')
        elif switches:
            errors.add('unexpected_trace')
        if any(r.get('kind') == 'error' for r in records):
            errors.add('target_error')
        if completions:
            cohort_rows = []
            for release, members in sorted(cohorts.items()):
                start = min(row['start_ns'] for row in members)
                finish = max(row['completion_ns'] for row in members)
                cohort_rows.append(dict(release_ns=release, job_count=len(members),
                                        start_ns=start, completion_ns=finish,
                                        span_ns=finish - start))
            tat = sum(row['span_ns'] for row in cohort_rows)
            result.update(response_sum_ns=response_sum, cohorts=cohort_rows,
                          warmup_jobs=warmup_count, measured_jobs=len(completions),
                          cohort_response_sum_ns=sum(row['completion_ns'] - row['release_ns']
                                                     for row in cohort_rows),
                          cohort_start_delay_sum_ns=sum(row['start_ns'] - row['release_ns']
                                                        for row in cohort_rows),
                          run_release_span_ns=max(completions) - header['t0_ns'],
                          run_execution_span_ns=max(completions) - min(starts))
            result.update(tet_ns=tet, tat_ns=tat,
                          makespan_ns=max(completions) - header['t0_ns'],
                          mean_response_ns=response_sum / len(completions))
            result.update(mean_elapsed_ns=sum(elapsed) / len(elapsed),
                          max_elapsed_ns=max(elapsed))
    except (KeyError, TypeError, ValueError) as error:
        errors.add('record_schema')
        result['schema_error'] = str(error)
    result.update(execution_status='failed' if errors else 'ok', errors=sorted(errors))
    return result


def _check_public_status(job: dict, release: int, tick: int, errors: set) -> None:
    # since_last_period is sampled inside get_status(), not at either uptime
    # endpoint. Keep an interval rather than inventing an exact kernel epoch.
    start, end = job['start_ns'], job['completion_ns']
    before_end, after_start = job['status_before_end_ns'], job['status_after_start_ns']
    if not start <= before_end <= after_start <= end:
        errors.add('timestamps')
    intervals = []
    for side, lo, hi in (('before', start, before_end), ('after', after_start, end)):
        wall = job[f'wall_{side}_ns']
        if wall < 0:
            errors.add('epoch_resolution')
        lower, upper = lo - wall, hi - wall
        intervals.append((lower, upper))
        if upper <= release - tick or lower >= release + tick:
            errors.add('release_mismatch')
        # One nanosecond accounts for separate timespec/uptime rounding.
        if f'epoch_{side}_ns' in job and not lower - 1 <= job[f'epoch_{side}_ns'] <= upper + 1:
            errors.add('accounting_epoch')
    lower, upper = max(i[0] for i in intervals), min(i[1] for i in intervals)
    if lower > upper + 1:
        errors.add('accounting_epoch')
    if upper - lower >= tick:
        errors.add('epoch_resolution')
    if lower <= release - tick or upper >= release + tick:
        errors.add('release_mismatch')
