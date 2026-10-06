# 스케줄링 아키텍처 비교 실험 (G / C / C₂ / P) — 재현 스크립트

laysim(GR740)에서 Global, Clustered (1+3), Clustered (1+1+2), Partitioned EDF의
TET/TAT 격차가 task set 구성에 따라 어떻게 달라지는지 측정한 실험 모음이다.
실험별 개요·목적·변인·재현 방법은 [EXPERIMENTS.md](EXPERIMENTS.md)에 있다.
이 디렉터리에는 스크립트와 작은 결과 묶음(`results/`)만 둔다. 빌드·원시 run 로그는
저장소 밖 `.cache/`에 있다(아래 "결과 위치").

실험 목록(1–13, 16–26)과 실험별 스크립트·출력(`.cache/`)·결과 묶음(`results/`)의 대응은
[EXPERIMENTS.md](EXPERIMENTS.md) 맨 위 표에 있다.

`figures/`는 결과 그림 스크립트, `supervisors/`는 실제로 쓴 실행 순서(셸)다.
`c2-topology.patch`는 C₂ (0,1,2,2) 토폴로지 추가 패치, `cls-bimodal/padding.patch`는
hot-cold 패턴에 load당·sweep당 레지스터 패딩(`pad_rounds`, `pad_tail`)을 추가하는 패치다.

## 재현 환경

결과를 수치까지 같게 재현하려면 아래 도구가 같아야 한다. laysim은 결정적이지만
run 기록에 simulator 해시가 남지 않으므로 바이너리를 해시로 확인한다.
해시 전체는 `results/environment.json`, RTEMS 라이브러리 해시는 각 prepared `manifest.json`에 있다.

| 도구 | 이 실험의 버전 |
|---|---|
| laysim GR740 | `/opt/laysim-gr740/laysim-gr740-cli`(2026-02-10 배포), sha256 `191c6a94b579d285…`. `license.dat` 필요 |
| X 디스플레이 | laysim이 접속할 `DISPLAY`(이 환경: `165.246.44.80:90.0`) |
| RTEMS 6 SDK | `/opt/rtems/6`, sparc-rtems6-gcc 13.3.0(RSB b1aec32, Newlib 1b3dcfd), `/opt/src/rtems/waf` |
| LLVM | clang-14 / opt-14(Ubuntu 14.0.0-1ubuntu1.1) |
| YARDA(실험 1–4) | `OBC-SIM/Yet-Another-Reuse-Distance-Analyzer` `feat/cpp-backend` a058a454 → `.cache/yarda-a058a454-build`(공유 빌드 폴더 `rtems/baseline/build/yarda`의 빌드를 2026-10-03에 복사해 고정, 해시 동일) |
| YARDA(CLS 양극단) | 같은 저장소 374b2c9 + frontend `Access-Pattern-Extractor` 2670c6e → `.cache/yarda-374b2c9-build` |
| Python | 3.10.12, numpy 2.2.6, scipy 1.15.3, matplotlib 3.10.9 |

YARDA 빌드: `cmake -S <YARDA> -B <빌드 폴더> -DCMAKE_BUILD_TYPE=Release -DLLVM_DIR=/usr/lib/llvm-14/cmake && cmake --build <빌드 폴더> -j`.

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
mkdir $B-c2/rtems/baseline/build && ln -s /workspace/experiments/chaser/.cache/yarda-a058a454-build $B-c2/rtems/baseline/build/yarda
```

c2의 YARDA는 a058a454 빌드다. 원래는 사본의 `rtems/baseline/build`가 저장소의 공유 빌드 폴더를
가리켰다. 그 폴더는 다른 작업이 YARDA를 새로 빌드하면 바뀌므로, 2026-10-03에 빌드 폴더를 복사해 고정했다.
복사본의 `yarda_cpp`(`dc482959…`)와 `libMemoryAccessPatterns.so`(`2e72346a…`)는 원본과 같고,
고정본으로 실험 3의 한 경우를 다시 분석했을 때 CLS·CLP가 저장된 `cls.json`과 같았다.
고정본이 없으면 YARDA 저장소를 a058a454로 checkout한 뒤 위 빌드 명령으로 만든다.

실험 5–26(22절 제외)은 c2 사본에 패딩 패치를 더하고, IR 명령어 카운트가 있는 YARDA
(`feat/cpp-backend` 374b2c9, frontend 2670c6e)를 별도 빌드해 연결한 **c3 사본**을 쓴다.

```sh
Y=/workspace/experiments/chaser/.cache/yarda-374b2c9-build
cmake -S /workspace/Yet-Another-Reuse-Distance-Analyzer -B $Y -DCMAKE_BUILD_TYPE=Release -DLLVM_DIR=/usr/lib/llvm-14/cmake && cmake --build $Y -j 32
cp -a $B-c2 $B-c3 && rm $B-c3/rtems/baseline/build/yarda && ln -s $Y $B-c3/rtems/baseline/build/yarda
patch -p1 -d $B-c3 < artifacts/periodic/scheduler-comparison-v1/cls-bimodal/padding.patch
```

모든 명령은 `PYTHONPATH=<사본>`으로, 사본 디렉터리를 현재 디렉터리로 두고 실행한다
(실험 1–4·22는 c2, 나머지는 c3).
`python3 -m pytest`를 저장소 루트에서 실행하면 HEAD의 `chaser`가 import된다.

## 테스트

```sh
C=/workspace/experiments/chaser/.cache/period-distribution-code-4d03b93-c2
R=/workspace/experiments/chaser/artifacts/periodic/scheduler-comparison-v1
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/period-distribution $R/period-distribution
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cls-distribution $R/cls-distribution
cd $C && PYTHONPATH=$C python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cache-affinity $R/cache-affinity
C3=/workspace/experiments/chaser/.cache/period-distribution-code-4d03b93-c3
cd $C3 && PYTHONPATH=$C3 python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cls-bimodal $R/cls-bimodal
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
- CLS 양극단: `bi_calibrate.py measure|fit --output O/calibration`(O2 job 시간 모델, 검증 오차 2% 게이트) →
  `bi_run.py prepare|isolated|pilot|full|summarize|stats --output O`
  (prepare가 task마다 yarda_cpp CLS를 설계식과 대조, isolated가 서로 다른 수준의 U를 3% 게이트)

