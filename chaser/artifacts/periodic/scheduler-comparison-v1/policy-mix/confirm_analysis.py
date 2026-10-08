"""Experiment 44's pre-registered analysis: the frozen pre-run check on the confirmatory sets.

Joins each confirm-* output's results.jsonl (CHASER p_racgb, G4 g, C1+3 c, C1+1+2 c2) with its decisions.json and
evaluates (EXPERIMENTS.md 44):
  H1  AUC of the RF's CHASER probability above the static cache-demand rule D (set bootstrap, two-sided p)
  H2  false-accept rate among the RF's accepted sets <= 2 % with a one-sided 95 % Clopper-Pearson bound <= 5 %
  H3  more successful sets with the RF than with the static D + M rule (exact McNemar)
  H4  among the RF's Global/Clustered choices, saved sets against wrong switches (exact binomial, secondary)
H1 and H3 are Holm-corrected. Sets with any run that did not start or failed otherwise are left out and counted.
Experiment 45 judges its real-kernel output with the same code (--outputs real-kernels-v1).
Usage: python3 confirm_analysis.py --cache <.cache dir> --dest <dir> [--outputs <output> ...]
"""

import argparse
import json
from pathlib import Path
from statistics import median

import numpy as np
from scipy import stats as scipy_stats

from period_swap_analysis import primary
import rf_devcheck as rd

OUTPUTS = ('confirm-small-v1', 'confirm-big-v1', 'confirm-mem-v1')
RUN_KEYS = {'ra-cgb': 'p_racgb', 'g': 'g', 'c13': 'c', 'c112': 'c2'}
BOOTSTRAP, BOOTSTRAP_SEED = 2000, 20264400
FALSE_ACCEPT_MAX, FALSE_ACCEPT_BOUND = 0.02, 0.05


def outcome(accepted: bool, chosen, met: dict) -> str:
    if accepted:
        return 'success' if met[chosen] else 'false_accept'
    return 'false_reject' if any(met.values()) else 'true_reject'


def sets(cache: Path, outputs=OUTPUTS) -> tuple[list[dict], dict]:
    out, excluded = [], {}
    for name in outputs:
        rows = [json.loads(l) for l in (cache / name / 'results.jsonl').read_text().splitlines()]
        decisions = json.loads((cache / name / 'decisions.json').read_text())['cases']
        for r in rows:
            label = f"{r['heaviness']}/u{round(r['load'] * 100):03d}/s{r['set_id']:02d}"
            states = {c: r[k]['state'] for c, k in RUN_KEYS.items()}
            if any(s not in ('ok', 'deadline') for s in states.values()):
                excluded[name] = excluded.get(name, 0) + 1
                continue
            d = decisions[label]
            met = {c: s == 'ok' for c, s in states.items()}
            rf_accept = d['status'] in ('P', 'fallback_gc')
            rf_choice = 'ra-cgb' if d['status'] == 'P' else d['choice']
            out.append(dict(design=name, label=label, load=r['load'], met=met, status=d['status'], choice=rf_choice,
                            p_chaser=d['probabilities'].get('ra-cgb'), cache_demand=d['cache_demand'],
                            occupancy=d['occupancy'], decide_seconds=d['decide_seconds'],
                            rf=outcome(rf_accept, rf_choice, met),
                            static=outcome(d['static_rule'] == 'P', 'ra-cgb', met),
                            always=outcome(True, 'ra-cgb', met)))
    return out, excluded


def auc_difference(y, a, b, reps=BOOTSTRAP, seed=BOOTSTRAP_SEED) -> dict:
    """AUC(a) - AUC(b) for label y, with a set bootstrap 95 % interval and two-sided p."""
    y, a, b = np.asarray(y), np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    point = rd.auc(list(y), list(a)) - rd.auc(list(y), list(b))
    rng, diffs = np.random.default_rng(seed), []
    while len(diffs) < reps:
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            diffs.append(rd.auc(list(y[i]), list(a[i])) - rd.auc(list(y[i]), list(b[i])))
    diffs = np.array(diffs)
    return dict(auc_a=rd.auc(list(y), list(a)), auc_b=rd.auc(list(y), list(b)), difference=point,
                low=float(np.quantile(diffs, 0.025)), high=float(np.quantile(diffs, 0.975)),
                p=float(min(1.0, 2 * min((diffs <= 0).mean(), (diffs >= 0).mean()))))


def false_accept_check(n_accepted: int, false_accepts: int) -> dict:
    rate = false_accepts / n_accepted if n_accepted else 0.0
    bound = float(scipy_stats.beta.ppf(0.95, false_accepts + 1, n_accepted - false_accepts)) if n_accepted else 1.0
    return dict(accepted=n_accepted, false_accepts=false_accepts, rate=rate, upper_95=bound,
                holds=rate <= FALSE_ACCEPT_MAX and bound <= FALSE_ACCEPT_BOUND)


def mcnemar_success(records, a='rf', b='static') -> dict:
    only_a = sum(r[a] == 'success' and r[b] != 'success' for r in records)
    only_b = sum(r[b] == 'success' and r[a] != 'success' for r in records)
    p = float(scipy_stats.binomtest(min(only_a, only_b), only_a + only_b).pvalue) if only_a + only_b else 1.0
    return dict(only_a=only_a, only_b=only_b, p=p, direction_holds=only_a > only_b)


def gc_switches(records) -> dict:
    gc = [r for r in records if r['status'] == 'fallback_gc']
    saved = sum((not r['met']['ra-cgb']) and r['met'][r['choice']] for r in gc)
    wrong = sum(r['met']['ra-cgb'] and not r['met'][r['choice']] for r in gc)
    p = float(scipy_stats.binomtest(saved, saved + wrong).pvalue) if saved + wrong else 1.0
    return dict(switched=len(gc), saved=saved, wrong_switch=wrong, p=p)


