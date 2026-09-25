"""Build comparable RF samples and preserve raw evidence in four JSONL tables."""

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isclose, isfinite
from pathlib import Path

from chaser.locality.cls import DEFAULT_ALPHAS
from chaser.locality.features import FEATURE_NAMES, build_features
from chaser.dataset.labeling import LABEL_RULE_ID, Measurement, label_measurements
from chaser.dataset.splits import LEGACY_POLICY, TASKSET_POLICY, taskset_split, validate_taskset_split

FEATURE_VERSION = 'caas-11/population-std/task-id-join-v1'


@dataclass(frozen=True)
class Workload:
    workload_id: str
    family_id: str
    utilization: Mapping[str, float | None]
    utilization_source: str
    input_signature: str | None = None


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _membership(workloads: Iterable[Workload]) -> dict[str, str]:
    result = {}
    for row in workloads:
        if not row.workload_id or not row.family_id or row.workload_id in result:
            raise ValueError('Unique workload IDs and nonempty family IDs are required')
        result[row.workload_id] = row.family_id
    if not result:
        raise ValueError('Workloads are required')
    return dict(sorted(result.items()))


def _validate_split(split: dict, membership: dict[str, str], signatures: dict) -> None:
    if split.get('schema_version') == 2:
        validate_taskset_split(split, membership, signatures)
        return
    if (split['schema_version'] != 1 or split['workloads'] != membership
            or set(split['families']) != set(membership.values())
            or set(split['families'].values()) != {'train', 'validation', 'test'}):
        raise ValueError('Frozen split does not match workload families')


def freeze_split(path: Path, workloads: Iterable[Workload], *, seed: int,
                 policy: str = TASKSET_POLICY) -> dict:
    """Freeze 60/20/20 within families; existing valid membership wins over seed.

    Workload input signatures bind duplicates and policy variants to one split.
    Legacy family holdout is explicit and retained for old artifact reproduction.
    Reusing a file under a different policy is rejected, never migrated in place.
    """
    workloads = list(workloads)
    membership = _membership(workloads)
    signatures = {w.workload_id: w.input_signature for w in workloads}
    if policy not in (TASKSET_POLICY, LEGACY_POLICY):
        raise ValueError('Unknown split policy')
    if path.exists():
        split = json.loads(path.read_text())
        if split.get('schema_version') != (2 if policy == TASKSET_POLICY else 1):
            raise ValueError('Frozen split policy mismatch')
        _validate_split(split, membership, signatures)
        return split
    if policy == TASKSET_POLICY:
        split = taskset_split(membership, signatures, seed=seed)
        with path.open('x') as stream:
            stream.write(_json(split) + '\n')
        return split
    families = sorted(set(membership.values()),
                      key=lambda f: (sha256(_json([seed, f]).encode()).hexdigest(), f))
    n = len(families)
    if n < 3:
        raise ValueError('At least three independent families are required')
    test = max(1, round(n * 0.1))
    validation = max(1, round(n * 0.2))
    train = n - test - validation
    groups = ['train'] * train + ['validation'] * validation + ['test'] * test
    split = {'schema_version': 1, 'seed': seed, 'workloads': membership,
             'families': dict(zip(families, groups))}
    with path.open('x') as stream:
        stream.write(_json(split) + '\n')
    return split