`--output`은 항상 지정한다(스크립트의 기본 출력 경로는 `.cache/configs/…`에서 실행할 때 기준).
같은 output으로 다시 실행하면 완료된 run은 건너뛰고, run header가 없는 run은
`*.aborted-N`으로 옮긴 뒤 다시 돌린다. 동시 laysim은 최대 84개, 시작 간격 1초.

## 결과 묶음(`results/`)

`python3 export_results.py <실험> ...`이 `.cache` 출력에서 설계 입력(보정표, set별 설정)과
결과(results.jsonl, 통계, 대조 측정, 그림 PNG·CSV)만 `results/<실험>/`로 복사한다.
실험 이름은 `export_results.py`의 `STUDIES`이며, EXPERIMENTS.md 맨 위 표의 마지막 열과 같다.
사용법은 [EXPERIMENTS.md](EXPERIMENTS.md) 15절.

## 결과 위치(버전 관리 안 함)

실험별 출력 폴더는 EXPERIMENTS.md 맨 위 표의 "출력" 열이다. 폐기한 설계의 목록과 이유는
EXPERIMENTS.md 14절에 있다. 그 출력 일부와 빌드 폴더의 waf 라이브러리 사본은 2026-10-05에 지웠다
(`.cache/cleanup-2026-10-05.log`).
각 output의 `protocol.json`에 설계 파라미터, 빌드 manifest 해시, 당시 스크립트 해시가 있다.

## 빌드 산출물 정리와 복구

실험 출력의 약 9할은 준비한 빌드의 실행 파일과 목적 파일(`prepared/build/*.exe`, `*.o`)이다.
같은 자리에서 같은 RTEMS 툴체인으로 다시 빌드하면 바이트 단위로 같은 파일이 나오므로,
`prepared_builds.py`로 지우고 필요할 때 복구한다. 소스, 계획, layout, `build.log`, waf 상태,
원시 run 로그와 측정값은 지우지 않는다.

```sh
R=/workspace/experiments/chaser/artifacts/periodic/scheduler-comparison-v1
python3 $R/prepared_builds.py status  <출력 폴더> ...   # complete / pruned / other 개수
python3 $R/prepared_builds.py prune   <출력 폴더> ...   # complete인 폴더의 .exe·.o 삭제, <출력>/pruned-builds.jsonl에 기록
python3 $R/prepared_builds.py restore <출력 폴더> ...   # manifest의 도구 해시 확인 → waf build → 모든 manifest 파일 해시 확인
python3 -m pytest -q -p no:cacheprovider --rootdir=$R $R/test_prepared_builds.py
```

`dataset.load_batch`는 실행 파일 해시를 확인한다. 그래서 원시 로그를 다시 읽는 단계
(각 실행기의 `summarize`·`full`·`stats` 전 집계, 실험 2의 `control.py`가 읽는 실험 1 출력)를
돌리기 전에 해당 출력 폴더를 `restore`한다. 결과 묶음, 통계, 그림을 보는 데는 복구가 필요 없다.
복구는 같은 절대 경로와 manifest에 기록된 툴체인(`/opt/rtems/6`) 해시가 필요하다.

## 해석 시 주의

- TAT = release cohort별 (첫 시작 → 마지막 완료) span의 합이며 일반 turnaround time이 아니다.
- laysim은 결정적이므로 통계 단위는 무작위 task set이다(셀당 20개, Wilcoxon + Holm).
- CLS는 배열 접근의 적중 비율만 담는다. 접근 빈도, 스택 접근(GCC -O0), write-back은 제외된다.
- CLS 양극단 v1(주기 20 ms)에서 트래픽 그대로인 낮은 CLS task는 공동 실행 시 job CPU가 단독 대비
  최대 2.75배였다(16개 모두 낮은 CLS일 때). 그래서 v2는 같은 2.5 ms job을 주기 40 ms로 돌린다.
- CLS 양극단의 "트래픽 맞춤"은 낮은 모드 task의 job당 L1 miss 수를 높은 모드 중심과 맞추고
  남는 시간을 레지스터 패딩으로 채운 조건이다. IR 명령어 수는 clang -O0 + mem2reg IR 기준이라
  O2 실행 명령어 수와 다르다.
