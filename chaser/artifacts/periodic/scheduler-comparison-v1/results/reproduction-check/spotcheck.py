"""Reproducibility spot-check before the cleanup (2026-10-07).

Rebuild one sampled case per design of experiments 27, 28, 41 and 44 with the trimmed runner (pm_run.prepare_one),
rerun 20 sampled runs, and compare with the raw outputs: prepared manifests (ELFs, sources, plans; build.log left
out), locality.json, yarda/*.json, configuration.json, and every field of the run records except wall-clock ones.
Run with PYTHONPATH=<c3 code copy>. Usage: python3 spotcheck.py <scratch output dir>
"""

import hashlib
import json
import random
import sys
from pathlib import Path

W = Path('/workspace/experiments/chaser')
sys.path.insert(0, str(W / 'artifacts/periodic/scheduler-comparison-v1/policy-mix'))
import pm_run  # noqa: E402
import hl_run  # noqa: E402
import run as design  # noqa: E402

hl_run.DESIGNS.update(pm_run.DESIGNS)
SAMPLE = {'deadline-small': ('g', 'c2', 'p_racgb', 'p_rnd0'), 'deadline-big': ('p', 'p_cgb', 'p_ra'),
          'deadline-small-caas': ('p_caas', 'p_clsa1cal'), 'deadline-big-caas': ('p_clsa1',),
          'memory-cost': ('p', 'p_cgb'), 'confirm-small': ('p_racgb', 'g', 'c', 'c2'),
          'confirm-big': ('p_racgb', 'c'), 'confirm-mem': ('p_racgb', 'c2')}
VOLATILE = {'started_utc', 'wall_seconds', 'run_id', 'log'}
SEED = 20261007


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_case(raw: Path, new: Path, placements) -> list[str]:
    out = []
    for name in ['locality.json'] + [f'yarda/{p.name}' for p in sorted((raw / 'yarda').glob('*.json'))]:
        if digest(raw / name) != digest(new / name):
            out.append(name)
    for placement in placements:
        if digest(raw / placement / 'configuration.json') != digest(new / placement / 'configuration.json'):
            out.append(f'{placement}/configuration.json')
        a, b = (json.loads((d / placement / 'prepared/manifest.json').read_text())['files'] for d in (raw, new))
        out += [f'{placement}/prepared/{k}' for k in sorted(set(a) | set(b)) if k != 'build.log' and a.get(k) != b.get(k)]
    return out


def compare_run(raw: Path, new: Path) -> list[str]:
    a, b = (json.loads((d / 'measurements.jsonl').read_text().splitlines()[0]) for d in (raw, new))
    return [k for k in sorted(set(a) | set(b)) if k not in VOLATILE and a.get(k) != b.get(k)]


def main():
    output = Path(sys.argv[1]).resolve()
    rng = random.Random(SEED)
    cases = []
    for name, keys in SAMPLE.items():
        hl_run.select_design(name)
        case = rng.choice(hl_run.cases())
        runs = [r for r in hl_run.RUNS if r[2] in keys]
        cases.append(dict(design=name, case=case, label=hl_run.label(case), placements=list(hl_run.hl.PLACEMENTS), runs=runs))

    def prepare(c):
        hl_run.select_design(c['design'])  # prepare_one reads the design's module from hl_run's globals
        pm_run.prepare_one(output / c['design'], c['case'])
        return c

    for c in cases:  # sequential: select_design sets module globals
        prepare(c)
        design.announce(f"prepared {c['design']} {c['label']}")
    report = dict(seed=SEED, cases=[])
    specs = []
    for c in cases:
        hl_run.select_design(c['design'])
        raw_case = hl_run.case_dir(W / '.cache' / f"{c['design']}-v1", c['case'])
        new_case = hl_run.case_dir(output / c['design'], c['case'])
        c['prepare_differences'] = compare_case(raw_case, new_case, c['placements'])
        for placement, arch, key in c['runs']:
            specs.append((f"{c['design']}/{c['label']}/{key}", new_case / placement / 'prepared', new_case / placement / arch, arch, 0))
        c['raw_case'], c['new_case'] = str(raw_case), str(new_case)
    failed, infra = design.run_specs(specs, len(specs))
    for c in cases:
        c['run_differences'] = {key: compare_run(Path(c['raw_case']) / placement / arch, Path(c['new_case']) / placement / arch)
                                for placement, arch, key in c['runs']}
        report['cases'].append(dict(c, case=list(c['case']), runs=[list(r) for r in c['runs']]))
    report.update(runs=len(specs), failed=failed, infra=infra,
                  identical_cases=sum(not c['prepare_differences'] for c in cases),
                  identical_runs=sum(not d for c in cases for d in c['run_differences'].values()))
    (output / 'spotcheck.json').write_text(json.dumps(report, indent=1) + '\n')
    print(f"cases with identical builds {report['identical_cases']}/{len(cases)}, "
          f"runs with identical records {report['identical_runs']}/{len(specs)}")


if __name__ == '__main__':
    main()