def build_dataset(cases: Mapping[str, dict], workloads: Iterable[Workload],
                  measurements: Iterable[Measurement], provenance: Mapping[str, dict],
                  split: dict, *, expected_runs: int) -> dict:
    """Join by task ID and exclude incomplete workloads from every representation.

    Build one allocator dataset at a time. U is workload-specific (period may
    vary), so characterization rows are keyed by workload_id and task_id.
    Missing schema/provenance/U is an error; unavailable locality or incomplete
    executions are retained with exclusion reasons. No train-time scaling occurs.
    """
    workloads = sorted(workloads, key=lambda w: w.workload_id)
    membership = _membership(workloads)
    _validate_split(split, membership, {w.workload_id: w.input_signature for w in workloads})
    if type(expected_runs) is not int or expected_runs < 1:
        raise ValueError('Positive expected_runs is required')
    measurements = sorted(measurements, key=lambda r: (r.workload_id, r.architecture, r.run_id))
    if any(r.workload_id not in membership for r in measurements):
        raise ValueError('Measurement references an unknown workload')
    if len({r.allocator_id for r in measurements}) > 1:
        raise ValueError('Build a separate dataset per allocator')
    if len({(r.time_unit, r.measurement_source) for r in measurements}) > 1:
        raise ValueError('Mixed measurement units or sources')
    for architecture in (0, 1, 2):
        if len({r.topology_id for r in measurements if r.architecture == architecture}) > 1:
            raise ValueError('Keep topology fixed per architecture across workloads')
    variants = [('caas-ca', None), ('ca-line', None), ('ca-csrd', None)] + [
        ('cls', a) for a in DEFAULT_ALPHAS]
    samples, characterizations, excluded = [], [], []
    used = sorted({t for w in workloads for t in w.utilization})
    required = {'source_hash', 'elf_hash', 'analyzer_commit', 'cache_model_id',
                'cache_config_hash', 'model_hash'}
    for t in used:
        if t not in cases or t not in provenance:
            raise ValueError(f'Missing locality or provenance: {t}')
        if (not required <= provenance[t].keys()
                or any(not provenance[t][k] for k in required - {'model_hash'})):
            raise ValueError(f'Missing provenance fields: {t}')
        if not {'ca_caas_element', 'ca_global_line', 'ca_csrd_l1', 'cls',
                'clp', 'modeled_accesses'} <= cases[t].keys():
            raise ValueError(f'Missing characterization fields: {t}')
    for w in workloads:
        if w.utilization_source not in ('measured-mean', 'wcet') or not w.utilization:
            raise ValueError('Utilization source and nonempty task mapping are required')
        tasks = []
        unavailable = False
        for t, u in sorted(w.utilization.items()):
            if u is None or not isfinite(u) or u < 0:
                raise ValueError(f'Utilization missing or invalid: {w.workload_id}/{t}')
            c = cases[t]
            tasks.append({**c, 'utilization': u})
            clp = c['clp']
            unavailable |= (c['modeled_accesses'] == 0 or clp is None)
            if clp is not None:
                unavailable |= (len(clp) != 3 or any(
                    p is None or not isfinite(p) or not 0 <= p <= 1 for p in clp))
                if not unavailable:
                    unavailable |= not isclose(sum(clp), 1, abs_tol=1e-12, rel_tol=0)
            characterizations.append({
                'workload_id': w.workload_id, 'task_id': t, 'ca_caas': c['ca_caas_element'],
                'ca_global_line': c['ca_global_line'], 'ca_csrd': c['ca_csrd_l1'],
                'cls': c['cls'], 'alpha': list(DEFAULT_ALPHAS), 'clp': clp,
                'modeled_accesses': c['modeled_accesses'], 'utilization': u,
                'utilization_source': w.utilization_source})
        try:
            if unavailable:
                raise ValueError('Unavailable CLP or no modeled accesses')
            features = [build_features(tasks, k, alpha=a) for k, a in variants]
            label = label_measurements((r for r in measurements if r.workload_id == w.workload_id),
                                       expected_runs=expected_runs)
        except ValueError as error:
            excluded.append({'workload_id': w.workload_id, 'reason': str(error)})
            continue
        for (kind, alpha), values in zip(variants, features):
            samples.append({'workload_id': w.workload_id, 'representation_id': kind,
                            'alpha': alpha, 'features': values, 'label': label.label,
                            'label_rule_id': LABEL_RULE_ID, 'family_id': w.family_id,
                            'split_group': (split['assignments'][w.workload_id]
                                            if split['schema_version'] == 2
                                            else split['families'][w.family_id]),
                            'label_evidence': asdict(label)})
    return {'raw_measurements': [asdict(r) for r in measurements],
            'task_characterization': characterizations, 'rf_samples': samples,
            'provenance': [{'task_id': t, **provenance[t]} for t in used],
            'metadata': {'schema_version': 1, 'feature_version': FEATURE_VERSION,
                         'feature_names': FEATURE_NAMES, 'split': split,
                         'split_hash': sha256(_json(split).encode()).hexdigest(),
                         'expected_runs': expected_runs, 'label_rule_id': LABEL_RULE_ID,
                         'excluded': excluded}}


def write_dataset(directory: Path, dataset: dict) -> None:
    """Create a new artifact directory; never overwrite a previous dataset."""
    tables = ('raw_measurements', 'task_characterization', 'rf_samples', 'provenance')
    contents = {name + '.jsonl': ''.join(_json(r) + '\n' for r in dataset[name])
                for name in tables}
    contents['metadata.json'] = _json(dataset['metadata']) + '\n'
    directory.mkdir()
    for name, content in contents.items():
        (directory / name).write_text(content)
