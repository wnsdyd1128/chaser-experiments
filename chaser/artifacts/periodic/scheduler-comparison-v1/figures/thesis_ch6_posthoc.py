"""Post hoc base-set statistics behind the thesis chapter 6 text (not pre-registered, computed 2026-10-12).

A base task set is one seed reused across loads (and period CV cells in experiment 27), so the per-case tests of the
pre-registered analyses count dependent cases. These checks summarise per base set first:
- experiment 27: per base set, the median log ratio of TET (RA-CGB against RA and WFD, cases where both met every
  deadline); the number of base sets with a lower TET. TAT against RA: per base set median log ratio, then the
  +-2 % TOST with one-sided Wilcoxon tests over base sets.
- experiment 44: per base set, the number of sets where the RF and the D + M rule succeeded; exact sign test.
- experiments 44 and 45: AUC difference (RF probability against D and D + M) with a bootstrap that resamples base
  sets with all their loads (2,000 resamples, seed 20264400, as the pre-registered case bootstrap).
Reads the result bundles only. Usage: python3 thesis_ch6_posthoc.py <output dir>   (run from scheduler-comparison-v1)
"""
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median
import sys

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'policy-mix'))
import confirm_analysis as ca  # noqa: E402
import rf_devcheck as rd  # noqa: E402

R = HERE / 'results'
REPS, SEED = 2000, 20264400


def tet_tat(design):
    rows = [json.loads(l) for l in (R / design / 'results.jsonl').open()]
    out = {}
    for ref, key in (('RA', 'p_ra'), ('WFD', 'p')):
        tet, tat = defaultdict(list), defaultdict(list)
        for r in rows:
            a, b = r['p_racgb'], r[key]
            if a.get('state') == 'ok' and b.get('state') == 'ok':
                tet[r['set_id']].append(math.log(a['tet_ns'] / b['tet_ns']))
                tat[r['set_id']].append(math.log(a['tat_ns'] / b['tat_ns']))
        meds = [median(v) for v in tet.values()]
        entry = dict(base_sets=len(meds), tet_lower=sum(m < 0 for m in meds))
        if ref == 'RA':
            t = [median(v) for v in tat.values()]
            lo = stats.wilcoxon([m - math.log(0.98) for m in t], alternative='greater').pvalue
            hi = stats.wilcoxon([m - math.log(1.02) for m in t], alternative='less').pvalue
            entry.update(tat_median_ratio=math.exp(median(t)), tat_tost_p=float(max(lo, hi)),
                         tat_equivalent=bool(max(lo, hi) < 0.05))
        out[ref] = entry
    return out


def base(r):
    return (r['design'], r['label'].split('/')[-1])


def sign_test(records):
    by = defaultdict(lambda: [0, 0])
    for r in records:
        by[base(r)][0] += r['rf'] == 'success'
        by[base(r)][1] += r['static'] == 'success'
    more = sum(a > b for a, b in by.values())
    less = sum(b > a for a, b in by.values())
    return dict(base_sets=len(by), rf_more=more, static_more=less, ties=len(by) - more - less,
                p=float(stats.binomtest(min(more, less), more + less).pvalue))


def cluster_auc(records, other):
    groups = defaultdict(list)
    for r in records:
        if r['p_chaser'] is not None:
            groups[base(r)].append(r)
    keys = list(groups)

    def diff(rs):
        y = [int(r['met']['ra-cgb']) for r in rs]
        return rd.auc(y, [r['p_chaser'] for r in rs]) - rd.auc(y, [-r[other] for r in rs])
    rng, diffs = np.random.default_rng(SEED), []
    while len(diffs) < REPS:
        rs = [r for k in rng.integers(0, len(keys), len(keys)) for r in groups[keys[k]]]
        if 0 < sum(r['met']['ra-cgb'] for r in rs) < len(rs):
            diffs.append(diff(rs))
    return dict(base_sets=len(keys), difference=diff([r for g in groups.values() for r in g]),
                low=float(np.quantile(diffs, 0.025)), high=float(np.quantile(diffs, 0.975)))


def main():
    out = Path(sys.argv[1]).resolve()
    e44, _ = ca.sets(R, ('confirm-small', 'confirm-big', 'confirm-mem'))
    e45, _ = ca.sets(R, ('real-kernels',))
    result = dict(experiment_27={t: tet_tat(f'deadline-{t}') for t in ('small', 'big')},
                  experiment_44_sign_test=sign_test(e44),
                  auc_cluster_bootstrap={name: {o: cluster_auc(rs, o) for o in ('cache_demand', 'occupancy')}
                                         for name, rs in (('experiment 44', e44), ('experiment 45', e45))})
    (out / 'posthoc.json').write_text(json.dumps(result, indent=1) + '\n')
    lines = ['# 6장 본문의 기본 집합 단위 사후 분석', '',
             '`figures/thesis_ch6_posthoc.py`가 결과 묶음에서 계산한다. 사전 등록 판정이 아니다.', '',
             '## 실험 27: RA-CGB의 TET·TAT (두 배치가 모두 마감을 지킨 사례, 기본 집합별 중앙 로그 비)', '',
             '| 유형 | 기준 | 기본 집합 | TET가 작은 집합 | TAT 중앙 비 | TAT ±2% TOST p |', '|---|---|---:|---:|---:|---:|']
    for t, label in (('small', '32 KiB'), ('big', '768 KiB')):
        for ref, e in result['experiment_27'][t].items():
            tat = (f"{e['tat_median_ratio']:.4f}", f"{e['tat_tost_p']:.3g}") if ref == 'RA' else ('-', '-')
            lines.append(f"| {label} | {ref} | {e['base_sets']} | {e['tet_lower']} | {tat[0]} | {tat[1]} |")
    s = result['experiment_44_sign_test']
    lines += ['', '## 실험 44: RF 대 D + M 규칙의 성공 set 수 (기본 집합별)', '',
              f"기본 집합 {s['base_sets']}개: RF가 많은 집합 {s['rf_more']}, 규칙이 많은 집합 {s['static_more']}, 같은 집합 {s['ties']}. "
              f"정확 부호검정 p = {s['p']:.3g}.", '',
              f'## AUC 차이: 기본 집합을 부하째 재표집한 bootstrap ({REPS}회, 시드 {SEED})', '',
              '| 실험 | 비교 | 기본 집합 | 차이 | 95% 구간 |', '|---|---|---:|---:|---|']
    for name, entry in result['auc_cluster_bootstrap'].items():
        for other, label in (('cache_demand', 'RF − D'), ('occupancy', 'RF − (D + M)')):
            e = entry[other]
            lines.append(f"| {name} | {label} | {e['base_sets']} | {e['difference']:.3f} | [{e['low']:.3f}, {e['high']:.3f}] |")
    (out / 'posthoc.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
