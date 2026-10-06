"""Prune and restore the rebuildable build outputs of prepared workloads in run output directories.

A prepared directory (chaser.periodic.build.prepare) records the SHA-256 of every input and
output in manifest.json. Its executables and objects (build/*.exe, build/**/*.o) take about
nine tenths of a run output, and rebuilding them in the same directory with the same RTEMS
toolchain gives byte-identical files, so they can be deleted and restored on demand.
Everything else (sources, plans, layout, build.log, waf state, raw run logs, measurements)
stays. dataset.load_batch hashes the executables, so restore a run output before re-reading
its raw logs (summarize stages, period-distribution/control.py).

  status   count prepared dirs per state: complete (every manifest file matches), pruned
           (only the executables and objects are missing, the rest matches), copied
           (complete, but waf was configured in another directory: a calibration folder
           copied with cp -a cannot be rebuilt where it is), other
  prune    delete the executables and objects of complete dirs and append the deleted
           list to <output>/pruned-builds.jsonl; copied dirs are kept as they are; any
           other state stops before deleting
  restore  rebuild pruned dirs in place ('waf build', log kept out of build.log), after
           checking the manifest's tool hashes, then require every manifest file to match
Usage: python3 prepared_builds.py {status,prune,restore} <run output dir> ... [--workers N]
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def find_prepared(roots) -> list[Path]:
    return sorted(p.parent for root in roots for p in Path(root).rglob('prepared/manifest.json'))


def manifest(prepared: Path) -> dict:
    return json.loads((prepared / 'manifest.json').read_text())


def build_outputs(files: dict) -> list[str]:
    return [name for name in files if name.startswith('build/') and name.endswith(('.exe', '.o'))]


def mismatches(prepared: Path, files: dict) -> tuple[list[str], list[str]]:
    """(missing, changed) manifest files."""
    missing, changed = [], []
    for name, expected in files.items():
        path = prepared / name
        if not path.exists():
            missing.append(name)
        elif sha256(path) != expected:
            changed.append(name)
    return missing, changed


def configured_here(prepared: Path) -> bool:
    """waf records its project directory as top_dir; a moved or copied folder does not rebuild."""
    lock = prepared / '.lock-waf_linux_build'
    if not lock.exists():
        return False
    match = re.search(r"^top_dir = '(.*)'$", lock.read_text(errors='replace'), flags=re.M)
    return bool(match) and Path(match.group(1)) == prepared.resolve()


def status(prepared: Path) -> str:
    files = manifest(prepared)['files']
    missing, changed = mismatches(prepared, files)
    if not missing and not changed:
        return 'complete' if configured_here(prepared) else 'copied'
    if not changed and set(missing) == set(build_outputs(files)):
        return 'pruned'
    return 'other'


def prune(prepared: Path) -> int:
    files = manifest(prepared)['files']
    if not configured_here(prepared):
        raise ValueError(f'{prepared}: configured in another directory, cannot be rebuilt here; nothing deleted')
    missing, changed = mismatches(prepared, files)
    if missing or changed:
        raise ValueError(f'{prepared}: not intact (missing {missing[:3]}, changed {changed[:3]}); nothing deleted')
    freed = 0
    for name in build_outputs(files):
        freed += (prepared / name).stat().st_size
        (prepared / name).unlink()
    return freed


def restore(prepared: Path) -> bool:
    """Rebuild a pruned dir; False if it was already complete."""
    m = manifest(prepared)
    state = status(prepared)
    if state == 'complete':
        return False
    if state != 'pruned' or not configured_here(prepared):
        raise RuntimeError(f'{prepared}: state {state}, only pruned dirs configured here are restored')
    changed_tools = [tool for tool, expected in m['tools'].items()
                     if not Path(tool).exists() or sha256(Path(tool)) != expected]
    if changed_tools:
        raise RuntimeError(f'{prepared}: recorded tool changed or missing: {changed_tools}')
    result = subprocess.run([m['build_command'][0], 'waf', 'build', '-v'], cwd=prepared,
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{prepared}: waf build failed: {result.stdout[-2000:]}{result.stderr[-2000:]}')
    missing, changed = mismatches(prepared, m['files'])
    if missing or changed:
        raise RuntimeError(f'{prepared}: rebuild differs from the manifest: missing {missing}, changed {changed}')
    return True


def output_root(prepared: Path, roots: list[Path]) -> Path:
    return next(root for root in roots if prepared.is_relative_to(root))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('status', 'prune', 'restore'))
    parser.add_argument('outputs', type=Path, nargs='+')
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    roots = [p.resolve() for p in args.outputs]
    prepared = find_prepared(roots)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        states = dict(zip(prepared, pool.map(status, prepared)))
    for root in roots:
        counts = {s: sum(1 for p, v in states.items() if v == s and p.is_relative_to(root))
                  for s in ('complete', 'pruned', 'copied', 'other')}
        print(f'{root.name}: {counts}')
    if args.action == 'status':
        return
    if args.action == 'prune':
        other = [p for p, s in states.items() if s == 'other']
        if other:
            raise SystemExit(f'{len(other)} prepared dirs are neither complete nor pruned, e.g. {other[:3]}; nothing deleted')
        todo = [p for p, s in states.items() if s == 'complete']
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            freed = dict(zip(todo, pool.map(prune, todo)))
        stamp = datetime.now(timezone.utc).isoformat()
        for root in roots:
            mine = {p: b for p, b in freed.items() if p.is_relative_to(root)}
            if mine:
                with (root / 'pruned-builds.jsonl').open('a') as log:
                    log.write(json.dumps(dict(pruned_utc=stamp, prepared_dirs=len(mine), bytes=sum(mine.values()),
                                              dirs=sorted(str(p.relative_to(root)) for p in mine))) + '\n')
        print(f'pruned {len(freed)} prepared dirs, freed {sum(freed.values()) / 2**30:.1f} GiB')
        return
    other = [p for p, s in states.items() if s == 'other']
    if other:
        raise SystemExit(f'{len(other)} prepared dirs are neither complete nor pruned, e.g. {other[:3]}')
    todo = [p for p, s in states.items() if s == 'pruned']
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rebuilt = list(pool.map(restore, todo))
    print(f'restored {sum(rebuilt)} prepared dirs; every manifest file matches')


if __name__ == '__main__':
    main()
