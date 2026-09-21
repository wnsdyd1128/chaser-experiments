"""Conservative lineage audit before proposing a periodic workload split.

The fixed structural catalog, rather than caller-supplied family names, defines
base-task lineage. Shared recipes or base tasks connect whole workload families.
Known development structures are excluded even if a caller renames their recipe.
"""

from copy import deepcopy

from chaser.periodic import digest, make_plan
from chaser.periodic_patterns import job_access_count
from chaser.periodic_recipes import RECIPES
from chaser.periodic_structures import STRUCTURES


DEVELOPMENT_STRUCTURES = frozenset(('cyclic', 'hot-cold', 'phase'))
LINEAGES = {p: p for p in (*DEVELOPMENT_STRUCTURES, *STRUCTURES)}
# Whole-array and tiled directional scans share their base traversal recipe.
LINEAGES.update({'forward-reverse': 'directional-scan', 'tile-reverse': 'directional-scan'})
LINEAGES.update(RECIPES)


def build_registry(records: list[dict]) -> dict:
    """Return deterministic components and global identities, without a split.

Records contain configuration, recipe_id, role, and development_exposed. A task
identity is bound to its workload and configuration; final ELF/snapshot evidence
must be added after build. Neither estimated U nor a valid plan grants eligibility.
"""
    rows, links, seen = [], {}, set()
    for source in sorted(records, key=lambda r: r['configuration']['workload_id']):
        row = deepcopy(source)
        config = row['configuration']
        name = config['workload_id']
        if name in seen:
            raise ValueError('Duplicate workload identity')
        seen.add(name)
        if (not isinstance(row['recipe_id'], str) or not row['recipe_id']
                or row['role'] not in ('candidate', 'development')
                or type(row['development_exposed']) is not bool):
            raise ValueError('Explicit recipe, role and development exposure required')
        for architecture in range(3):
            make_plan(config, architecture)
        patterns = {t.get('pattern', 'cyclic') for t in config['tasks']}
        lineages = {LINEAGES[p] for p in patterns}
        tokens = {'recipe:' + row['recipe_id']} | {'base:' + b for b in lineages}
        row.update(workload_id=name, base_task_lineages=sorted(lineages), tokens=tokens,
                   development_exposed=(row['development_exposed']
                       or row['role'] == 'development' or bool(patterns & DEVELOPMENT_STRUCTURES)))
        index = len(rows)
        for token in tokens:
            links.setdefault(token, set()).add(index)
        rows.append(row)

    remaining, families = set(range(len(rows))), {}
    while remaining:
        pending, members, tokens = [min(remaining)], set(), set()
        while pending:
            index = pending.pop()
            if index in members:
                continue
            members.add(index)
            for token in rows[index]['tokens']:
                tokens.add(token)
                pending.extend(links[token] - members)
        remaining -= members
        family_id = 'family-' + digest(sorted(tokens))[:16]
        exposed = any(rows[i]['development_exposed'] for i in members)
        families[family_id] = dict(workloads=sorted(rows[i]['workload_id'] for i in members),
            lineage_tokens=sorted(tokens), development_exposed=exposed)
        for i in members:
            row = rows[i]
            row.pop('tokens')
            config = row['configuration']
            config['family_id'] = family_id
            identity = digest(config)
            plan = make_plan(config, 2)
            row.update(family_id=family_id, configuration_hash=identity,
                       family_development_exposed=exposed,
                       primary_candidate=row['role'] == 'candidate' and not exposed,
                       exclusion_reasons=['development_lineage'] if exposed else [],
                       tasks=[dict(task_id=t['task_id'],
                           global_task_id='task-' + digest([row['workload_id'], t['task_id'], identity]),
                           base_task_lineage=LINEAGES[t.get('pattern', 'cyclic')],
                           snapshot_hash=None, allocated_bytes=t['data_size'],
                           active_lines=min(t['distinct'], (t['data_size'] - t['stride']) // 32 + 1),
                           loads_per_job=job_access_count(t), period_ticks=t['period_ticks'],
                           job_count=t['job_count']) for t in plan['tasks']])
    return dict(schema_version=1, lineage_rule='structural-components-v1',
                families=dict(sorted(families.items())), workloads=rows,
                primary_family_count=len({r['family_id'] for r in rows if r['primary_candidate']}))
