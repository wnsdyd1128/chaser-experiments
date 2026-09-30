# 스케줄링 아키텍처 비교 실험 (G / C / C₂ / P) — 재현 스크립트

laysim(GR740)에서 Global, Clustered (1+3), Clustered (1+1+2), Partitioned EDF의
TET/TAT 격차가 task set 구성에 따라 어떻게 달라지는지 측정한 실험 모음이다.
이 디렉터리에는 재현에 필요한 스크립트만 둔다. raw·통계·그림은 저장소 밖
`.cache/`에 있다(아래 "결과 위치").

| 실험 | 디렉터리 | 내용 |
|---|---|---|
| 주기 분포 | `period-distribution/` | task별 주기 ~ N(μ, (CV·μ)²), μ ∈ {20,50,80,100,500} ms, CV ∈ {0,.1,.2,.3}, 셀당 20 set |
| release-aware P′ 대조 | `period-distribution/{placement,control}.py` | 같은 set에서 P의 코어 배치만 release cohort 부하 하한 최소화로 변경 |
| CLS 분포 | `cls-distribution/` | 공통 주기 20/100 ms, task별 CLS(yarda_cpp, α=0.5) ~ N(μ, (CV·μ)²), hot-cold workload, P 배치 2종 |
| 캐시 친화성 | `cache-affinity/` | 코어당 작업 집합 {25,50,100,150}% of L1 × job당 sweep {2,8,32}, workload O0/O2 |

`figures/`는 결과 그림 스크립트, `supervisors/`는 실제로 쓴 실행 순서(셸)다.
`c2-topology.patch`는 C₂ (0,1,2,2) 토폴로지 추가 패치다.

## 요구 환경

- GR740 RTEMS 6 SDK(`/opt/rtems/6`), `/opt/src/rtems/waf`, laysim(`tools/rtems_smoke.SIMULATOR`)
- laysim이 접속할 X 디스플레이: `DISPLAY=165.246.44.80:90.0`
- CLS 실험: YARDA 빌드(`rtems/baseline/build/yarda`, `feat/cpp-backend` a058a454로 분석함)
- Python: numpy, scipy, matplotlib

## 코드 기준(중요)

HEAD의 측정 코드는 커밋 `3058321` 이후 schema 없는(legacy) 입력을 거부한다.
이 실험들은 **커밋 `4d03b93`의 코드 + `c2-topology.patch`**로 실행했다.

```sh
cd /workspace/experiments/chaser
B=.cache/period-distribution-code-4d03b93
mkdir -p $B
git ls-tree -r --name-only 4d03b93 -- chaser tools rtems/periodic rtems/baseline/cache.yaml |
  while read -r f; do mkdir -p "$B/$(dirname "$f")"; git show "4d03b93:./$f" > "$B/$f"; done
cp -a $B $B-c2 && (cd .cache && patch -p1 -d period-distribution-code-4d03b93-c2 < ../artifacts/periodic/scheduler-comparison-v1/c2-topology.patch)
ln -s /workspace/experiments/chaser/rtems/baseline/build $B-c2/rtems/baseline/build   # YARDA 사용
```

모든 명령은 `PYTHONPATH=<…-c2 사본>`으로, 사본 디렉터리를 현재 디렉터리로 두고 실행한다.
`python3 -m pytest`를 저장소 루트에서 실행하면 HEAD의 `chaser`가 import된다.

## 테스트

```sh
C=/workspace/experiments/chaser/.cache/period-distribution-code-4d03b93-c2
R=/workspace/experiments/chaser/artifacts/periodic/scheduler-comparison-v1
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/period-distribution $R/period-distribution
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cls-distribution $R/cls-distribution
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cache-affinity $R/cache-affinity
```

`test_c2.py`는 패치 전 사본(`-c2` 접미사 없는 디렉터리)이 있으면 G/C/P 계획이 패치 전과
같은지도 비교한다.

## 실행

`supervisors/*.sh`가 실제 실행 순서다(백그라운드 `setsid nohup`, 로그·PID·exit 파일 기록).
단계와 출력 경로는 스크립트 docstring에 있다. 요약:

- 주기 분포: `run.py prepare|u-check|pilot|full|summarize --output O` → `stats.py O`,
  대조: `control.py prepare|g-check|run|summarize|stats --main O --output O2`,
  중복 제거 민감도: `dedup.py O`
- CLS: `calibrate.py measure|verify|analyze --output O/calibration` →
  `cls_run.py prepare|u-check|pilot|full|stats --output O`
- 캐시 친화성: `aff_run.py prepare [--optimization O2]|isolated|pilot|empty|full|stats --output O`

`--output`은 항상 지정한다(스크립트의 기본 출력 경로는 `.cache/configs/…`에서 실행할 때 기준).
같은 output으로 다시 실행하면 완료된 run은 건너뛰고, run header가 없는 run은
`*.aborted-N`으로 옮긴 뒤 다시 돌린다. 동시 laysim은 최대 84개, 시작 간격 1초.

## 결과 위치(버전 관리 안 함)

| 실험 | output |
|---|---|
| 주기 분포 | `.cache/period-distribution-v2/`(stats.json, stats-dedup.json, figures/) |
| P′ 대조 | `.cache/period-distribution-cohort-v2/` |
| CLS 분포 | `.cache/cls-distribution-v1/`(calibration/, stats-p020/p100.json, figures/) |
| 캐시 친화성 | `.cache/cache-affinity-v2/`(O0), `.cache/cache-affinity-o2-v1/`(O2), 실패한 1 ms 설정 `.cache/cache-affinity-v1/` |

각 output의 `protocol.json`에 설계 파라미터, 빌드 manifest 해시, 당시 스크립트 해시가 있다.

## 해석 시 주의

- TAT = release cohort별 (첫 시작 → 마지막 완료) span의 합이며 일반 turnaround time이 아니다.
- laysim은 결정적이므로 통계 단위는 무작위 task set이다(셀당 20개, Wilcoxon + Holm).
- CLS는 배열 접근의 적중 비율만 담는다. 접근 빈도, 스택 접근(GCC -O0), write-back은 제외된다.
