"""Export CLP RF samples from the frozen final-label analysis set."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from chaser.features import CLP_FEATURE_NAMES, CLP_FEATURE_VERSION, build_features

POLICIES = ('caas-ca', 'ca-csrd', 'cls')
SOURCE_FILES = ('eligibility.json', 'split.json', *(
    f'{policy}/{name}' for policy in POLICIES
    for name in ('rf_samples.jsonl', 'task_characterization.jsonl')
))


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def build_clp_samples(eligibility: dict, split: dict, characterizations: list[dict],
                      scalar_samples: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Join frozen common workloads to task CLP/U and each policy's measured label."""
    common = eligibility['common_workloads']
    common_set = set(common)
    assignments, families = split['assignments'], split['workloads']
    if (not common or len(common_set) != len(common) or not common_set <= assignments.keys()
            or not common_set <= families.keys() or set(eligibility['required_policies']) != set(POLICIES)
            or set(scalar_samples) != set(POLICIES)):
        raise ValueError('Invalid common analysis set or policy set')

    evidence = {}
    for row in eligibility['policy_workloads']:
        key = (row['kind'], row['workload_id'])
        if key in evidence:
            raise ValueError(f'Duplicate eligibility row: {key}')
        evidence[key] = row
    if set(evidence) != {(policy, w) for policy in POLICIES for w in assignments}:
        raise ValueError('Eligibility does not cover the frozen population')
    if any(evidence[(policy, w)]['common_eligible'] != (w in common_set)
           for policy in POLICIES for w in assignments):
        raise ValueError('Eligibility disagrees with the common analysis set')

    tasks = defaultdict(dict)
    for row in characterizations:
        w = row['workload_id']
        if w not in common_set:
            continue
        task_id = row['task_id']
        if (task_id in tasks[w] or row['modeled_accesses'] <= 0
                or row['utilization_source'] != 'measured-mean'
                or not row['u_characterization_id'] or not row['u_elf_hash']):
            raise ValueError(f'Invalid task characterization: {w}/{task_id}')
        tasks[w][task_id] = row
    if set(tasks) != common_set:
        raise ValueError('Missing task profiles for the common analysis set')
    features = {w: build_features([tasks[w][t] for t in sorted(tasks[w])], 'clp')
                for w in common}

    result = {}
    expected = {(w, rep) for w in common_set for rep in POLICIES}
    for policy in POLICIES:
        indexed = {}
        for row in scalar_samples[policy]:
            key = (row['workload_id'], row['representation_id'])
            if key in indexed:
                raise ValueError(f'Duplicate scalar sample: {policy}/{key}')
            indexed[key] = row
        if set(indexed) != expected:
            raise ValueError(f'Scalar samples differ from the common analysis set: {policy}')
        result[policy] = []
        for w in sorted(common_set):
            rows = [indexed[(w, rep)] for rep in POLICIES]
            reference = rows[0]
            policy_evidence = evidence[(policy, w)]
            if (not policy_evidence['eligible'] or not policy_evidence['common_eligible']
                    or reference['label_evidence'] != policy_evidence['label_evidence']
                    or reference['label'] != reference['label_evidence']['label']
                    or reference['split_group'] != assignments[w]
                    or reference['family_id'] != families[w]
                    or any(not row['eligible_for_common_analysis']
                           or row['label'] != reference['label']
                           or row['label_evidence'] != reference['label_evidence']
                           or row['split_group'] != reference['split_group']
                           or row['family_id'] != reference['family_id']
                           or row['allocator_id'] != reference['allocator_id']
                           or len(row['features']) != 11
                           or row['features'][5:] != features[w][15:] for row in rows)):
                raise ValueError(f'Scalar label, split or U mismatch: {policy}/{w}')
            output = dict(reference)
            output.update(representation_id='clp', alpha=None, features=features[w])
            result[policy].append(output)
    return result


def export_final_clp(source: Path, output: Path) -> dict:
    """Verify the analysis-set lock and write a separate CLP feature version."""
    if output.exists():
        raise FileExistsError(f'CLP export already exists: {output}')
    lock = json.loads((source / 'analysis-set-lock.json').read_text())
    if set(lock['source_hashes']) != set(SOURCE_FILES):
        raise ValueError('Analysis-set lock has an unexpected source file set')
    for name in SOURCE_FILES:
        digest = sha256((source / name).read_bytes()).hexdigest()
        if digest != lock['source_hashes'][name]:
            raise ValueError(f'Analysis-set source hash mismatch: {name}')
    if len({lock['source_hashes'][f'{p}/task_characterization.jsonl']
            for p in POLICIES}) != 1:
        raise ValueError('Policies have different task characterizations')

    eligibility = json.loads((source / 'eligibility.json').read_text())
    split = json.loads((source / 'split.json').read_text())
    if (len(eligibility['common_workloads']) != lock['common_count']
            or dict(Counter(split['assignments'][w]
                            for w in eligibility['common_workloads'])) != lock['split_counts']):
        raise ValueError('Analysis-set count or split differs from lock')
    samples = build_clp_samples(
        eligibility, split, _rows(source / 'caas-ca/task_characterization.jsonl'),
        {p: _rows(source / p / 'rf_samples.jsonl') for p in POLICIES})
    contents = {f'{p}/rf_samples.jsonl': ''.join(_json(row) + '\n' for row in samples[p])
                for p in POLICIES}
    summary = {'schema_version': 1, 'analysis_set_id': lock['analysis_set_id'],
               'common_eligible': lock['common_count'], 'split_counts': lock['split_counts'],
               'feature_version': CLP_FEATURE_VERSION, 'feature_names': CLP_FEATURE_NAMES,
               'feature_dimension': len(CLP_FEATURE_NAMES),
               'sample_rows': {p: len(samples[p]) for p in POLICIES},
               'source_hashes': lock['source_hashes'],
               'files': {name: sha256(value.encode()).hexdigest()
                         for name, value in contents.items()}, 'rf_trained': False}
    output.mkdir(parents=True)
    for name, content in contents.items():
        path = output / name
        path.parent.mkdir()
        path.write_text(content)
    (output / 'summary.json').write_text(_json(summary) + '\n')
    return summary
