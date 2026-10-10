"""Experiment 46: the frozen pre-run check (v1, experiment 43) on held-out kernels (2MM, SYRK, TRMM, DOITGEN).

The run was registered to test a policy v2 (v1 + training-domain check + out-of-domain recalibration); v2 was dropped
on 2026-10-08 and its code removed (EXPERIMENTS.md 46). v1's decisions were made in the same run before any measured
run (decisions.json, under compare; kernel_report.v1_records). This reports them with experiment 44's definitions,
which were not pre-registered for v1 on this run: false accepts with the one-sided 95 % Clopper-Pearson bound, AUC of
the RF against D when it is defined, success against the static D + M rule (exact McNemar), Global/Clustered choices
and outcomes per load. Sets with a run that did not start or failed otherwise are left out and counted.
Usage: python3 heldout_analysis.py --cache <.cache dir> --output heldout-kernels-v1 --dest <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import median

import confirm_analysis as ca
from kernel_report import v1_records


def analyze(records) -> dict:
    accepted = [r for r in records if r['rf'] in ('success', 'false_accept')]
    h = [r for r in records if r['p_chaser'] is not None]
    y = [int(r['met']['ra-cgb']) for r in h]
    auc = ca.auc_difference(y, [r['p_chaser'] for r in h], [-r['cache_demand'] for r in h]) if 0 < sum(y) < len(y) else None
    loads = {}
    for r in records:
        loads.setdefault(str(r['load']), []).append(r)
    return dict(sets=len(records), false_accepts=ca.false_accept_check(len(accepted), sum(r['rf'] == 'false_accept' for r in accepted)),
                auc_rf_vs_d=auc, success_vs_static=ca.mcnemar_success(records), gc=ca.gc_switches(records),
                overall=ca.tally(records), loads={k: ca.tally(v) for k, v in sorted(loads.items())},
                decide_seconds=dict(median=median(r['decide_seconds'] for r in records),
                                    max=max(r['decide_seconds'] for r in records)))


def markdown(result, excluded) -> str:
    fa, a, s, gc = result['false_accepts'], result['auc_rf_vs_d'], result['success_vs_static'], result['gc']
    auc = (f"AUC for CHASER meeting every deadline: RF {a['auc_a']:.3f} vs D {a['auc_b']:.3f}, difference {a['difference']:+.3f} "
           f"(95 % {a['low']:+.3f}..{a['high']:+.3f})" if a else
           'AUC for CHASER meeting every deadline: not computable (every judged CHASER run had the same outcome)')
    fmt = lambda t: ' / '.join(str(t[k]) for k in ('success', 'false_accept', 'false_reject', 'true_reject'))
    lines = ['# Experiment 46: the frozen pre-run check (v1) on held-out kernels', '',
             f"{result['sets']} sets judged; left out for a failed run: {excluded or 'none'}", '',
             f"- false accepts {fa['false_accepts']} of {fa['accepted']} accepted ({fa['rate']:.1%}, one-sided 95 % bound {fa['upper_95']:.1%})",
             f'- {auc}',
             f"- successful sets only with v1 {s['only_a']}, only with the static D + M rule {s['only_b']}, exact p {s['p']:.4f}",
             f"- Global/Clustered choices {gc['switched']}: saved {gc['saved']}, wrong switches {gc['wrong_switch']}",
             f"- decision time per set: median {result['decide_seconds']['median']:.2f} s, max {result['decide_seconds']['max']:.2f} s", '',
             '## Outcomes (success / false accept / false reject / true reject)', '',
             '| group | sets | CHASER met | any config met | v1 | static D + M | always CHASER | v1 status P / G-C / rejected / deferred |',
             '|---|---:|---:|---:|---|---|---|---|']
    for name, t in [('all', result['overall'])] + [(f'load {k}', v) for k, v in result['loads'].items()]:
        st = t['status']
        lines.append(f"| {name} | {t['sets']} | {t['chaser_met']} | {t['any_met']} | {fmt(t['rf'])} | {fmt(t['static'])} | "
                     f"{fmt(t['always'])} | {st['P']} / {st['fallback_gc']} / {st['rejected']} / {st['deferred']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', default='heldout-kernels-v1')
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    records, excluded = v1_records(args.cache.resolve(), args.output)
    result = dict(analyze(records), excluded=excluded)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'heldout.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'heldout.md').write_text(markdown(result, excluded))
    print('wrote', args.dest / 'heldout.md')


if __name__ == '__main__':
    main()
