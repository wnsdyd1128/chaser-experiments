"""Offline placement and strict parsing for the three-job RTEMS wiring check."""

from hashlib import sha256
import json

from chaser.policy.allocator import CoreGroups, allocate

TASKS = ('packed', 'spread', 'conflict')
PROTOCOL = 'singleton-common-release-smoke-v1'


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def make_plan(cases: dict, configuration: dict) -> dict:
    """Require explicit synthetic U and core groups; never calibrate from smoke data."""
    c = configuration
    groups = CoreGroups(tuple(c['isolated']), tuple(c['non_isolated']))
    cores = groups.isolated + groups.non_isolated
    if (len(cores) != 4 or set(cores) != set(range(4))
            or any(type(core) is not int for core in cores)):
        raise ValueError('Smoke core groups must partition cores 0, 1, 2, 3')
    if set(c['utilization']) != set(TASKS) or c['utilization_source'] != 'synthetic':
        raise ValueError('Smoke requires the three baseline tasks and explicit synthetic U')
    placement = allocate(cases, c['utilization'], groups, kind=c['kind'],
                         threshold=c['threshold'], alpha=c.get('alpha'))
    if placement.infeasible:
        raise ValueError(f'Cannot execute incomplete mapping: {placement.infeasible}')
    return {'schema_version': 1, 'measurement_protocol': PROTOCOL,
            'configuration': c, 'mapping': placement.mapping,
            'mapping_hash': digest(placement.mapping), 'locality_hash': digest(cases),
            'scope': 'Wiring check only; baseline locality uses different linked ELFs'}


def _fields(line: str) -> dict:
    pairs = [part.split('=', 1) for part in line.split(',')[1:]]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError('Malformed result fields')
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Duplicate result fields')
    return result


def parse_log(log: str, plan: dict) -> dict:
    """Accept complete successful runs only, checking requested and observed cores."""
    lines = [line.strip() for line in log.splitlines()]
    headers = [_fields(line) for line in lines if line.startswith('SMOKE,')]
    jobs = [_fields(line) for line in lines if line.startswith('JOB,')]
    if (len(headers) != 1 or len(jobs) != len(TASKS)
            or lines.count('CHASER SMOKE PASS') != 1
            or any(line.startswith('SMOKE_ERROR,') for line in lines)):
        raise ValueError('Incomplete or failed smoke execution')
    header = headers[0]
    if (header.get('version') != '1' or header.get('cpus') != '4'
            or header.get('mapping_hash') != plan['mapping_hash']):
        raise ValueError('Wrong protocol, processor count or mapping')
    release = int(header['release_ns'])
    if release <= 0 or {row.get('task') for row in jobs} != set(TASKS):
        raise ValueError('Invalid release or duplicate/missing task')
    parsed = []
    for row in jobs:
        task = row.pop('task')
        values = {key: int(value) for key, value in row.items()}
        required = {'core', 'start_core', 'end_core', 'affinity_ok', 'cpu_ns',
                    'start_ns', 'completion_ns', 'check'}
        if set(values) != required:
            raise ValueError('Missing or unknown job fields')
        core = plan['mapping'][task]
        if (any(values[key] != core for key in ('core', 'start_core', 'end_core'))
                or values['affinity_ok'] != 1 or values['check'] != 1
                or not release <= values['start_ns'] < values['completion_ns']
                or not 0 < values['cpu_ns'] <= values['completion_ns'] - values['start_ns']):
            raise ValueError('Invalid affinity, checksum or timing')
        parsed.append({'task': task, **values,
                       'response_ns': values['completion_ns'] - release})
    return {'release_ns': release, 'jobs': sorted(parsed, key=lambda row: row['task']),
            'sum_job_cpu_ns': sum(row['cpu_ns'] for row in parsed),
            'sum_response_ns': sum(row['response_ns'] for row in parsed),
            'makespan_ns': max(row['completion_ns'] for row in parsed) - release}
