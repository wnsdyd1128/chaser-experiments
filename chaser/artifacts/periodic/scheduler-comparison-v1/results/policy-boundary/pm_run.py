"""Run the policy-mix design through high-load/hl_run.py: prepare, isolated, pilot, full, stats.

--design policy-mix (default, mix_set): wfd/, tg/, ra/ and ra-tg/ builds per case; G,
C2 (1+1+2) and P run on wfd, P on tg (p_tg), ra (p_ra) and ra-tg (p_ratg).
--design policy-mix-cls (mix_cls_set): the same cases with wfd/, cg/ and ra-cg/ builds;
P runs on cg (p_cg) and ra-cg (p_racg), to pair with a policy-mix output.
--design policy-boundary (boundary_set): 24 period-CV x memory cells; wfd/, cgb/, ra/ and
ra-cgb/ builds with P on each (p, p_cgb, p_ra, p_racgb).
On top of hl_run's prepare, every case runs yarda_cpp on the wfd build (locality.json:
counts, CLS, IR instructions per task; CLS must equal the planned closed form) and the
policy-mix scripts are snapshot next to hl_run's. Run pm_check.py first (its shapes are
the same for both designs); run with PYTHONPATH set to the c3 code copy. Stages and
options are hl_run's.
"""

import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

from tools.rtems_smoke import file_hash, write_json

import bi_run
import boundary_set
import hl_run
import mix_cls_set
import mix_set
import yarda_counts

DESIGN = 'policy-mix'
RUNS = (('wfd', 'g', 'g'), ('wfd', 'c2', 'c2'), ('wfd', 'p', 'p'), ('tg', 'p', 'p_tg'), ('ra', 'p', 'p_ra'),
        ('ra-tg', 'p', 'p_ratg'))
PAIRS = (('p_ratg', 'p'), ('p_ratg', 'p_tg'), ('p_ratg', 'p_ra'), ('p_tg', 'p'), ('p_ra', 'p'), ('g', 'p_ratg'),
         ('c2', 'p_ratg'), ('g', 'p'))
CLS_RUNS = (('cg', 'p', 'p_cg'), ('ra-cg', 'p', 'p_racg'))
CLS_PAIRS = (('p_racg', 'p_cg'),)
BOUNDARY_RUNS = (('wfd', 'p', 'p'), ('cgb', 'p', 'p_cgb'), ('ra', 'p', 'p_ra'), ('ra-cgb', 'p', 'p_racgb'))
BOUNDARY_PAIRS = (('p_cgb', 'p_ra'), ('p_racgb', 'p_ra'), ('p_racgb', 'p_cgb'), ('p_cgb', 'p'), ('p_ra', 'p'))
SNAPSHOT = ('placement_lib.py', 'mix_set.py', 'mix_cls_set.py', 'boundary_set.py', 'pm_check.py', 'pm_run.py',
            'test_placement_lib.py', 'test_mix_set.py', 'test_boundary_set.py')
HL_SNAPSHOT = ('hl_run.py', 'hl_set.py', 'mem_set.py')

_hl_prepare_one, _hl_prepare_all = hl_run.prepare_one, hl_run.prepare_all


def prepare_one(output, case):
    manifests = _hl_prepare_one(output, case)
    target = hl_run.case_dir(output, case)
    counts = yarda_counts.analyze(target / 'wfd/prepared', target / 'yarda')
    rows = []
    for task in json.loads((target / 'wfd/configuration.json').read_text())['tasks']:
        count = counts[task['task_id']]
        if abs(count['cls'] - task['cls_planned']) > bi_run.CLS_TOLERANCE:
            raise ValueError(f'{hl_run.label(case)}/{task["task_id"]}: yarda CLS {count["cls"]} != planned')
        rows.append(dict(count, task_id=task['task_id'], role=task['role'], period_ticks=task['period_ticks'],
                         u_planned=task['u_planned'], footprint_kib=task['footprint_kib'],
                         traffic_planned=task['traffic_planned']))
    write_json(target / 'locality.json', dict(tasks=rows))
    return manifests


def prepare_all(output, workers):
    _hl_prepare_all(output, workers)
    for name in SNAPSHOT:
        if (HERE / name).exists():
            shutil.copyfile(HERE / name, output / name)
    protocol = json.loads((output / 'protocol.json').read_text())
    protocol['snapshot_hashes'].update({name: file_hash(output / name) for name in SNAPSHOT
                                        if (output / name).exists()})
    if hasattr(hl_run.hl, 'protocol_extra'):
        protocol.update(hl_run.hl.protocol_extra())
    else:
        protocol.update(factors=mix_set.FACTORS, set_factors=[mix_set.factors(k) for k in range(mix_set.SETS)],
                        seed_base=mix_set.SEED_BASE)
    protocol.update(placements=hl_run.hl.PLACEMENTS, pairs=hl_run.PAIRS)
    write_json(output / 'protocol.json', protocol)


def main():
    hl_run.DESIGNS[DESIGN] = (mix_set, RUNS, PAIRS)
    hl_run.DESIGNS['policy-mix-cls'] = (mix_cls_set, CLS_RUNS, CLS_PAIRS)
    hl_run.DESIGNS['policy-boundary'] = (boundary_set, BOUNDARY_RUNS, BOUNDARY_PAIRS)
    hl_run.SNAPSHOT = HL_SNAPSHOT
    # hl_run's stages look these up as module globals.
    hl_run.prepare_one, hl_run.prepare_all = prepare_one, prepare_all
    if '--design' not in sys.argv:
        sys.argv += ['--design', DESIGN]
    hl_run.main()


if __name__ == '__main__':
    main()
