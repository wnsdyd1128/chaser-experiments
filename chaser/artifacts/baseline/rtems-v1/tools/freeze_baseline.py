"""Snapshot the verified standalone RTEMS runs without overwriting a baseline."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CASES = ('packed', 'spread', 'conflict')


def snapshot(output):
    files = ['rtems/baseline/' + name for name in
             ('init.c', 'workload.c', 'workload.h', 'Makefile', 'cache.yaml',
              'build/workload.ll', 'build/workload_ape.json', 'build/verify.log')]
    files += ['exports/element.rdh.json', 'exports/line.rdh.json',
              'scripts/verify', 'tests/test_rtems_baseline.py',
              'tests/test_freeze_baseline.py', 'tools/freeze_baseline.py']
    element = json.loads((ROOT / 'exports/element.rdh.json').read_bytes())
    if element['granularity'] != 'element':
        raise ValueError('The CAAS baseline requires element RD')
    blocks = {b['name'].split()[0]: b['profile'] for b in element['blocks']}
    results = {}
    for case in CASES:
        elf = f'rtems/baseline/build/{case}.exe'
        log = f'rtems/baseline/build/laysim-{case}.log'
        text = (ROOT / log).read_text()
        rows = re.findall(r'RESULT,case=(\w+),elapsed_ns=(\d+)', text)
        if (len(rows) != 1 or rows[0][0] != case or int(rows[0][1]) <= 0
                or 'CHASER PASS' not in text or '[ RTEMS shutdown ]' not in text
                or '*** FATAL ***' in text or elf not in text):
            raise ValueError(f'Invalid standalone execution log: {case}')
        profile = blocks[f'chaser_{case}']
        reuses = sum(profile['histogram'].values())
        weighted = sum(int(rd) * count for rd, count in profile['histogram'].items())
        results[case] = {'elapsed_ns': int(rows[0][1]), 'reuses': reuses,
                         'cold_misses': profile['cold_misses'], 'weighted_rd_sum': weighted,
                         'mean_rd': weighted / reuses if reuses else None,
                         'ca_caas': reuses / (reuses + weighted) if reuses else None,
                         'command': ['/opt/laysim-gr740/laysim-gr740-cli', '-r', '-core0', elf]}
        files += [elf, log]
    cache = ROOT / 'rtems/baseline/build/yarda/CMakeCache.txt'
    repo = Path(re.search(r'^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)$', cache.read_text(), re.M)[1])
    tools = [ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp',
             repo / 'build-release/libLoopAnnotatedTrace.so',
             Path('/opt/rtems/6/bin/sparc-rtems6-gcc'),
             Path('/opt/laysim-gr740/laysim-gr740-cli')]
    contents = {name: (ROOT / name).read_bytes() for name in sorted(files)}
    manifest = {
        'schema_version': 1, 'results': results,
        'protocol': 'Separate ELF and fresh laysim process per case; one run; no explicit warmup; Init task not pinned.',
        'scope': 'Element Global RD and CAAS formula baseline; timings are smoke observations, not cache counters.',
        'yarda_commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'tool_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tools},
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    snapshot(parser.parse_args().output)
