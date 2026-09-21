"""Expand source-informed families and retain a record of duplicate exclusions."""

import json

from chaser.periodic_recipes import RECIPES
from tools.rtems_periodic_pool import ROOT
from tools.rtems_periodic_pool_audit import input_signature
from tools.rtems_periodic_pool_v2 import (
    REVISION, SOURCE_PATHS, candidate_pool as previous_pool, recipe_candidates,
)
from tools.rtems_smoke import file_hash


NEW_SOURCES = {
    'staged-butterfly': ['bench/kernel/fft/fft.c'],
    'triangular-solve': ['bench/kernel/ludcmp/ludcmp.c'],
}


def candidate_pool() -> dict:
    """Enumerate five families; keep first identical input without using outcomes.

    Original target-tagged duplicates remain in duplicate_candidates with the
    representative identity. This is a new provisional pool, never a rewrite
    of V2 or a statement of statistical sufficiency.
    """
    design = previous_pool()['design']
    manifest_path = ROOT / 'rtems/periodic/staged-recipe-sources.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest['revision'] != REVISION or {f['path'] for f in manifest['files']} !=
            {p for paths in NEW_SOURCES.values() for p in paths}):
        raise ValueError('Staged recipe source manifest does not match the declared corpus')
    design.update(version='periodic-candidates-v3',
        staged_source_manifest_hash=file_hash(manifest_path),
        staged_recipe_contract='rtems/periodic/STAGED-RECIPES.md',
        lineage_limit='five conservative groups; validation/test still one family each',
        deduplication_rule='first exact generator input excluding names and eligibility metadata',
        pending=[*design['pending'][:-1], 'five families do not establish split sufficiency',
                 'LLC high-load coverage and role/core/period confounding remain'])
    sources = {**SOURCE_PATHS, **NEW_SOURCES}
    groups = {group: [p for p, g in RECIPES.items() if g == group] for group in sources}
    generated = recipe_candidates(design, groups, sources, version=3)
    seen, unique, duplicates = {}, [], []
    for row in generated:
        signature = input_signature(row['configuration'])
        if signature in seen:
            duplicates.append(dict(row, duplicate_of=seen[signature],
                                   exclusion_reason='duplicate_generator_input'))
        else:
            seen[signature] = row['configuration']['workload_id']
            unique.append(row)
    design['generated_candidate_workloads'] = len(generated)
    return dict(design=design, candidates=unique, duplicate_candidates=duplicates,
                dataset_ready=False, split_frozen=False)
