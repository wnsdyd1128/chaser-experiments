"""Deterministic taskset assignment within each workload family."""

from collections import defaultdict
from hashlib import sha256
import json


TASKSET_POLICY = 'taskset-stratified-60-20-20-v1'
LEGACY_POLICY = 'family-70-20-10-v1'
GROUPS = ('train', 'validation', 'test')


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                             separators=(',', ':')).encode()).hexdigest()


def taskset_split(membership: dict[str, str], signatures: dict[str, str], *, seed: int) -> dict:
    """Assign unique input signatures, keeping aliases together and families in all splits.

    SHA-256 ranking makes the seeded shuffle independent of input order and the
    Python random implementation. Largest remainders use train/validation/test
    tie order; for three inputs, move one from train to test to keep all nonempty.
    Fewer than three unique inputs in any family is an error, never a silent
    fallback to family holdout. Callers must supply outcome-independent identities.
    """
    if type(seed) is not int:
        raise ValueError('Integer split seed required')
    if set(signatures) != set(membership) or any(
            not isinstance(s, str) or len(s) != 64 or any(c not in '0123456789abcdef' for c in s)
            for s in signatures.values()):
        raise ValueError('SHA-256 input signature required for every workload')
    families, owners = defaultdict(set), {}
    for name, family in membership.items():
        signature = signatures[name]
        if signature in owners and owners[signature] != family:
            raise ValueError('Identical input assigned to multiple families')
        owners[signature] = family
        families[family].add(signature)
    assigned, counts = {}, {}
    for family, inputs in sorted(families.items()):
        n = len(inputs)
        if n < 3:
            raise ValueError('Each family requires at least three unique inputs')
        numerators = (3 * n, n, n)
        sizes = [v // 5 for v in numerators]
        remainder_order = sorted(range(3), key=lambda i: (-(numerators[i] % 5), i))
        for i in remainder_order[:n - sum(sizes)]:
            sizes[i] += 1
        for i in range(3):
            if sizes[i] == 0:
                donor = max(range(3), key=lambda j: (sizes[j], -j))
                sizes[donor] -= 1
                sizes[i] += 1
        ranked = sorted(inputs, key=lambda s: (_hash([TASKSET_POLICY, seed, family, s]), s))
        groups = [g for g, count in zip(GROUPS, sizes) for _ in range(count)]
        assigned.update(zip(ranked, groups))
        counts[family] = dict(zip(GROUPS, sizes))
    result = dict(schema_version=2, policy_id=TASKSET_POLICY, seed=seed,
        ratios=dict(zip(GROUPS, (0.6, 0.2, 0.2))),
        shuffle_rule='sha256([policy_id,seed,family_id,input_signature]); ascending hex',
        rounding_rule='largest-remainder; ties train,validation,test; nonempty from largest donor',
        minimum_unique_inputs_per_family=3,
        workloads=dict(sorted(membership.items())), input_signatures=dict(sorted(signatures.items())),
        assignments={name: assigned[signatures[name]] for name in sorted(membership)},
        family_counts=counts)
    result['membership_hash'] = _hash(result)
    return result


def validate_taskset_split(split: dict, membership: dict[str, str], signatures: dict[str, str]) -> None:
    """Recompute the frozen assignment, including metadata and its integrity hash."""
    try:
        expected = taskset_split(membership, signatures, seed=split['seed'])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError('Frozen split has invalid membership or input identities') from error
    if split != expected:
        raise ValueError('Frozen split does not match inputs or deterministic assignment')
