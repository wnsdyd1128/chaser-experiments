"""Validate complete YARDA RESULT/EVENTS pairs before independent S1 replay."""

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isclose

from chaser.locality.cache_reference import CacheLevel, FirstHits, validate_hierarchy
from chaser.locality.estimators import csrd_counts


@dataclass
class Analysis:
    task: dict
    l1: CacheLevel
    llc: CacheLevel
    counts: FirstHits
    lines: list[int]
    stream_hash: str


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Artifact count/address must be a valid integer')
    return value


def _stream(events: dict, task: dict, line_bytes: int) -> tuple[list[int], str]:
    if events['schema_version'] != 1 or events['events_truncated'] is not False:
        raise ValueError('A complete EVENTS v1 stream is required')
    rows = events['events']
    if len(rows) != task['modeled_accesses'] or _integer(events['event_limit']) < len(rows):
        raise ValueError('Event population differs from modeled accesses')
    source, span, base, size, spans, operation, obj = 0, 0, 0, 0, 0, None, None
    lines, digest = [], sha256()
    for event in rows:
        ordinal = _integer(event['source_access_ordinal'])
        offset = _integer(event['line_span_ordinal'])
        address = _integer(event['linked_address'])
        access_size = _integer(event['access_size'], 1)
        if event['task_id'] != task['task_id'] or (ordinal, offset) != (source, span):
            raise ValueError('Event task/ordinal ordering mismatch')
        if event['operation'] not in ('load', 'store') or not event['object_id']:
            raise ValueError('Unsupported event operation/object')
        if span == 0:
            base, size, operation, obj = address, access_size, event['operation'], event['object_id']
            if base + size > 2 ** 64:
                raise ValueError('Event address range overflows')
            spans = (base % line_bytes + size + line_bytes - 1) // line_bytes
        expected_address = base if span == 0 else (base // line_bytes + span) * line_bytes
        if (address != expected_address or access_size != size or
                event['operation'] != operation or event['object_id'] != obj):
            raise ValueError('Cross-line event span mismatch')
        # Only the input-side fields participate, never YARDA's set/tag/outcome.
        identity = [task['task_id'], source, span, obj, address, size, operation]
        digest.update((json.dumps(identity, separators=(',', ':')) + '\n').encode())
        lines.append(address // line_bytes)
        span += 1
        if span == spans:
            source, span = source + 1, 0
    if span or source != task['source_accesses']:
        raise ValueError('Incomplete source-access event population')
    return lines, digest.hexdigest()


def read_analysis(result: dict, events: dict, task_id: str, inputs: dict) -> Analysis:
    """Reject incomplete/incompatible artifacts instead of scoring them as zero error."""
    required = {'schema_version': 2, 'analysis_mode': 'hierarchy-rd',
                'model_id': 'exact-two-level-lru-demand-v1', 'csrd_mode': 'full-exact',
                'address_basis': 'linked_absolute'}
    if any(result[k] != v for k, v in required.items()):
        raise ValueError('Unsupported YARDA analysis model/schema/address basis')
    if any(result['inputs'][k] != v for k, v in inputs.items()):
        raise ValueError('Analysis input hashes differ')
    if events['analysis_id'] != result['analysis_id']:
        raise ValueError('RESULT/EVENTS analysis identity mismatch')
    if len(result['tasks']) != 1 or result['tasks'][0]['task_id'] != task_id:
        raise ValueError('Expected one matching result task')
    hierarchy = result['cache_hierarchy']
    model = {'allocation': 'all-demand-misses', 'lower_level_requests': 'l1-misses-only',
             'inclusion': 'independent-no-back-invalidation-or-victim-insertion',
             'task_initial_state': 'cold'}
    if any(hierarchy[k] != v for k, v in model.items()):
        raise ValueError('Unsupported demand-cache contract')
    path = result['selected_path']
    levels = {level['name']: level for level in hierarchy['levels']}
    if len(levels) != 2 or path['l1_name'] == path['llc_name']:
        raise ValueError('Expected exactly two distinct cache levels')
    caches = []
    for key, role in (('l1_name', 'L1'), ('llc_name', 'LLC')):
        level = levels[path[key]]
        cache = CacheLevel(level['size_bytes'], level['line_size_bytes'], level['associativity'])
        if level['replacement'] != 'LRU' or level['role'] != role or level['set_count'] != cache.sets:
            raise ValueError('Unsupported or inconsistent cache geometry')
        caches.append(cache)
    l1, llc = caches
    validate_hierarchy(l1, llc)
    task = result['tasks'][0]
    source, modeled = _integer(task['source_accesses']), _integer(task['modeled_accesses'])
    coverage = {'source_accesses': source, 'resolved_accesses': source, 'rejected_accesses': 0,
                'emitted_line_references': modeled, 'excluded_opaque_call_sites': 0}
    if (task['coverage']['complete'] is not True or
            any(_integer(task['coverage'][k]) != v for k, v in coverage.items())):
        raise ValueError('Incomplete analysis coverage')
    for key in ('level_conservation_l1', 'level_conservation_llc', 'llc_input_matches_l1_misses',
                'first_service_conservation', 'all_passed'):
        if task['invariants'][key] is not True:
            raise ValueError('Analysis conservation invariant failed')
    counts = csrd_counts(task, l1, llc)
    exported = FirstHits(*(task[k] for k in
                          ('l1_first_hit_count', 'llc_first_hit_count', 'all_cache_miss_count')))
    if exported != counts:
        raise ValueError('Exported first-hit counts disagree with CSRD thresholds')
    for key, hit in (('l1', counts.l1), ('llc', counts.llc)):
        profile = task[key]
        if (_integer(profile['hits']) != hit or
                _integer(profile['misses']) != profile['lookups'] - hit):
            raise ValueError('Exported level counts disagree with CSRD thresholds')
    ratios = [task[k] for k in ('l1_first_hit_ratio', 'llc_first_hit_ratio', 'all_cache_miss_ratio')]
    if counts.total:
        if any(type(r) not in (float, int) or not isclose(r, expected, rel_tol=0, abs_tol=1e-12)
               for r, expected in zip(ratios, counts.ratios)):
            raise ValueError('Exported ratios disagree with counts')
    elif ratios != [None, None, None]:
        raise ValueError('Empty analysis must have null ratios')
    lines, stream_hash = _stream(events, task, l1.line_bytes)
    return Analysis(task, l1, llc, counts, lines, stream_hash)
