"""Build and evaluate the controlled, load-only S1 suite with preserved artifacts."""

import argparse
import json
from pathlib import Path
import resource
import subprocess
from time import perf_counter

from chaser.s1_suite import run_suite
from chaser.s1_workloads import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, dest='output_dir')
    parser.add_argument('--cases', nargs='+', choices=[c['id'] for c in cases()], dest='case_ids')
    parser.add_argument('--sweeps', type=int, default=3)
    parser.add_argument('--max-references', type=int, default=250000)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    start = perf_counter()
    try:
        report = run_suite(**vars(args))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f'{error}\n')
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    (args.output_dir / 'resources.json').write_text(json.dumps({
        'wall_seconds': perf_counter() - start,
        'max_process_rss_kib': max(own.ru_maxrss, children.ru_maxrss),
        'scope': 'Linux maximum individual-process high-water RSS; not concurrent sum or analyzer-only',
        'artifact_bytes': sum(p.stat().st_size for p in args.output_dir.rglob('*') if p.is_file())
    }, indent=2) + '\n')
    print(f"{report['status']}: {args.output_dir / 'suite.json'}")
    if report['status'] != 'ok':
        parser.exit(1)


if __name__ == '__main__':
    main()
