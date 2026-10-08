"""Copy each study's small design inputs and results out of .cache into results/.

Rebuildable outputs (prepared ELFs, YARDA events, raw run directories) stay in
.cache. Per study, results/<name>/ receives:
  - top-level files of the run output: protocol, results, statistics and
    isolated/empty controls
  - snapshot.tar.gz: the script snapshots the run used (the top-level .py
    files; their SHA-256 under "snapshot" in MANIFEST.json, as in protocol.json)
  - calibration tables and fitted models
  - figures/*.png and *.csv
  - per-set.jsonl.gz: every configuration.json, cls.json, locality.json and
    summary.json outside prepared/ builds, one {"path", "content"} line each
  - MANIFEST.json: SHA-256 of every exported file
results/environment.json records the simulator, toolchain and analyzer builds.
Usage: python3 export_results.py <study> [<study> ...]   (names: see STUDIES)
"""

import gzip
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / '.cache'
RESULTS = HERE / 'results'
STUDIES = {
    'period-distribution': 'period-distribution-v2',
    'release-aware-control': 'period-distribution-cohort-v2',
    'cls-distribution': 'cls-distribution-v1',
    'cache-affinity-o0': 'cache-affinity-v2',
    'cache-affinity-o2': 'cache-affinity-o2-v1',
    'cls-bimodal': 'cls-bimodal-v2',
    'cls-bimodal-ext': 'cls-bimodal-v2-ext',
    'load-level': 'load-level-v1',
    'u-imbalance': 'u-imbalance-v1',
    'l2-probe': 'l2-probe-v1',
    'footprint': 'footprint-v1',
    'high-load': 'high-load-v1',
    'infeasible': 'infeasible-v1',
    'memory-load': 'memory-load-v1',
    'g-vs-c': 'g-vs-c-v1',
    'g-vs-c-sync': 'g-vs-c-sync-v1',
    'policy-mix': 'policy-mix-v1',
    'policy-mix-cls': 'policy-mix-cls-v1',
    'policy-boundary': 'policy-boundary-v1',
    'task-count': 'task-count-v1',
    'small-memory': 'small-memory-v1',
    'period-taskcount': 'period-taskcount-v1',
    'period-taskcount-cohort': 'period-taskcount-cohort-v1',
    'cls-spread': 'cls-spread-v1',
    'small-memory-load': 'small-memory-load-v1',
    'conflict-cls': 'conflict-cls-v2',
    'random-small-memory': 'random-small-memory-v1',
    'random-task-count': 'random-task-count-v1',
    'random-cls-spread': 'random-cls-spread-v1',
    'random-small-memory-load': 'random-small-memory-load-v1',
    'random-conflict-cls': 'random-conflict-cls-v1',
    'random-policy-boundary': 'random-policy-boundary-v1',
    'random-policy-mix': 'random-policy-mix-v1',
    'deadline-small': 'deadline-small-v1',
    'deadline-big': 'deadline-big-v1',
    'deadline-small-caas': 'deadline-small-caas-v1',
    'deadline-big-caas': 'deadline-big-caas-v1',
    # Re-analysis of the bundles above (feature-precheck/precheck.py); no simulation.
    'feature-precheck': 'feature-precheck-v1',
    # The 20 ms design whose pilot missed deadlines; kept as the reason for v2. Its .cache output
    # was deleted on 2026-10-05, so results/cls-bimodal-v1-pilot cannot be re-exported.
    'cls-bimodal-v1-pilot': 'cls-bimodal-v1',
    'memory-cost': 'memory-cost-v1',
    'confirm-small': 'confirm-small-v1',
    'confirm-big': 'confirm-big-v1',
    'confirm-mem': 'confirm-mem-v1',
}
TOP_LEVEL = ('.json', '.jsonl', '.md')
CALIBRATION = ('calibration.json', 'sweeps.json', 'sweep-cost.json', 'model.json', 'measured.json',
               'extend.json', 'model-before-extend.json')