def tally(records) -> dict:
    out = {}
    for method in ('rf', 'static', 'always'):
        out[method] = {k: sum(r[method] == k for r in records) for k in ('success', 'false_accept', 'false_reject', 'true_reject')}
    out['sets'] = len(records)
    out['chaser_met'] = sum(r['met']['ra-cgb'] for r in records)
    out['any_met'] = sum(any(r['met'].values()) for r in records)
    out['status'] = {s: sum(r['status'] == s for r in records) for s in ('P', 'fallback_gc', 'rejected', 'deferred')}
    return out


def analyze(records) -> dict:
    h = [r for r in records if r['p_chaser'] is not None]
    y = [int(r['met']['ra-cgb']) for r in h]
    h1 = auc_difference(y, [r['p_chaser'] for r in h], [-r['cache_demand'] for r in h])
    h1_dm = auc_difference(y, [r['p_chaser'] for r in h], [-r['occupancy'] for r in h])
    accepted = [r for r in records if r['rf'] in ('success', 'false_accept')]
    h2 = false_accept_check(len(accepted), sum(r['rf'] == 'false_accept' for r in accepted))
    h3 = mcnemar_success(records)
    tests = primary({'H1': dict(h1, p=h1['p']), 'H3': dict(h3)})
    h1.update(holm_p=tests['H1']['holm_p'], supported=tests['H1']['holm_p'] < 0.05 and h1['difference'] > 0)
    h3.update(holm_p=tests['H3']['holm_p'], supported=tests['H3']['holm_p'] < 0.05 and h3['direction_holds'])
    groups = {}
    for r in records:
        groups.setdefault(r['design'], []).append(r)
        groups.setdefault(f"{r['design']} {r['load']}", []).append(r)
    seconds = [r['decide_seconds'] for r in records]
    return dict(sets=len(records), h1=h1, h1_vs_occupancy=h1_dm, h2=h2, h3=h3, h4=gc_switches(records),
                rf_main_supported=h1['supported'] and h3['supported'] and h2['holds'], overall=tally(records),
                groups={k: tally(v) for k, v in groups.items()},
                decide_seconds=dict(median=median(seconds), max=max(seconds)))


def markdown(result, excluded) -> str:
    h1, h2, h3, h4 = (result[k] for k in ('h1', 'h2', 'h3', 'h4'))
    d = result['h1_vs_occupancy']
    lines = ['# Confirming the pre-run check (pre-registered; experiment 44 or 45)', '',
             f"{result['sets']} sets judged; left out for a failed run: {excluded or 'none'}", '',
             '## Hypotheses', '',
             f"- **H1** AUC for CHASER meeting every deadline: RF {h1['auc_a']:.3f} vs D {h1['auc_b']:.3f}, difference "
             f"{h1['difference']:+.3f} (95 % {h1['low']:+.3f}..{h1['high']:+.3f}), p {h1['p']:.4f}, Holm {h1['holm_p']:.4f} -> "
             f"**{'supported' if h1['supported'] else 'not supported'}**",
             f"  - reported: RF vs D + M {d['difference']:+.3f} (95 % {d['low']:+.3f}..{d['high']:+.3f}), AUC D + M {d['auc_b']:.3f}",
             f"- **H2** false accepts {h2['false_accepts']} of {h2['accepted']} accepted ({h2['rate']:.1%}, one-sided 95 % bound "
             f"{h2['upper_95']:.1%}) -> **{'met' if h2['holds'] else 'not met'}**",
             f"- **H3** successful sets only with RF {h3['only_a']}, only with D + M {h3['only_b']}, McNemar p {h3['p']:.4f}, "
             f"Holm {h3['holm_p']:.4f} -> **{'supported' if h3['supported'] else 'not supported'}**",
             f"- **H4** (secondary) Global/Clustered choices {h4['switched']}: saved {h4['saved']}, wrong switches "
             f"{h4['wrong_switch']}, p {h4['p']:.4f}",
             f"- RF as the main method (H1, H3 supported and H2 met): **{result['rf_main_supported']}**", '',
             '## Outcomes (success / false accept / false reject / true reject)', '',
             '| group | sets | CHASER met | any config met | RF | static D + M | always CHASER | RF status P / G-C / rejected / deferred |',
             '|---|---:|---:|---:|---|---|---|---|']
    fmt = lambda t: f"{t['success']} / {t['false_accept']} / {t['false_reject']} / {t['true_reject']}"
    for name, t in [('all', result['overall'])] + list(result['groups'].items()):
        s = t['status']
        lines.append(f"| {name} | {t['sets']} | {t['chaser_met']} | {t['any_met']} | {fmt(t['rf'])} | {fmt(t['static'])} | "
                     f"{fmt(t['always'])} | {s['P']} / {s['fallback_gc']} / {s['rejected']} / {s['deferred']} |")
    lines += ['', f"Decision time per set: median {result['decide_seconds']['median']:.2f} s, max {result['decide_seconds']['max']:.2f} s."]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--outputs', nargs='+', default=list(OUTPUTS), help='outputs to judge (default: experiment 44)')
    args = parser.parse_args()
    records, excluded = sets(args.cache.resolve(), args.outputs)
    result = dict(analyze(records), excluded=excluded)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'confirm.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'confirm.md').write_text(markdown(result, excluded))
    print('wrote', args.dest / 'confirm.md')


if __name__ == '__main__':
    main()
