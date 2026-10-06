"""Task-count view of the 12-20 task rerun of experiments 1 and 2 (tc_run.py outputs).

The means scale every period alike, so relative gaps barely move with the mean and the
five means repeat each set: per (set, CV) the gap is averaged over the means first, one
value per set. Gap (X_a - X_b) / X_b on runs that met every deadline; a failed run drops
that set for that pair. Pairs: G, C (1+3), C2 (1+1+2) against the snake P (main run); the
cohort-aware P' against the snake P, and G against P' (control run). Writes
<main>/period-taskcount-analysis.json/md:
  scopes     per CV and scope (all sets, task-count group 12-14 / 15-17 / 18-20, multiple
             of 4 or not): n, median, wins, Wilcoxon (zeros dropped, n >= 6) with Holm
             over every test
  by_count   per CV and task count: median gap (two sets per count, one at CV 0)
Usage: python3 tc_analysis.py --main <main output> --control <control output>
"""

import argparse
import json
from pathlib import Path
import shutil
from statistics import mean, median

from scipy import stats

from stats import holm

METRICS = ('tat_ns', 'tet_ns')
MAIN_PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'))
CONTROL_PAIRS = (('p', 'ps'), ('g', 'p'))
NAMES = dict(g='G', c='C (1+3)', c2='C2 (1+1+2)', p='P', ps='snake P')
GROUPS = (('12-14', range(12, 15)), ('15-17', range(15, 18)), ('18-20', range(18, 21)))
CORES = 4
ALPHA = 0.05


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def set_gaps(rows, a, b, metric):
    """{(set_id, cv): gap averaged over the means}, skipping sets with a failed run."""
    table = {}
    for r in rows:
        key = (r['set_id'], r['cv'])
        if r[a]['status'] != 'ok' or r[b]['status'] != 'ok':
            table[key] = None
        elif table.get(key, []) is not None:
            table.setdefault(key, []).append(r[a][metric] / r[b][metric] - 1)
    return {k: mean(v) for k, v in table.items() if v}


def label(run, a, b):
    if run == 'control':
        return {'p': "P'", 'ps': 'snake P', 'g': 'G'}[a] + ' vs ' + {'p': "P'", 'ps': 'snake P'}[b]
    return f'{NAMES[a]} vs snake P'


def summary(values):
    entry = dict(n=len(values), median=median(values) if values else None,
                 better=sum(v < 0 for v in values), worse=sum(v > 0 for v in values))
    nonzero = [v for v in values if v != 0]
    if len(nonzero) >= 6:
        entry['wilcoxon_p'] = float(stats.wilcoxon(nonzero).pvalue)
    return entry


def markdown(result) -> str:
    lines = ['# Experiments 1-2 with 12-20 tasks: task-count view', '',
             'Gap (X_a - X_b) / X_b per set, averaged over the five means; negative = first is shorter.', '',
             '| metric | pair | CV | scope | n | median | better / worse | Holm p |', '|---|---|---:|---|---:|---:|---|---:|']
    for e in result['scopes']:
        med = f"{e['median'] * 100:+.2f}%" if e['median'] is not None else '-'
        p = f"{e['holm_p']:.3g}" if 'holm_p' in e else '-'
        lines.append(f"| {e['metric']} | {e['pair']} | {e['cv']} | {e['scope']} | {e['n']} | {med} "
                     f"| {e['better']} / {e['worse']} | {p} |")
    counts = sorted({n for e in result['by_count'] for n in e['medians']}, key=int)
    lines += ['', '## Median gap per task count', '', '| metric | pair | CV | ' + ' | '.join(counts) + ' |',
              '|---|---|---:|' + '---:|' * len(counts)]
    for e in result['by_count']:
        lines.append(f"| {e['metric']} | {e['pair']} | {e['cv']} | " + ' | '.join(
            f"{e['medians'][n] * 100:+.1f}%" if n in e['medians'] else '-' for n in counts) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    args = parser.parse_args()
    main_dir, control_dir = args.main.resolve(), args.control.resolve()
    counts = json.loads((main_dir / 'protocol.json').read_text())['task_counts']
    runs = dict(main=(load(main_dir / 'results.jsonl'), MAIN_PAIRS),
                control=(load(control_dir / 'results.jsonl'), CONTROL_PAIRS))
    scopes = [('all', lambda n: True)] + [(g, lambda n, v=v: n in v) for g, v in GROUPS]
    scopes += [('multiple of 4', lambda n: n % CORES == 0), ('not a multiple of 4', lambda n: n % CORES != 0)]
    result = dict(scopes=[], by_count=[])
    for metric in METRICS:
        for run, (rows, pairs) in runs.items():
            for a, b in pairs:
                gaps = set_gaps(rows, a, b, metric)
                for cv in sorted({cv for _, cv in gaps}):
                    at = {s: v for (s, c), v in gaps.items() if c == cv}
                    tag = dict(metric=metric.split('_')[0].upper(), pair=label(run, a, b), cv=cv)
                    for scope, keep in scopes:
                        result['scopes'].append(dict(tag, scope=scope,
                                                     **summary([v for s, v in at.items() if keep(counts[s])])))
                    by_n = {}
                    for s, v in at.items():
                        by_n.setdefault(str(counts[s]), []).append(v)
                    result['by_count'].append(dict(tag, medians={n: median(v) for n, v in by_n.items()}))
    tested = [e for e in result['scopes'] if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    (main_dir / 'period-taskcount-analysis.json').write_text(json.dumps(result, indent=1) + '\n')
    (main_dir / 'period-taskcount-analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), main_dir / 'tc_analysis.py')
    print('wrote', main_dir / 'period-taskcount-analysis.md')


if __name__ == '__main__':
    main()