PER_SET = ('configuration.json', 'cls.json', 'locality.json', 'summary.json')
TOOLS = {
    'laysim': Path('/opt/laysim-gr740/laysim-gr740-cli'),
    'sparc-rtems6-gcc': Path('/opt/rtems/6/bin/sparc-rtems6-gcc'),
    'yarda_cpp (CLS distribution, feat/cpp-backend a058a454)': CACHE / 'yarda-a058a454-build/backend/yarda_cpp',
    'yarda_cpp (CLS bimodal, feat/cpp-backend 374b2c9 + frontend 2670c6e)':
        CACHE / 'yarda-374b2c9-build/backend/yarda_cpp',
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_snapshot(scripts, path: Path) -> dict:
    """Write the scripts into a tar.gz whose bytes depend only on their names and contents; return name -> SHA-256."""
    with gzip.GzipFile(path, 'wb', mtime=0) as stream, tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for script in sorted(scripts, key=lambda p: p.name):
            info = tarfile.TarInfo(script.name)
            info.size, info.mode = script.stat().st_size, 0o644
            with script.open('rb') as data:
                archive.addfile(info, data)
    return {p.name: sha256(p) for p in sorted(scripts, key=lambda p: p.name)}


def first_line(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True).stdout.splitlines()[0]


def environment() -> dict:
    import matplotlib
    import numpy
    import scipy
    return dict(
        tools={name: dict(path=str(path), sha256=sha256(path)) for name, path in TOOLS.items()},
        compiler_version=first_line([str(TOOLS['sparc-rtems6-gcc']), '--version']),
        clang_version=first_line(['clang-14', '--version']),
        python=platform.python_version(),
        packages=dict(numpy=numpy.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__))


def export(name: str) -> None:
    source = CACHE / STUDIES[name]
    # A study output has protocol.json; the L2 probe writes probe.json instead.
    if not any((source / marker).exists() for marker in ('protocol.json', 'probe.json')):
        raise SystemExit(f'{name}: {source} has no protocol.json or probe.json')
    target = RESULTS / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    copied = [p for p in source.iterdir() if p.is_file() and p.suffix in TOP_LEVEL]
    copied += [p for p in (source / 'calibration').glob('*') if p.name in CALIBRATION]
    copied += [p for p in (source / 'figures').glob('*') if p.suffix in ('.png', '.csv')]
    for path in copied:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    snapshot = write_snapshot([p for p in source.iterdir() if p.is_file() and p.suffix == '.py'],
                              target / 'snapshot.tar.gz')
    per_set = sorted(p for p in source.rglob('*.json') if p.name in PER_SET
                     and 'prepared' not in p.relative_to(source).parts)
    with gzip.open(target / 'per-set.jsonl.gz', 'wt') as stream:
        for path in per_set:
            stream.write(json.dumps(dict(path=str(path.relative_to(source)),
                                         content=json.loads(path.read_text())), sort_keys=True) + '\n')
    files = sorted(p for p in target.rglob('*') if p.is_file())
    (target / 'MANIFEST.json').write_text(json.dumps(dict(
        source=str(source.relative_to(ROOT)), exported_utc=datetime.now(timezone.utc).isoformat(),
        per_set_files=len(per_set), files={str(p.relative_to(target)): sha256(p) for p in files}, snapshot=snapshot),
        indent=2) + '\n')
    size = sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
    print(f'{name}: {len(files)} files, {len(per_set)} per-set records, {size / 2**20:.1f} MiB')


def main():
    names = sys.argv[1:]
    unknown = [n for n in names if n not in STUDIES]
    if not names or unknown:
        raise SystemExit(f'Usage: export_results.py <study> ...; unknown {unknown}; known {list(STUDIES)}')
    for name in names:
        export(name)
    (RESULTS / 'environment.json').write_text(json.dumps(environment(), indent=2) + '\n')


if __name__ == '__main__':
    main()
