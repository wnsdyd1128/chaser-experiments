# Memory-access-intensive G/C/P 진단 (2026-09-25~27)

변경한 실험 변수·현재 결론·남은 가설은 [실험 점검](EXPERIMENT-AUDIT.md)에,
이후 task/역할 재집계와 O0/O2 대조군은 [SIM 후속 진단](SIM-FOLLOWUP.md)에,
저장된 RTEMS ELF의 보드 실행·로그 검증 절차는
[GR740 HW 검증](../../../rtems/periodic/HARDWARE-VALIDATION.md)에 정리했다.
JSON에서 소스·ELF를 만들고 재실행하는 명령은
[실험 생성·수정·재현 안내](../../../rtems/periodic/EXPERIMENT-GUIDE.md)를 참고한다.

이 실험은 [데이터셋 명세](../../../system-prompt-extraction/plan/DATASET-SPECIFICATION.md)의
load/store 접근량 기준에 맞는 후보에서 G/C/P의 TET·TAT 격차를 확인하는
controlled diagnostic이다. 5/1/1/1 배치에서 관찰한 큰 TAT 차이는 core별 task 수가
불균형한 결과이므로, 공정한 cache representation 비교의 근거로 사용하지 않는다.
입력은 [설정 디렉터리](../../../.cache/configs/periodic-memory-gap/)에,
빌드 snapshot·HARA 분석·시뮬레이터 raw는 `.cache/periodic-memory-gap-v1/`에 있다.
아래 결과를 본 데이터셋의 표본이나 학습 label로 사용하지 않는다.

## 입력과 계측

- 8 task, 4 core, 공통 10 ms period가 기본이다. `paired-pass-8-high-load`와
  성공한 victim/polluter 대응군은 2 ms, 아래 확장 paired-pass는 4/6/8 ms
  period다. 실패한 victim/polluter 원본만 1 ms다.
  모든 짧은 진단은 20 warm-up + 20 measurement round로
  시작했고, 기본 실행은 architecture당 1회·측정 job 160개다.
  `paired-pass-8-skewed`만 architecture당 1회 추가 반복했다.
  정식 길이 입력은 task당 20 warm-up + 200 measurement job이며,
  G/C/P를 각각 1회 실행했다. `sweeps=2`는 한 job 내부의 kernel 반복 수다.
  설정의 `u_repeats=5`는 독립 P-only U 측정용 계획값으로, 이 진단에서
  5회 G/C/P 실행했다는 뜻이 아니다. 확장 paired-pass는 `sweeps=4/8`이다.
- G는 4-core EDF-SMP, C는 1+3 scheduler, P는 4개의 1-core scheduler다.
  `paired-pass-8-skewed`의 명시적 P 배치는 task 수 기준 5/1/1/1이며,
  균형 후보는 2/2/2/2다. C에서도 core 0 task는 1-core scheduler에 남는다.
- `paired-pass-8`와 `paired-pass-8-skewed`는 task source·순서·접근 수·period가
  같고 core 지정만 다르다. 각 task의 고정된 job body는 4,608회 byte load를
  수행하며 768개 cache line(24 KiB)을 참조한다. 공통 kernel 설정은
  `width=8`, `distinct=768`, `stride=32`, `sweeps=2`다. 10 ms period당 접근 수요는
  task당 460,800 line references/s다. 이는 실제 memory bandwidth 측정치가 아니다.
- HARA의 isolated cold-task 분석은 세 ELF의 주소·접근 stream이 같음을 확인했다.
  `window-bank-conflict-8`은 task당 4,608회 load, 64개 고유 line(2 KiB)을
  256 KiB 주소 범위에 걸쳐 접근한다. 주소 범위를 working set 크기로 쓰지 않는다.
- 실행용 G/C/P의 `workload.c`, `init.c`, `probe.c`는 모두
  `sparc-rtems6-gcc -O0 -g`로 컴파일한다. HARA 입력 LLVM IR은 별도로
  `clang-14 -O0 -Xclang -disable-O0-optnone`으로 생성한다.

## 20+20 round 진단 결과

아래 시간은 측정 round의 ns 합을 ms로 환산했다. Spread는 세 값의
`(최대−최소)/최소`이며, 데이터셋 명세의 초기 진단 기준은 5%다.
모든 행에서 G/C/P 각각 `execution_status=ok`, 오류 목록 없음, warm-up 160 job과
측정 160 job이 raw 재파싱에서 일치했다.

| 입력 | 패턴·배치 | TET G/C/P (ms) | TAT G/C/P (ms) | TET spread | TAT spread |
|---|---|---:|---:|---:|---:|
| `candidate-01-short` | 4종 혼합, 2/2/2/2 | 123.428 / 124.756 / 124.525 | 36.069 / 34.346 / 33.981 | 1.08% | 6.14% |
| `candidate-02-short` | window/reuse 혼합, 2/2/2/2 | 108.900 / 109.930 / 109.954 | 29.215 / 28.808 / 28.554 | 0.97% | 2.32% |
| `paired-pass-8` | 동일 `paired-pass`, 2/2/2/2 | 119.429 / 118.792 / 118.821 | 31.459 / 31.078 / 30.730 | 0.54% | 2.37% |
| `paired-pass-8-high-load` | 동일 `paired-pass`, 2/2/2/2·2 ms | 119.196 / 119.143 / 119.102 | 31.386 / 31.141 / 30.869 | 0.08% | 1.67% |
| `window-bank-conflict-8` | 동일 `window-bank`/파라미터, 2/2/2/2 | 199.078 / 199.377 / 199.643 | 51.276 / 51.187 / 51.075 | 0.28% | 0.39% |
| `window-bank-variants-8` | 동일 `window-bank`, cache 변형, 2/2/2/2 | 134.281 / 144.609 / 143.533 | 38.394 / 37.434 / 37.045 | **7.69%** | 3.64% |
| `window-bank-variants-grouped-8` | 같은 변형을 core별로 묶음, 2/2/2/2 | 134.281 / 135.176 / 128.036 | 38.394 / 38.416 / 37.191 | **5.58%** | 3.29% |
| `paired-pass-8-skewed` | 동일 `paired-pass`/파라미터, 5/1/1/1 | 119.429 / 108.272 / 108.192 | 31.459 / 66.985 / 67.049 | **10.39%** | **113.13%** |

동일 파라미터의 완전 동질 task를 2/2/2/2로 배치하면 TET spread는 0.54%,
TAT spread는 2.37%로 모두 초기 진단 기준 5%보다 작았다.
`window-bank-variants-8`은 같은 source 패턴의 L1 중심·LLC 중심 변형을 섞어
TET 격차를 만들었지만 TAT spread는 5% 미만이다.
`paired-pass-8-skewed`는 G의 TAT가 가장 작고, 차선 C와의 margin도 112.93%다.
반대로 TET는 P가 가장 작다. 균형 배치와 skewed 배치의 G 측정값은 정확히 같아,
이 큰 TAT 격차의 직접적인 조작 변수는 P/C에서의 core 배치다.
따라서 이 결과를 cache representation의 우월성으로 해석하지 않는다.
`paired-pass-8-skewed`를 같은 snapshot의 새 simulator 프로세스에서 한 번 더 실행했고,
G/C/P 모두 2/2회 성공했다. 반복한 TET·TAT ns 값은 첫 실행과 정확히 같았다.
Deterministic simulator의 동일값을 독립적인 확률 표본으로 해석하지 않는다.

## 20+200 round 2/2/2/2 균형 배치 확인

`paired-pass-8-balanced-full.json`은 짧은 균형 진단과 task·배치·period가 같고
측정 구간만 200 round로 늘렸다. 짧은 균형 입력 및 5/1/1/1 입력과
`source/workload.c` hash·G/C/P data layout이 같다. G/C/P 모두 exit code 0,
raw 재파싱 `execution_status=ok`, 오류 없음, warm-up 160 job·측정 1,600 job·
200 cohort가 일치했다. Architecture당 독립 실행은 1회다.

| 지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| TET (ms) | 1190.200 | 1190.697 | 1189.172 | 0.13% |
| TAT (ms) | 313.014 | 310.931 | 307.269 | 1.87% |

균형 배치에서는 짧은 진단과 정식 길이 모두 TET·TAT spread가 초기 5% 기준보다
작다. TAT 최선 P와 차선 C의 차이도 P 대비 1.19%다. 따라서 이 동질
`paired-pass` 입력은 유의미한 G/C/P 차이를 보인 후보로 분류하지 않는다.
G의 TET·TAT는 아래 5/1/1/1 입력과 ns 단위까지 같아, skewed 입력의 큰 TAT
차이는 G의 workload 변화가 아니라 C/P의 core 배치 변화에 따른 결과다.

## 동질 paired-pass 태스크 수·sweep 확장

기존 `paired-pass-8-high-load`의 8 task·2 sweep·2 ms 결과를 기준으로
8 task에서 job당 sweep을 2→4→8로 늘리고, 4 sweep에서 task 수를
8→12→16으로 늘린다.
모든 task는 `width=8`, `distinct=768`, `stride=32`를 공유하고
24 KiB working set을 참조한다. 4/8 sweep은 job당 byte load
9,216/18,432회다.

| 입력 | Task 수 | P core별 task 수 | Sweep/job | Period | Warm-up + 측정 |
|---|---:|---|---:|---:|---:|
| `paired-pass-8-high-load` | 8 | 2/2/2/2 | 2 | 2 ms | 20 + 20 |
| `paired-pass-8-sweeps4-balanced-short` | 8 | 2/2/2/2 | 4 | 4 ms | 20 + 20 |
| `paired-pass-8-sweeps8-balanced-short` | 8 | 2/2/2/2 | 8 | 8 ms | 20 + 20 |
| `paired-pass-12-sweeps4-balanced-short` | 12 | 3/3/3/3 | 4 | 6 ms | 20 + 20 |
| `paired-pass-16-sweeps4-balanced-short` | 16 | 4/4/4/4 | 4 | 8 ms | 20 + 20 |

기존 2 ms 입력의 task당 CPU 약 0.75 ms를 바탕으로 4/8 sweep의 CPU를
약 1.5/3 ms로 예상했다. 이 값을 2 ms period에 그대로 넣으면 task 수 증가와
무관하게 과부하가 예상된다. Period를 core당 task 수에 비례해 늘려
예상 core 이용률을 약 75%로 맞췄다. 이는 사전 추정이며 실제 CPU 시간과
deadline·job completeness는 raw로 확인한다. 각 입력 내부의 G/C/P spread를
비교하고, task 수·period·horizon이 다른 입력 사이에서 TET/TAT 합계의
절대값을 직접 비교하지 않는다. 네 추가 입력 모두 G/C/P 계획 생성,
`prepare`, HARA `analyze`를 통과했다.

8-task/4-sweep의 첫 G/C/P 실행은 시뮬레이터 시작 전에 X display 연결
실패로 모두 종료됐다. 실패 raw를 원래 `g/c/p`에 보존하고,
`g-display-retry/c-display-retry/p-display-retry`에서 재실행했다.
12-task와 16-task 실행은 `paired-pass-scaled-supervisor.log`에서 순차로
완료했다. 각 case 내부의 G/C/P는 동시에 실행했다.

12-task/4-sweep은 G/C/P 모두 exit code 0, raw 재파싱
`execution_status=ok`, 오류 없음, warm-up 240 job·측정 240 job·20 cohort가
일치했다. TET G/C/P는 354.760/354.482/354.468 ms (spread 0.08%),
TAT는 91.314/90.688/90.560 ms (spread 0.83%), 전체 run makespan은
238.692/238.650/238.643 ms (spread 0.02%)다. 이 조건에서 규모 확대만으로
5% 격차가 나타나지 않았다.

8-task/4-sweep의 display 재실행도 G/C/P 모두 exit code 0, raw 재파싱
`execution_status=ok`, 오류 없음, warm-up 160 job·측정 160 job·20 cohort가
일치했다. TET G/C/P는 236.590/236.078/236.367 ms (spread 0.22%),
TAT는 60.761/60.373/60.318 ms (spread 0.73%), 전체 run makespan은
159.137/159.089/159.071 ms (spread 0.04%)다. 측정 job 평균 CPU는
G/C/P 1.479/1.475/1.477 ms로 예상 1.5 ms와 가깝고, 최대 release→completion은
3.137/3.089/3.089 ms로 4 ms period 안에 있다.

HARA의 isolated task 분석에서 modeled access는 sweep 2/4/8에 따라
4,608/9,216/18,432회로 늘지만, element·line CA는 각각
0.00617/0.00461/0.00415로 감소한다. Working set을 그대로 두고 같은
주소를 더 반복한 결과와 일치한다. 이 정적 수치만으로 동시 실행 중의 cache
간섭을 추론하지 않는다.

8-task/8-sweep도 G/C/P 모두 exit code 0, raw 재파싱 `execution_status=ok`,
오류 없음, warm-up 160 job·측정 160 job·20 cohort가 일치했다. TET G/C/P는
469.892/470.211/469.895 ms (spread 0.07%), TAT는
119.218/119.013/118.918 ms (spread 0.25%), 전체 run makespan은
318.030/318.043/318.038 ms (spread <0.01%)다. 측정 job 평균 CPU는
G/C/P 2.937/2.939/2.937 ms이고, 최대 release→completion은
6.061/6.043/6.046 ms로 8 ms period 안에 있다. 8 task에서 sweep을
2→4→8로 늘릴수록 TAT spread는 1.67%→0.73%→0.25%로 줄었다.

16-task/4-sweep도 G/C/P 모두 exit code 0, raw 재파싱 `execution_status=ok`,
오류 없음, warm-up 320 job·측정 320 job·20 cohort가 일치했다. TET G/C/P는
473.562/472.716/472.603 ms (spread 0.20%), TAT는
122.050/121.019/121.006 ms (spread 0.86%), 전체 run makespan은
318.220/318.176/318.181 ms (spread 0.01%)다. 최대 release→completion은
6.220/6.176/6.181 ms로 8 ms period 안에 있다. 4 sweep에서 task 수를
8→12→16으로 늘린 TAT spread는 0.73%→0.83%→0.86%다.

| Task 수 / sweep | TET spread | TAT spread | Makespan spread | P의 TAT winner margin |
|---|---:|---:|---:|---:|
| 8 / 2 | 0.08% | 1.67% | 0.04% | 0.88% |
| 8 / 4 | 0.22% | 0.73% | 0.04% | 0.09% |
| 8 / 8 | 0.07% | 0.25% | <0.01% | 0.08% |
| 12 / 4 | 0.08% | 0.83% | 0.02% | 0.14% |
| 16 / 4 | 0.20% | 0.86% | 0.01% | 0.01% |

Period를 함께 늘렸으므로 다섯 입력의 모델상 aggregate byte-load rate는 모두
초당 18.432M회다. P의 측정 CPU에서 계산한 정규화된 core 이용률도 약
0.73–0.75다. 따라서 이 실험은 P의 core별 task working set을 48→72→96 KiB로
늘리거나 job을 길게 했을 때의 비교이며, 단위 시간당 memory 접근 수요를
증가시킨 실험은 아니다. 모든 입력의 TET·TAT spread가 초기 5% 기준보다
작고, TAT 최선 P와 차선 C의 margin도 1% 미만이다. 동질·균형
`paired-pass`의 task 수나 sweep만 늘리는 방식은 이 조건에서 뚜렷한
architecture-sensitive workload를 만들지 못했다.

## Warm-up 민감도와 20+200 주기 확장

[측정 계약 v3](../../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT-V3.md)에
따라 앞 20주기는 실행하며 checksum·deadline·배치를 검증하되 TET/TAT와
label에서는 제외한다. Cache flush 없이 다음 200주기를 측정한다.
`makespan_ns`는 warm-up을 포함한 공통 epoch부터 계산하므로 측정 구간만의
길이를 원할 때는 `run_execution_span_ns`를 본다. 시작 상태까지 목적함수에
포함하려면 별도의 cold-start 지표로 보고하고 steady-state TET/TAT와 섞지 않는다.

기존 20+20 raw에서 앞 20주기와 뒤 20주기를 같은 TAT 규칙으로 각각
재집계한 결과는 다음과 같다. 기준 8/2 raw는 수정된 준비 소스를 건드리지 않고,
원래 manifest hash와 일치하는 소스를 임시 복사본에만 넣어 재검증했다.

| Task 수 / sweep | 앞 20주기 TAT spread·최선 | 뒤 20주기 TAT spread·최선 |
|---|---:|---:|
| 8 / 2 | 2.06% · P | 1.67% · P |
| 8 / 4 | 0.69% · P | 0.73% · P |
| 8 / 8 | 0.31% · C | 0.25% · P |
| 12 / 4 | 0.71% · P | 0.83% · P |
| 16 / 4 | 0.97% · P | 0.86% · P |

8/8의 최선 순위가 바뀐 것은 두 값의 차이가 매우 작아서다. Warm-up
제외 여부를 격차를 키우기 위한 선택 변수로 취급하지 않는다.

위 다섯 입력에 대응하는 `*-full.json`을 새로 만들어 task당 warm-up 20회와
측정 200회, architecture당 독립 실행 1회를 계획했다. Task 수 8/12/16의
총 계획 job은 각각 1,760/2,640/3,520개다. 각 short/full 쌍의
`source/workload.c` hash가 같고, G/C/P `prepare`와 HARA `analyze`가 모두
통과했다. 2026-09-26 09:18 UTC에 15개 실행을 백그라운드로 시작했으며,
8-task 세 입력과 16-task 입력의 G/C/P는 모두 exit code 0이었다.
`load_batch()` 재파싱에서 각각 task당 20 warm-up + 200 measurement job,
200 cohort, 오류 없음, deadline miss 없음이 확인됐다. Architecture당 독립
실행은 1회이며, 단위는 ms다. Spread는 세 값 중 최댓값과 최솟값의 차이를
최솟값으로 나눈 값이다.

| Task / sweep | TET G / C / P | TET spread | TAT G / C / P | TAT spread | Makespan G / C / P | Makespan spread |
|---|---:|---:|---:|---:|---:|---:|
| 8 / 2 | 1189.751 / 1190.354 / 1189.174 | 0.099% | 312.860 / 310.766 / 307.527 | 1.734% | 439.670 / 439.625 / 439.614 | 0.013% |
| 8 / 4 | 2362.967 / 2362.657 / 2361.904 | 0.045% | 606.049 / 603.515 / 602.388 | 0.608% | 879.110 / 879.110 / 879.097 | 0.002% |
| 8 / 8 | 4700.141 / 4699.029 / 4699.003 | 0.024% | 1191.617 / 1188.877 / 1188.856 | 0.232% | 1758.067 / 1758.024 / 1758.031 | 0.002% |
| 16 / 4 | 4733.585 / 4728.473 / 4723.977 | 0.203% | 1218.839 / 1209.300 / 1207.887 | 0.907% | 1758.215 / 1758.195 / 1758.207 | 0.001% |

12-task 입력의 G/P는 재파싱에 통과했으나, C는 2,640 job을 모두 기록하고
simulator return code도 0인 상태에서 `arm_phase`와 `release_mismatch`가
검출돼 측정 실패로 분류됐다. 원본 `c/`는 보존하고 2026-09-26 09:55 UTC에
같은 설정의 C를 `c-retry1/`로 재실행했다. 재실행의 첫 4개 task도 모두
arm tick이 `t0_tick + 1`이고 public status의 release mismatch가
재현되어 2026-09-26 10:07 UTC에 중단했다(960/2,640 job 기록).
`load_batch()`는 이 부분 실행도 실패로 분류하며 label에는 사용하지 않는다.
12-task 입력은 유효한 G/C/P 비교가 없고, 현재 유효한 네 입력은 task 수·sweep
증가만으로 큰 G/C/P TET/TAT 차이를 만들지 못했다.

진행 상태와 예시 raw는 다음과 같이 볼 수 있다.

```sh
tail -f .cache/periodic-memory-gap-v1/paired-pass-period-200-supervisor.log
```

## Paired-pass working-set capacity 비교

기존 24 KiB/task `paired-pass-8-high-load-full`과 비교할 4/6/8 KiB/task
설정을 `.cache/configs/periodic-memory-gap/working-set-capacity/`에 만들었다.
각 workload는 동일한 paired-pass task 8개를 core당 2개씩 배치하고
period 2 ms, task당 20 warm-up + 200 measurement job을 사용한다.
`distinct × stride`로 계산한 task별 working set은 4/6/8 KiB이고
P에서 core당 두 task의 배열 크기 합은 8/12/16 KiB다. `sweeps`를 각각
12/8/6으로 조절해 기존 24 KiB × 2 sweep 입력을 포함한 네 workload의
job당 volatile load 수를 모두 4,608회로 맞췄다. 루프 trip 수는
4,322–4,332회로 근접한다. 이 비교에서는 working set을 workload 간에
바꾸고, 각 workload 내부의 task는 동일하게 유지한다.

G/C/P `prepare`와 HARA `analyze`가 모두 통과했다. 2026-09-26 10:12 UTC에
세 입력 × 세 architecture의 정식 길이 실행을 백그라운드로 시작했고,
10:33–10:34 UTC에 9개 모두 exit code 0으로 끝났다. `load_batch()` 재파싱에서
모두 오류 없음, warm-up 160 job·측정 1,600 job·200 cohort가 확인됐다.
최대 release→completion은 전체에서 1.511 ms로 2 ms period 안에 있다.
Architecture당 독립 실행은 1회다. Raw는
`.cache/periodic-memory-gap-v1/working-set-capacity/wss{4,6,8}k/`에 있다.

| WSS/task | TET G / C / P (ms) | Spread | TAT G / C / P (ms) | Spread | Makespan spread |
|---|---:|---:|---:|---:|---:|
| 4 KiB | 876.631 / 867.276 / 857.970 | 2.175% | 232.174 / 227.659 / 221.355 | 4.888% | 0.015% |
| 6 KiB | 891.897 / 881.119 / 874.831 | 1.951% | 236.242 / 231.323 / 225.576 | 4.729% | 0.015% |
| 8 KiB | 909.109 / 900.756 / 892.851 | 1.821% | 240.900 / 236.537 / 231.094 | 4.243% | 0.014% |

세 입력 모두 P가 TET/TAT 최선이다. 24 KiB/task 기준 입력의 TET/TAT
spread 0.099%/1.734%보다 격차가 커졌지만, 최대 TAT spread도 초기 5%
기준 아래다. P와 차선 C의 TAT 차이는 약 2.4–2.9%다. 작업집합 크기에
따른 변화와 일치하지만 독립 반복과 packed 대조 없이 cache migration을
원인으로 단정하지 않는다.

```sh
tail -f .cache/periodic-memory-gap-v1/working-set-capacity/supervisor.log
tail -f .cache/periodic-memory-gap-v1/working-set-capacity/wss4k/g/0.log
```

## 8-task job·sweep 확장

기존 역할 균형 victim/polluter 두 입력의 task 수와 core당 victim 1개·polluter
1개 배치를 유지하고, spread/packed 모두 period 2 ms에서 sweep을 2→3으로
늘렸다. Victim은 384 load/job, polluter는 3,072 load/job이며 각 task는
20 warm-up + 200 measurement job을 계획했다. 기존 2-sweep full raw의
최대 응답시간은 G에서 1.015 ms였으므로, 1 ms 주기에 sweep까지 늘린 조합은
공통 deadline 성공을 기대하기 어렵다.

`window-bank-variants-8`도 8-task·2/2/2/2 배치를 유지하고 period 10 ms,
각 task 20+200 job으로 늘렸다. Sweep은 원본 8/4/1/2의 3배인
24/12/3/6이며, 네 종류 task의 접근 수가 모두 13,824 load/job이다.
기존 짧은 실행의 최대 응답시간은 2.205 ms였다. 이 입력도 deadline 성공과
TET/TAT를 새 raw에서 판정했다.

설정은 `.cache/configs/periodic-memory-gap/victim-polluter-sweep/`의 spread/packed
쌍과 `.cache/configs/periodic-memory-gap/window-bank-sweep/`의 s3x 입력이다.
세 설정의 G/C/P `prepare`와 HARA `analyze`가 통과했다. 2026-09-26
10:23 UTC에 9개 G/C/P 실행을 기존 working-set batch 종료 뒤 시작하도록
백그라운드에 예약했고 10:33:55 UTC에 모두 시작돼 10:55 UTC까지 종료됐다.
9개 모두 exit code 0, `load_batch()` 재파싱에서 오류 없음, warm-up 160 job·
측정 1,600 job·200 cohort가 일치했다. 최대 release→completion은 victim
쌍에서 1.328 ms(2 ms period), window-bank에서 5.732 ms(10 ms period)다.
Architecture당 독립 실행은 현재 1회다. 원시 자료는 `.cache/periodic-memory-gap-v1/`의
`victim-polluter-sweep/`과 `window-bank-sweep/`에 각각 보존한다.

| 입력 | TET G / C / P (ms) | TET spread | TAT G / C / P (ms) | TAT spread | Makespan spread |
|---|---:|---:|---:|---:|---:|
| victim spread, 3 sweep | 703.434 / 736.738 / 735.035 | 4.735% | 209.142 / 203.224 / 202.433 | 3.314% | 0.018% |
| victim packed, 3 sweep | 691.774 / 720.113 / 712.229 | 4.097% | 203.856 / 198.093 / 194.540 | 4.789% | 0.012% |
| window-bank, 3× sweep | 3941.955 / 4260.810 / 4250.627 | **8.089%** | 1096.083 / 1080.623 / 1078.751 | 1.607% | 0.010% |

Victim 두 입력은 TET/TAT 모두 초기 5% 기준 아래다. Window-bank는
TET에서 G와 차선 P의 차이도 7.83%로 커서 architecture sensitivity의
초기 격차 조건을 충족하지만, TAT 최선 P와 차선 C의 차이는 0.173%로
`near_tie` 범위다. Window-bank conflict 네 task의 측정 CPU 합계는
G/P 2,394/2,975 ms, resident 네 task는 G/P 1,548/1,275 ms여서
서로 반대 방향의 변화가 일부 상쇄된다. 측정 200 cohort에서 마지막 완료
task는 G에서 conflict128 task 3이 168회, P에서 resident512 task 4가
200회였다. TET 격차를 TAT label의 명확성으로 대체하지 않는다.

Window-bank TET 격차의 반복 안정성을 확인하려고 2026-09-26 11:08 UTC에
G/C/P별 독립 프로세스 4회를 더 시작했고 11:30 UTC에 모두 종료됐다.
첫 실행을 포함한 15개 raw를 `load_batch()`로 재파싱한 결과 모두 성공했으며,
같은 architecture의 5회는 TET·TAT·makespan이 ns 단위까지 동일했다.
G/C/P의 TET는 각각 3941.955/4260.810/4250.627 ms, TAT는
1096.083/1080.623/1078.751 ms다. 이 실행 환경에서 반복값이 동일하다는
확인이며, 독립 확률 표본 5개로 불확실성을 추정할 수 있다는 뜻은 아니다.

```sh
tail -f .cache/periodic-memory-gap-v1/extended-eight-task-supervisor.log
tail -f .cache/periodic-memory-gap-v1/window-bank-sweep/variants-8-s3x/repeats-supervisor.log
```

## 주기와 job당 접근량 동시 확장

8-task·2/2/2/2 core 배치와 각 task의 20 warm-up + 200 measurement job을
유지하면서 주기와 sweep 수를 각각 두 배로 늘렸다. 총 horizon과 warm-up
tick도 두 배로 맞췄다. 따라서 계획상 단위 시간당 배열 load 수는 같고,
job 하나에서 배열을 접근하는 횟수는 두 배다. 아래 CPU 시간은 배열 load와
동일한 job 구간의 부대 비용을 함께 포함한다.

| 입력 | 이전 → 새 주기 | 이전 → 새 sweep/job | 이전 → 새 load/job | 작업집합 |
|---|---:|---:|---:|---:|
| paired-pass WSS 4 KiB | 2 → 4 ms | 12 → 24 | 4,608 → 9,216 | task당 4 KiB |
| window-bank variants | 10 → 20 ms | 24/12/3/6 → 48/24/6/12 | 13,824 → 27,648 | task당 기존 크기 유지 |

설정은 `.cache/configs/periodic-memory-gap/working-set-capacity/paired-pass-wss4k-p4-s24-full.json`과
`.cache/configs/periodic-memory-gap/window-bank-sweep/window-bank-variants-8-s6x-p20-full.json`이다.
두 입력 모두 G/C/P 계획 검증, 빌드, HARA `analyze`를 통과했다.
2026-09-26 11:43 UTC에 총 6개 실행을 백그라운드에서 시작했고 12:05 UTC까지
모두 exit code 0으로 종료됐다. `load_batch()`로 raw를 다시 파싱한 결과
6개 모두 `execution_status=ok`, 오류 없음, warm-up 160 job·측정 1,600 job·
200 cohort가 일치한다. 전체 job의 최대 release→completion은 paired-pass
2.541 ms(주기 4 ms), window-bank 11.077 ms(주기 20 ms)다.

| 입력 | TET G / C / P (ms) | TET spread | TAT G / C / P (ms) | TAT spread | Makespan G / C / P (ms) |
|---|---:|---:|---:|---:|---:|
| paired-pass WSS 4 KiB, 4 ms | 1716.245 / 1707.759 / 1698.254 | 1.059% | 442.021 / 437.830 / 431.827 | 2.361% | 878.304 / 878.261 / 878.223 |
| window-bank variants, 20 ms | 7852.395 / 8478.760 / 8467.598 | **7.977%** | 2149.541 / 2141.492 / 2139.455 | 0.471% | 4391.077 / 4390.794 / 4390.771 |

P의 측정 job당 평균 CPU는 paired-pass에서 기존 0.536→1.061 ms,
window-bank에서 2.657→5.292 ms로 늘었다. 하지만 기존 입력 대비
G/C/P TET spread는 각각 2.175→1.059%, 8.089→7.977%이고 TAT spread는
4.888→2.361%, 1.607→0.471%로 줄었다. Window-bank는 TET 최선 G와
차선 P의 차이가 7.835%로 여전히 크지만, TAT 최선 P와 차선 C의 차이는
0.095%로 `near_tie`다. 주기·job당 접근량을 함께 늘리는 것만으로
TAT 구분력이 커지지는 않았다. 새 입력의 architecture당 독립 실행은 1회다.

원시 로그는 다음 경로에 보존한다.

```sh
tail -f .cache/periodic-memory-gap-v1/period-scaled-supervisor.log
tail -f .cache/periodic-memory-gap-v1/working-set-capacity/wss4k-p4-s24/g/0.log
tail -f .cache/periodic-memory-gap-v1/window-bank-sweep/variants-8-s6x-p20/p/0.log
```

## victim/polluter 접근 패턴 진단

`victim-polluter-8-spread-short.json`은 앞선 연구의 exp5-1 F128과 같은
역할 분리 구조를 진단하기 위해 4 KiB victim 4개와 32 KiB polluter 4개를
2/2/2/2로 배치했다. 모두 job당 2 sweep이며, 주기 1 ms·task당
20 warm-up + 20 measurement job을 계획했다. G/C/P 각각 1회 실행했고
raw와 실패 상태를 보존했다. 시작 구간에서 deadline miss와 postponed job이
발생해 G/C는 계획한 320 job 중 281개, P는 242개만 기록됐다.
`load_batch()` 재파싱 결과 세 architecture 모두 `execution_status=failed`이며
`deadline_miss`, `job_completeness`, `period_state`, `postponed_job` 오류가 있다.
따라서 이 실행의 부분 TET/TAT는 비교 결과로 사용하지 않는다.

`victim-polluter-8-spread-p2-short.json`은 역할·접근 패턴·core 배치를 유지하고
주기만 2 ms로 늘린 재진단이다. 동일한 20+20 job 계획으로 prepare와 HARA
analysis가 통과했다. G/C/P 각각 1회 실행해 모두 exit code 0,
raw 재파싱 `execution_status=ok`, 오류 없음, warm-up 160 job·측정 160 job·
20 cohort가 일치했다. 두 설정은 실패한 1 ms 입력을 버리지 않고 구분해 보존한다.

| 지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| TET (ms) | 48.511 | 37.418 | 33.741 | **43.77%** |
| TAT (ms) | 14.726 | 16.648 | 15.933 | **13.05%** |

TAT 최선 G와 차선 P의 차이는 G 대비 8.19%다. 다만 P의 2/2/2/2 배치는
victim 전용 core 2개와 polluter 전용 core 2개로 역할을 분리한다.
P에서 측정한 victim 한 job의 CPU는 약 41 µs인 반면 polluter는
약 368–394 µs여서 core별 작업량이 균형이 아니다. 그러므로 이 TAT 격차를
cache 효과만의 증거로 해석하지 않는다. `victim-polluter-8-mixed-p2-short.json`은
각 core에 victim·polluter를 하나씩 배치하는 작업량 균형 대조군이다.

이 대조군 역시 G/C/P 각각 1회 실행해 모두 exit code 0,
raw 재파싱 `execution_status=ok`, 오류 없음, warm-up 160 job·측정 160 job·
20 cohort가 일치했다. 두 입력의 생성된 `source/workload.c` hash는 같고,
G의 TET·TAT도 ns 단위까지 같다. 차이는 C/P에서의 core 지정이다.

| 작업량 균형 배치 지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| TET (ms) | 48.511 | 50.100 | 49.766 | 3.28% |
| TAT (ms) | 14.726 | 14.214 | 13.767 | **6.97%** |

TET spread는 역할 분리 배치의 43.77%에서 3.28%로 줄었다. TAT는 P가
가장 작지만 차선 C와의 winner margin은 P 대비 3.25%로, 명세의 초기
`boundary` 범위다. 이는 architecture별 차이가 존재한다는 짧은 진단 결과이며,
200 measurement round로 label 안정성을 확인한 결과는 아니다. 정식 길이
대응군 결과도 아래에 별도로 기록한다.

`victim-polluter-8-mixed-packed-p2-short.json`은 바로 위 대조군과 task 수,
core 배치, period, victim당 256 load/job 및 polluter 입력이 같고,
victim stride만 32에서 1로 바꾼 packed 대응군이다. Victim의 주소 범위는
4 KiB에서 128 B로 줄었다. HARA 분석에서 victim의 element CA는 두 입력
모두 0.0078125이고, line CA는 spread 0.0078125 대 packed 0.954545로
구분된다. G/C/P 각각 1회 실행해 모두 exit code 0,
raw 재파싱 `execution_status=ok`, 오류 없음, warm-up 160 job·측정 160 job·
20 cohort가 일치했다.

| packed 배치 지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| TET (ms) | 45.995 | 48.490 | 48.125 | **5.42%** |
| TAT (ms) | 14.154 | 13.672 | 13.602 | 4.05% |

같은 역할 균형 배치에서 spread→packed로 바꾸면 TAT spread는
6.97%→4.05%, P의 winner margin은 3.25%→0.51%로 줄었다. P가 둘 다
TAT 최선이지만 packed의 margin은 초기 `near_tie` 범위다. 이 비교는
cache footprint의 영향과 일치하나, 단일 짧은 실행과 정적 분석만으로
원인을 단정하거나 최종 label을 부여하지 않는다.

계약상 앞 20 round는 실제 실행하되 TET/TAT 합계에서 제외하고, 그 뒤
cache flush 없이 측정한다. Raw의 앞 20 round를 같은 cohort 규칙으로
별도 재집계하면 spread의 TAT G/C/P는 14.840/14.224/13.782 ms,
packed는 14.261/13.680/13.613 ms다. 두 입력 모두 측정 20 round와
TAT 순위가 같다. 첫 cohort TAT는 각 architecture의 측정 구간 median보다
약 5–8% 길었다. 이는 초기 transient의 존재를 보여주지만 20 round가
모든 workload에 충분한 warm-up이라는 증명은 아니다.

## 20+200 round victim/polluter 역할 균형 배치

`victim-polluter-8-mixed-p2-full.json`과
`victim-polluter-8-mixed-packed-p2-full.json`은 위 짧은 대응군의 task,
배치, 접근 패턴, period를 유지하고 측정 구간만 200 round로 늘렸다.
각각 짧은 입력과 `source/workload.c` hash가 같다. 두 입력 모두 G/C/P
exit code 0, raw 재파싱 `execution_status=ok`, 오류 없음,
warm-up 160 job·측정 1,600 job·200 cohort가 일치했다.

| 입력·지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| spread TET (ms) | 478.658 | 499.680 | 498.411 | 4.39% |
| spread TAT (ms) | 146.889 | 141.260 | 139.050 | **5.64%** |
| packed TET (ms) | 465.981 | 482.996 | 478.299 | 3.65% |
| packed TAT (ms) | 141.093 | 136.260 | 132.592 | **6.41%** |

두 입력 모두 P의 TAT가 가장 작다. 차선 C 대비 P의 winner margin은 spread
1.59%, packed 2.77%로 모두 초기 `boundary` 범위다. 짧은 입력에서
packed TAT spread는 4.05%였으나 200 round에서는 6.41%이므로,
짧은 실행의 5% 기준 통과 여부를 그대로 연장하지 않는다. Architecture당
독립 실행이 1회라 최종 label 안정성이나 원인을 확정하지 않는다.

## Victim 작업량을 늘린 critical-path 파일럿

기존 3-sweep 역할 균형 입력에서 P의 victim CPU는 job당 약 0.04–0.07 ms,
polluter CPU는 약 0.75–0.90 ms였다. 측정 cohort의 마지막 완료도 대부분
polluter였다. Victim의 cache-footprint 차이가 TAT의 마지막 완료를 바꾸는지
검사하려고 victim sweep만 24/48/72로 늘린다. Polluter는 3 sweep,
공통 주기는 2 ms, task 수는 8개이며 각 core에 victim과 polluter를 하나씩
둔다. Spread/packed layout을 쌍으로 유지하므로 각 task의 주소 범위는
기존과 같다. Victim load/job은 3,072/6,144/9,216회이고 polluter는
3,072회다.

6개 입력 모두 task당 20 warm-up + 20 measurement job으로 계획했고,
G/C/P 계획 검증·빌드·HARA `analyze`를 통과했다. 2026-09-26 13:11 UTC에
18개 G/C/P 실행을 최대 6개 동시 실행으로 백그라운드에서 시작했고
13:21 UTC에 모두 종료됐다. 24/48-sweep의 12개 실행은 exit code 0이며
`load_batch()` raw 재파싱에서 각 실행의 warm-up 160 job·측정 160 job·
20 cohort와 오류 없음이 확인됐다. 72-sweep의 6개 실행은 모두
`deadline_miss`, `job_completeness`, `period_state`, `postponed_job`로
실패했고, 부분 TET/TAT는 비교하지 않는다.

| Victim layout/sweep | TET G / C / P (ms) | TET spread | TAT G / C / P (ms) | TAT spread | TAT 최선·차선 margin |
|---|---:|---:|---:|---:|---:|
| spread/24 | 84.668 / 94.216 / 93.669 | 11.278% | 25.739 / 25.559 / 25.067 | 2.683% | P 1.961% |
| packed/24 | 83.259 / 92.494 / 92.356 | 11.093% | 25.226 / 24.995 / 24.895 | 1.328% | P 0.402% |
| spread/48 | 107.319 / 117.079 / 116.563 | 9.094% | 30.955 / 31.265 / 30.794 | 1.530% | P 0.524% |
| packed/48 | 105.666 / 115.632 / 115.296 | 9.433% | 30.612 / 30.878 / 30.647 | 0.869% | G 0.112% |

Victim 작업량을 늘려도 TAT의 명확한 winner가 나타나지 않았다. 48-sweep
spread에서는 G의 마지막 완료 task가 20 cohort 중 9회 victim으로 바뀌었지만,
P에서는 여전히 polluter가 20회 모두 마지막이었다. 24/48-sweep의 최대
release→completion은 각각 1.576/1.874 ms로 2 ms period 안에 있다.
짧은 실행과 200-round 실행의 차이를 점검하기 위해 **유효한 네 설정 모두**의
20 warm-up + 200 measurement job 대응군을 빌드·HARA 검증했고,
2026-09-26 13:33 UTC에 G/C/P 12개 실행을 최대 6개 동시 실행으로 시작했다.
14:15 UTC에 모두 exit code 0으로 종료됐다. Raw 재파싱에서 각 실행의
warm-up 160 job·측정 1,600 job·200 cohort가 일치하고 오류가 없었다.
최대 release→completion은 1.864 ms로 2 ms period 안에 있다.

| 20+200 입력 | TET G / C / P (ms) | TET spread | TAT G / C / P (ms) | TAT spread | TAT 최선·차선 margin |
|---|---:|---:|---:|---:|---:|
| spread/24 | 848.089 / 940.501 / 938.069 | 10.896% | 255.489 / 254.764 / 252.882 | 1.031% | P 0.745% |
| packed/24 | 829.344 / 923.215 / 918.607 | 11.319% | 251.089 / 249.194 / 245.987 | 2.074% | P 1.304% |
| spread/48 | 1068.045 / 1167.119 / 1167.111 | 9.276% | 309.828 / 310.533 / 310.257 | 0.228% | G 0.138% |
| packed/48 | 1059.298 / 1152.780 / 1146.761 | 8.825% | 305.052 / 306.917 / 302.457 | 1.474% | P 0.858% |

정식 길이 네 설정 모두 G의 TET가 가장 작고 전체 TET spread는
8.825–11.319%다. 반면 TAT 최선·차선 margin은 0.138–1.304%로
5%에 미치지 않는다. 특히 spread/48의 TAT 최선은 짧은 실행에서 P였지만
정식 길이에서는 G로 바뀌었다. 전체 run makespan spread도
0.006–0.013%다. Architecture당 독립 실행이 1회이므로 label 안정성을
확정할 수 없다. 모든 후보와 72-sweep 실패를 공개하며 이 파일럿을
본 데이터셋 label로 사용하지 않는다.

설정은 `.cache/configs/periodic-memory-gap/victim-polluter-sweep/critical-path/`,
raw는 `.cache/periodic-memory-gap-v1/victim-polluter-sweep/critical-path/`에 있다.

```sh
tail -f .cache/periodic-memory-gap-v1/victim-polluter-sweep/critical-path/supervisor.log
tail -f .cache/periodic-memory-gap-v1/victim-polluter-sweep/critical-path/full-supervisor.log
tail -f .cache/periodic-memory-gap-v1/victim-polluter-sweep/critical-path/spread-v24-p2-full/g/0.log
```

## 주기 혼합·기준 U 고정 파일럿

공통 10 ms 주기인 `window-bank-variants-8-s3x-full`을 대조군으로 두고,
같은 8 task·2/2/2/2 배치에서 conflict 네 task만 주기 10→20 ms,
sweep/job 24/12→48/24로 늘린다. Resident 네 task는 주기 10 ms와
sweep/job 3/6을 유지한다. 모든 task의 배열·접근 순서와 초당 계획 load 수
(task당 1,382,400회)는 유지된다. 두 입력의 horizon은 2,200 ms,
warm-up은 200 ms다. 대조군의 측정 job은 1,600개, 혼합 주기는
1,200개이며, 각 입력 내부에서만 동일한 job 집합으로 G/C/P를 비교한다.

기존 다중 task P raw에서 대조군의 코어별 측정 U는 0.526–0.536이고,
20 ms conflict P raw와 10 ms resident P raw를 합친 혼합 주기 예상 U도
약 0.525–0.535다. 이는 사전 추정이며 독립 P 실행에서 task별 U 차이가
5% 이내인지 확인한다. Pilot은 독립 P를 task당 각 입력 1회만 실행하므로
정식 데이터셋의 5회 U 보정으로 간주하지 않는다. 그 검증을 통과해야
혼합 주기 G/C/P를 실행하도록 정했고, 실패와 deadline miss도 그대로 남긴다.

혼합 주기 [설정](../../../.cache/configs/periodic-memory-gap/mixed-period-fixed-u/window-bank-variants-8-conflict-p20-resident-p10-full.json)과
[실행기](../../../.cache/configs/periodic-memory-gap/mixed-period-fixed-u/run.py)는
G/C/P 계획 검증, 빌드, HARA 분석을 통과했다. Raw와 진행 로그는
`.cache/periodic-memory-gap-v1/mixed-period-fixed-u/`에 둔다.
혼합 주기의 TAT는 동일 nominal release cohort별 span 합이므로,
공통 주기 대조군과 절대 TAT 합계를 같은 job 집합처럼 비교하지 않는다.
2026-09-26 17:45 UTC에 독립 P 16개→U 확인→혼합 주기 G/C/P 3개를
지속 실행 세션에서 시작해 18:12 UTC에 모두 종료했다. 최대 동시 실행 수는
각 단계에서 4개·3개다. 독립 P 16개 모두 exit code 0, raw 재파싱 오류가
없다. 대조군 대비 혼합 주기의 task별 독립 U 차이는 최대 0.143%,
코어별 U 합 차이는 최대 0.085%로 사전 5% 기준을 통과했다. 독립 P의
코어별 U 합은 대조군 0.384–0.386, 혼합 주기 0.383–0.386이다.
위의 0.53 수준은 두 task가 함께 실행한 P 측정치이므로 독립 P U와
같은 값으로 해석하지 않는다.

혼합 주기 G/C/P도 모두 exit code 0이고 `load_batch()`로 raw를 재파싱해
오류 없음, warm-up 120 job·측정 1,200 job·200 cohort를 확인했다.
100 cohort에는 8개 task가, 나머지 100 cohort에는 10 ms resident
4개 task만 release된다. 전체 job의 최대 release→completion은
9.494 ms로 각 task의 10/20 ms deadline 안에 있다.

| 입력 | TET G / C / P (ms) | TET spread | TAT G / C / P (ms) | TAT spread | TAT 최선·차선 margin |
|---|---:|---:|---:|---:|---:|
| 공통 10 ms 대조군 | 3941.955 / 4260.810 / 4250.627 | 8.089% | 1096.083 / 1080.623 / 1078.751 | 1.607% | P 0.173% |
| 혼합 20/10 ms | 4246.043 / 4248.863 / 4234.585 | 0.337% | 1079.501 / 1076.986 / 1073.638 | 0.546% | P 0.312% |

기준 U와 task별 초당 load 수를 맞췄어도 혼합 주기에서 TAT winner margin은
0.312%로 여전히 작다. TET spread는 8.089→0.337%로 줄고 최선도 G에서
P로 바뀌었다. 측정 구간의 conflict 네 task CPU 합은 G에서 대조군
2,394.338→혼합 2,964.577 ms, P에서는 2,975.181→2,966.224 ms다.
이는 G의 conflict CPU 이점이 이 조건에서 사라졌다는 관찰이며, EDF 실행
순서·캐시 간섭 중 무엇이 원인인지는 별도 trace 없이 확정하지 않는다.
주기와 job당 sweep을 함께 바꿨으므로 이 결과를 주기만의 인과 효과로
해석하지 않는다. Architecture당 혼합 주기 실행은 1회이며 본 데이터셋
label로 사용하지 않는다.

Raw를 task 종류별로 다시 집계하면, 공통 10 ms에서 conflict job당 CPU는
G/P 2.993/3.719 ms였지만 혼합 20/10 ms에서는 7.411/7.416 ms로
거의 같아졌다. Resident도 G/P 1.934/1.594 ms에서 1.602/1.586 ms로
가까워졌다. 반면 **모든** task의 주기와 sweep을 두 배로 늘린 공통
20 ms 대조군에서는 conflict job당 G/P 6.010/7.426 ms로 G의 이점이
유지됐다. 따라서 job을 길게 만든 것만으로 혼합 실험의 TET 격차 감소를
설명할 수 없다. 혼합 실험에서 P resident의 평균 release→start는
0.035 ms(공통 10 ms에서는 3.786 ms), conflict는 1.655 ms(기존
0.042 ms)로 실행 순서가 뒤집혔다. G에서도 resident 시작 지연은
2.289→0.065 ms로 줄었다. 10 ms resident의 더 이른 EDF deadline과
resident-only release가 스케줄을 바꿨다는 증거지만, CPU 변화 중 캐시
miss와 migration이 각각 얼마나 기여했는지는 현재 raw만으로 분리할 수 없다.

```sh
tail -f .cache/periodic-memory-gap-v1/mixed-period-fixed-u/supervisor.log
tail -f .cache/periodic-memory-gap-v1/mixed-period-fixed-u/isolated/control/task-00/0.log
```

## 태스크 수·주기 혼합 파일럿

태스크 수를 4·8·12·16개(코어당 1·2·3·4개)로 늘리고 각 입력에
10·20·40·80 ms 주기를 섞었다. 네 종류의 window-bank task를 코어별로
회전 배치해 task 수가 늘수록 코어당 종류도 늘어난다. Task 종류별 period,
working set, 접근 패턴은 같고, task 수에 맞춰 job당 sweep을 조정했다.
기존 독립 P 측정에 근거한 코어별 계획 U는 약 0.395–0.401이다.
입력별 계획 배열 접근 빈도는 약 1,184만–1,187만 회/s로 비슷하다.

| Task 수 | 코어당 task 수 | 전체 job 수 | 측정 job 수 |
|---:|---:|---:|---:|
| 4 | 1 | 600 | 525 |
| 8 | 2 | 1,200 | 1,050 |
| 12 | 3 | 1,800 | 1,575 |
| 16 | 4 | 2,400 | 2,100 |

모든 입력의 horizon은 3,200 ms, warm-up은 400 ms다. [설정과 실행기](../../../.cache/configs/periodic-memory-gap/task-period-sweep/run.py)는
먼저 각 입력의 task 종류별 대표 1개씩 독립 P로 측정한다(총 16회).
같은 종류의 다른 코어 task는 이 대표 측정치를 사용해 코어별 독립 U를
추정하며, 모든 코어가 0.38–0.42 범위에 있을 때만 G/C/P 각 1회씩
실행한다(총 12회). 대표 task만 측정한 파일럿 추정이므로 복제 task의
U가 동일함을 입증하거나 정식 5회 보정을 대체하지 않는다. 실패와
deadline miss는 원시 결과에 그대로 남긴다.

Task 수가 다른 입력은 job 수와 코어당 cache footprint도 달라지므로
TET/TAT 절댓값이나 격차 변화를 task 수만의 인과 효과로 해석하지 않는다.
정책 비교는 각 입력 안에서 같은 job 집합을 실행한 G/C/P 사이에서 한다.
G/C/P 빌드와 정적 분석, `scripts/verify`(507 passed, 1 skipped)는 통과했다.
진행 로그와 raw는 `.cache/periodic-memory-gap-v1/task-period-sweep/`에 둔다.
2026-09-26 18:29:51 UTC에 독립 P 16회→U 확인→G/C/P 12회를
지속 실행 세션에서 시작해 19:44:42 UTC에 모두 종료했다. 28회 모두
exit code 0이고, `load_batch()` 재파싱에서 오류·deadline miss가 없다.
대표 task 기반 코어별 독립 U 추정치는 0.391–0.400으로 사전 범위
0.38–0.42를 통과했다. 각 입력의 G/C/P는 architecture당 1회다.

| Task 수 | TET G/C/P (ms) | TET spread | TAT G/C/P (ms) | TAT spread | TAT 최선·차선 margin |
|---:|---:|---:|---:|---:|---:|
| 4 | 4952.825 / 4952.071 / 4949.764 | 0.062% | 3112.318 / 3110.274 / 3103.622 | 0.280% | P 0.214% |
| 8 | 5519.336 / 5477.978 / 5459.850 | 1.090% | 2114.509 / 2230.715 / 2186.147 | 5.496% | G 3.388% |
| 12 | 5567.991 / 5545.238 / 5531.768 | 0.655% | 1977.812 / 2023.184 / 1979.662 | 2.294% | G 0.094% |
| 16 | 5865.238 / 5863.943 / 5865.653 | 0.029% | 1551.465 / 1544.699 / 1542.932 | 0.553% | P 0.114% |

전체 run makespan의 G/C/P spread는 각 입력에서 최대 0.0011%였다.
TET 격차는 모두 1.1% 이하다. TAT는 8-task에서 5.496%까지 벌어지지만
12·16-task에서는 최선·차선 차이가 각각 0.094%·0.114%에 불과하다.
입력마다 job 수·cohort 크기·코어당 task 종류가 함께 바뀌므로 TAT 합계의
절댓값이 task 수에 따라 감소하는 것을 성능 향상으로 해석하지 않는다.
독립 반복이 없는 진단 파일럿이며 정식 label이나 통계적 유의성 주장이 아니다.

```sh
tail -f .cache/periodic-memory-gap-v1/task-period-sweep/supervisor.log
tail -f .cache/periodic-memory-gap-v1/task-period-sweep/n4/isolated/conflict64/0.log
```

## L1 재사용·혼합 주기 대조 파일럿

작은 working set과 주기 다양화의 결합을 확인하려고 8개 `paired-pass`
task의 공통 2 ms 대조군과 혼합 2/3/5/6 ms 입력을 만들었다. 모든 task는
`width=8`, `distinct=128`, `stride=32`로 4 KiB의 private array에서
128개 cache line을 반복 접근한다. P에서는 코어당 task 2개, 명목상
8 KiB의 데이터 line을 공유한다. GR740 L1D의 16 KiB·4-way에 비해
여유가 있지만 stack·RTEMS 데이터와 충돌하지 않는다고 보장하지는 않는다.

공통 입력은 각 task가 2 ms에 12 sweep을 수행한다. 혼합 입력은 같은
task·코어 배치에서 period 2/3/5/6 ms에 sweep 12/18/30/36을 대응시켜
각 task의 계획 load 빈도를 2,304회/ms로 고정한다. 코어별 period 쌍은
(2,6), (3,5), (5,3), (6,2) ms다. 두 입력 모두 horizon 660 ms,
warm-up 60 ms이며 측정 job은 각각 2,400개와 1,440개다. 주기 혼합은
release/EDF 순서와 job당 접근량도 바꾸므로, 더 잦은 G 이동이나 더 큰
G/P 격차를 결과로 전제하지 않는다.

[설정·실행기](../../../.cache/configs/periodic-memory-gap/l1-resident-period/run.py)는
입력별 task 8개를 각각 독립 P로 1회 측정해 task별·코어별 U 차이가
5% 이내인지 확인한다. 통과한 경우에만 입력별 G/C/P 각 1회로 TET,
TAT, makespan과 job 사이의 시작 코어 변경률을 비교한다. 이 변경률은
job 내부 migration까지 세지 않으므로 캐시 miss의 직접 계측이 아니다.
G/C/P 빌드와 정적 분석은 통과했고, raw·진행 로그는
`.cache/periodic-memory-gap-v1/l1-resident-period/`에 둔다.
정적 독립-task HARA의 L1 first-hit 추정은 task별 97.2–99.1%지만,
공동 실행 시 캐시 잔존율이나 측정 TET를 대신하지 않는다.
`scripts/verify`는 507 passed, 1 skipped였다. 2026-09-26 21:02:32 UTC에
독립 P 16회→U 검사→G/C/P 6회를 지속 실행 세션에서 시작했다.

```sh
tail -f .cache/periodic-memory-gap-v1/l1-resident-period/supervisor.log
```

## 접근 패턴·태스크 수 확장 파일럿

[`pattern-task-count` 설정·실행기](../../../.cache/configs/periodic-memory-gap/pattern-task-count/run.py)는
8/16/24/32 task를 같은 4 ms 주기에서 비교한다. 모든 task는 64개 32-byte
cache line(2 KiB)을 접근하고, 측정 job마다 1,920 byte load를 수행한다.
접근 순서는 `cyclic`(30 sweep), `paired-pass`(10), `window-bank`(6),
`phase`(hot 16 line×4, cold 48 line×2, 12 sweep)로 다르다. 네 패턴의
비율은 모든 task 수에서 1:1:1:1이고, P의 코어 배치는 패턴 순서를
회전해 코어당 task 수를 균형 있게 한다.

각 task는 100 job 중 앞 10 job을 warm-up으로 사용하고 90 job을 측정한다.
G/C/P는 각 설정에서 정확히 같은 task·release·job 내용을 실행한다.
P의 코어당 task 수는 2/4/6/8개, 배열의 명목상 합계는 4/8/12/16 KiB다.
다만 각 private array는 4 KiB 경계에 정렬되어 있어 L1 set 충돌이
용량 한계보다 먼저 나타날 수 있다. 따라서 task 수가 늘 때의 차이를
순수 용량 효과로 해석하지 않는다. 설정 간 총 job 수와 이용률도 달라지므로
성능 격차는 각 설정 안의 G/C/P에서 계산한다.

Raw와 진행 로그는 `.cache/periodic-memory-gap-v1/pattern-task-count/`에 둔다.
실행 중에는 다음 명령으로 케이스별 시작·완료와 TET/TAT를 확인한다.
32-task·3-job 사전 실행은 G/C/P 모두 정상 완료했다. `scripts/verify`는
508 passed, 1 skipped였다. 2026-09-27 03:47:42 UTC에 32→24→16→8
task 순서의 G/C/P 각 1회 파일럿을 백그라운드로 시작했다. 이는 재현성
반복을 마친 확정 성능 결과가 아니다.

```sh
tail -f .cache/periodic-memory-gap-v1/pattern-task-count/supervisor.log
```

## 전체 run makespan

`makespan_ns`는 warm-up을 포함한 공통 epoch `t0`부터 마지막 측정 job
완료까지의 경과시간이다. 측정 job의 첫 시작부터 마지막 완료까지는
`run_execution_span_ns`로 따로 기록한다. 둘 다 주기별 makespan의 합인
TAT와 다르다. 아래는 각 입력에서 유효한 G/C/P raw를 재파싱한 값이며,
입력마다 horizon이 다르므로 행 사이의 절대 시간은 비교하지 않는다.

| 입력 | 전체 run makespan G/C/P (ms) | Spread | 측정 구간 span G/C/P (ms) |
|---|---:|---:|---:|
| `paired-pass-8-high-load` | 79.647 / 79.621 / 79.613 | 0.04% | 39.592 / 39.573 / 39.567 |
| `paired-pass-8-sweeps4-balanced-short` | 159.137 / 159.089 / 159.071 | 0.04% | 79.087 / 79.042 / 79.024 |
| `paired-pass-8-sweeps8-balanced-short` | 318.030 / 318.043 / 318.038 | <0.01% | 157.973 / 157.997 / 157.993 |
| `paired-pass-12-sweeps4-balanced-short` | 238.692 / 238.650 / 238.643 | 0.02% | 118.638 / 118.586 / 118.580 |
| `paired-pass-16-sweeps4-balanced-short` | 318.220 / 318.176 / 318.181 | 0.01% | 158.166 / 158.100 / 158.107 |
| `paired-pass-8-balanced-full` | 2191.649 / 2191.631 / 2191.619 | <0.01% | 1991.592 / 1991.584 / 1991.575 |
| `paired-pass-8-skewed-full` | 2191.649 / 2193.422 / 2193.420 | 0.08% | 1991.592 / 1993.382 / 1993.391 |
| `victim-polluter-8-spread-p2-short` | 78.810 / 78.956 / 78.871 | 0.19% | 38.759 / 38.916 / 38.834 |
| `victim-polluter-8-mixed-p2-short` | 78.810 / 78.799 / 78.771 | 0.05% | 38.759 / 38.756 / 38.729 |
| `victim-polluter-8-mixed-packed-p2-short` | 78.817 / 78.768 / 78.746 | 0.09% | 38.763 / 38.726 / 38.705 |
| `victim-polluter-8-mixed-p2-full` | 438.854 / 438.816 / 438.766 | 0.02% | 398.802 / 398.772 / 398.724 |
| `victim-polluter-8-mixed-packed-p2-full` | 438.822 / 438.756 / 438.744 | 0.02% | 398.770 / 398.712 / 398.702 |

이 실험은 정해진 주기마다 다음 job을 기다리므로 전체 run makespan은
대체로 horizon에 의해 결정된다. 같은 입력의 TAT 격차가 커도 전체 run
makespan 격차는 작을 수 있다. 주기별 평균 makespan을 원하면 같은 입력의
TAT를 측정 cohort 수로 나누며, 이 경우 G/C/P 상대 격차는 TAT와 같다.

## 20+200 round 5/1/1/1 배치 확인 (할당 불균형 대조군)

`paired-pass-8-skewed-full.json`은 짧은 진단과 task·배치·period가 같고,
측정 구간만 200 round로 늘렸다. 두 snapshot의 `source/workload.c` hash와
G/C/P data layout도 일치한다. G/C/P 모두 exit code 0, raw 재파싱
`execution_status=ok`, 오류 없음, warm-up 160 job·측정 1,600 job·200 cohort가
일치했다. Architecture당 독립 실행은 1회다.

| 지표 | G | C | P | Spread |
|---|---:|---:|---:|---:|
| TET (ms) | 1190.200 | 1081.781 | 1082.194 | **10.02%** |
| TAT (ms) | 313.014 | 668.450 | 669.640 | **113.93%** |

G의 TAT winner margin은 차선 C 대비 113.55%다. 이는 의도적으로 한 core에
5개 task를 몰아놓은 배치의 영향이며, 동질 task를 균형 있게 배치했을 때도
TAT가 크게 벌어진다는 증거는 아니다. 짧은 진단과 격차의 방향·크기는 유지됐다.
TET의 C/P 순서는 짧은 진단과 달라졌지만 두 값의 차이는 0.04% 미만이다.
전체 job의 최대 release→completion은 G 1.875 ms, C 3.687 ms, P 3.656 ms로
10 ms period 안에 있다. 이 값은 TAT의 정의와 구분해 기록한다.
정식 길이 5회 반복과 불확실성 판정은 아직 수행하지 않았으므로 최종 label 안정성이나
본 데이터셋 적격성을 이 표로 확정하지 않는다.

## 검증 범위와 재생

각 입력의 `.cache/periodic-memory-gap-v1/<입력>/prepared/manifest.json`은
source·ELF·toolchain hash를, `analysis/manifest.json`은 HARA 산출물 hash를,
`g`, `c`, `p`의 `protocol.json`과 `0.log`는 실행 조건과 raw를 보존한다.
`chaser.periodic.dataset.load_batch()`로 모든 완료 batch를 재파싱했다.
단, 기존 `paired-pass-8-high-load/prepared/source/workload.c`는 이번 확장
실행 전인 2026-09-26 08:52 UTC에 원래 manifest hash와 다르게 수정돼
현재 경로에서 직접 `load_batch()`가 실패한다. 원본 파일은 건드리지 않고,
동일 config에서 별도 생성한 소스가 원래 manifest의 예상 hash와 일치함을 확인한
뒤 임시 `prepared` 복사본의 해당 소스만 교체해 기존 G/C/P raw를 재검증했다.
짧은 독립 재실행은 `paired-pass-8-skewed/{g,c,p}-repeat1/`에 있다.
HARA는 isolated cold-task를 모델링하므로 concurrent cache interference의 원인을
단독으로 증명하지 않는다. 독립 U와 보정된 allocator도 이 진단에는 아직 없다.
본 데이터셋용 `memory_intensity_rule_id`는 이 진단으로 확정하지 않았다.

정식 길이 결과는 새 output 디렉터리에서 다음 명령으로 재생할 수 있다.

```sh
python3 -m tools.rtems_periodic prepare \
  .cache/configs/periodic-memory-gap/paired-pass-8-balanced-full.json \
  --output .cache/periodic-memory-gap-v1/replay/prepared
python3 -m tools.rtems_periodic analyze \
  .cache/periodic-memory-gap-v1/replay/prepared
for architecture in g c p; do
  DISPLAY=165.246.44.80:90.0 python3 -m tools.rtems_periodic run \
    .cache/periodic-memory-gap-v1/replay/prepared \
    --output ".cache/periodic-memory-gap-v1/replay/$architecture" \
    --architecture "$architecture" --runs 1 --timeout 3600
done
```

정식 길이 raw는 `.cache/periodic-memory-gap-v1/paired-pass-8-balanced-full/`과
`.cache/periodic-memory-gap-v1/paired-pass-8-skewed-full/`의 `g`, `c`, `p`
하위 디렉터리와 architecture별 `*.background.log`, `*.pid`, `*.exit`에 있다.
5/1/1/1 입력을 재생할 때는 설정 경로와 output 디렉터리를 함께 바꾼다.
짧은 결과와 정식 길이 결과를 별도 집계했다.

## 공유 캐시 라인 진단 (2026-09-27)

[`false-sharing` 시나리오](../../../.cache/configs/periodic-memory-gap/false-sharing/run.py)는
8 task를 reader/writer 4쌍으로 구성한다. 한 쌍의 두 task는 job마다 같은
128개 32-byte line(4 KiB)을 각각 offset 0에서 읽고 offset 4에 쓴다.
대조군은 같은 작업을 하되 reader/writer가 독립적인 4 KiB 배열을 사용한다.
각 task는 job마다 8 sweep×128=1,024회 접근하고, 1 ms period의 100 job 중
앞 10개를 warm-up으로 제외한다. P는 core당 2 task로 균형을 맞추면서
각 쌍의 두 task를 서로 다른 core에 배치했다. 세 ELF의 실제 symbol 주소와
같은/다른 line 관계는 `layout.json`으로 확인했다.

G/C/P와 공유/독립 조건의 6개 실행은 모두 exit 0, raw 재파싱
`execution_status=ok`, 오류 없음, 측정 job 720개·cohort 90개였다.
측정 job 안의 core 변경도 없었다. Architecture·조건당 실행은 1회다.

| 조건 | TET G / C / P (ms) | TAT G / C / P (ms) |
|---|---:|---:|
| 같은 line | 91.925 / 95.547 / 88.056 | 29.429 / 29.620 / 26.828 |
| 독립 line | 84.656 / 83.657 / 79.857 | 27.861 / 26.593 / 23.266 |
| 같은 line의 증가율 | +8.59% / +14.21% / +10.27% | +5.63% / +11.38% / +15.31% |

같은 line 조건에서 reader TET의 증가분은 G/C/P 각각
7.554/13.715/9.019 ms이며 writer TET는 각각
0.285/1.825/0.820 ms 감소했다. 측정된 쌍 360개 중 reader와 writer가
다른 core에서 시작한 수는 같은 line 조건에서 G 328개, C/P 각 360개다.
P의 마지막 완료 task는 두 조건 모두 매 cohort에서 writer 3이었다.
Reader 실행시간 증가가 뒤따르는 writer의 완료도 늦출 수 있으므로,
TAT 증가를 writer의 CPU 시간 증가로 해석하지 않는다.

같은 line 조건의 G/P TET·TAT 격차는 4.39%·9.69%로,
독립 line 조건의 6.01%·19.75%보다 작다. 공유 line 접근은 이 입력의
TET/TAT를 높였지만 **G/P 차이를 극대화하지는 않았다**.
이 진단은 공유 쓰기를 지원하지 않는 현재 private-load 생성기 대신 별도
RTEMS workload source를 사용한다. `plan.json`의 기존
`locality_scope=one-cold-task-local-job`은 이 공유-memory 시나리오의
locality 분석에 적용되지 않는다. HARA/RF feature 적격성을 주장하거나
본 데이터셋 label로 사용하지 않는다. Cache miss·snoop counter는 측정하지
않았고, 반복 실행을 통한 격차 안정성도 아직 확인하지 않았다.

입력·빌드 snapshot·raw·집계는
`.cache/periodic-memory-gap-v1/false-sharing-paired-v1/`에 보존했다.
`summary.json`은 각 조건의 TET/TAT·역할별 CPU 시간·실제 core 분리를,
각 `prepared/manifest.json`은 source·ELF hash를 기록한다. 새 경로에 재생하려면
workspace에서 다음을 실행한다.

```sh
PYTHONPATH=. DISPLAY=165.246.44.80:90.0 python3 -u \
  .cache/configs/periodic-memory-gap/false-sharing/run.py \
  --output .cache/periodic-memory-gap-v1/false-sharing-replay
```

## 균일 주기 공유 라인 비교 (2026-09-27 완료)

8 task·reader/writer 4쌍의 접근 코드(128 line × 8 sweep/job)와 코어당
2 task인 P 배치를 고정하고, 모든 task의 주기를 각각 5, 25, 100, 500 ms로
맞춘 네 조건을 실행한다. 조건마다 같은 line과 독립 line의 G/C/P를 비교한다.
설정은 `.cache/configs/periodic-memory-gap/false-sharing/uniform-p{5,25,100,500}.json`에
있다. 각 task는 8 job을 실행하고 첫 2개를 warm-up으로 제외하므로 실행당
48개 job·6개 nominal-release cohort가 측정된다. 조건별 주기만 달라지고
job당 접근 코드와 측정 job 수는 같다. 이는 1차 진단으로, 각 조건의 1회 실행과
6개 측정 job/task로 통계적 worst-case나 격차 안정성을 주장하지 않는다.

4개 주기 × 2개 line 조건 × G/C/P의 24회 실행이 모두 성공했고,
`supervisor.exit=0` 및 raw 재파싱으로 각 실행의 오류 없음·48개 측정 job·
6개 cohort를 확인했다. 단위는 ms이며 TET/TAT는 측정 구간의 합계다.

| 주기 | line 조건 | TET G / C / P | TAT G / C / P |
|---:|---|---:|---:|
| 5 | 공유 | 6.172 / 6.448 / 5.890 | 1.969 / 2.003 / 1.796 |
| 5 | 독립 | 5.744 / 5.659 / 5.320 | 1.909 / 1.796 / 1.551 |
| 25 | 공유 | 6.152 / 6.448 / 5.886 | 1.981 / 1.998 / 1.794 |
| 25 | 독립 | 5.694 / 5.672 / 5.323 | 1.870 / 1.788 / 1.547 |
| 100 | 공유 | 6.171 / 6.430 / 5.884 | 1.994 / 1.967 / 1.793 |
| 100 | 독립 | 5.722 / 5.687 / 5.320 | 1.911 / 1.797 / 1.548 |
| 500 | 공유 | 6.152 / 6.424 / 5.889 | 1.973 / 1.989 / 1.796 |
| 500 | 독립 | 5.739 / 5.671 / 5.316 | 1.928 / 1.828 / 1.551 |

공유 line의 G/P 격차는 TET 4.47–4.88%, TAT 9.61–11.24%이며
C/P 격차는 각각 9.09–9.54%, 9.74–11.53%다. 이 1회 예비측정에서는
주기가 길수록 격차가 커지는 추세가 보이지 않았으며, 반복 검증 전 결론을
보류한다. 공유 line의 관측 최대 cohort TAT는 주기 순서대로
G 361/361/353/355 µs, C 346/364/347/371 µs, P 322/320/319/322 µs다.
독립 line의 G/P TAT 격차는 20.87–24.31%로 오히려 크다.

Supervisor 로그·PID·종료 코드는
`.cache/periodic-memory-gap-v1/false-sharing-uniform-sweep-v1/`에 있다.
각 조건의 빌드 snapshot·raw·집계는
`.cache/periodic-memory-gap-v1/false-sharing-uniform-p{주기}-v1/`에 저장한다.
혼합 주기 조건은 별도 실행하며 이 균일 주기 집계에는 포함하지 않는다.

## 균일 주기 표본 확대 (2026-09-27 예약)

예비측정의 태스크당 측정 6 job·독립 실행 1회는 변동이나 관측 최대치를
판단하기에 부족하다. [측정 계약 v3](../../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT-V3.md)의
공통 주기 시작값에 맞춰 주기별 동일한 8-task 입력을 **warm-up 20 job + 측정
200 job/task**, 독립 실행 **5회**로 다시 측정한다. 네 주기 × 공유/독립 line ×
G/C/P의 총 120개 simulator 실행이며, 한 실행의 측정 job은 1,600개·
cohort는 200개다. 같은 repeat 번호의 공유/독립 line 결과를 paired 비교하고,
G/C/P의 run별 TET/TAT 합의 median과 관측 최대 cohort TAT를 기록한다.
시뮬레이터 반복값이 같으면 확률적 표본으로 과장하지 않으며,
관측 최대치 역시 보장된 WCET/WCRT가 아니다.

설정은 `.cache/configs/periodic-memory-gap/false-sharing/uniform-p{5,25,100,500}-full.json`에
있다. 혼합 주기 supervisor 종료 후 시작하도록 대기 중인 실행기의 로그·PID·
종료 코드는 `.cache/periodic-memory-gap-v1/false-sharing-uniform-full-sweep-v1/`에,
각 주기의 snapshot·raw·집계는
`.cache/periodic-memory-gap-v1/false-sharing-uniform-p{주기}-full-v1/`에 둔다.

## 혼합 주기 공유 라인 비교 (2026-09-27 시작)

[`mixed-periods.json`](../../../.cache/configs/periodic-memory-gap/false-sharing/mixed-periods.json)은
reader/writer 6쌍에 각각 5·8, 20·50, 500·1000 ms를 배정한 12-task
입력이다. 같은 쌍의 두 task는 같은 주기와 같은 작업 코드를 쓰고, P는
코어당 3 task로 균형을 맞춘다. 3초 공통 관측 구간에서 첫 1초를
warm-up으로 제외하므로 주기별 task당 측정 job 수는 차례대로
400·250·100·40·4·2개다. 공유/독립 line 각각에 대해 G/C/P를 실행한다.
TET/TAT 합계는 고속 task의 job이 크게 지배하므로 주기별 job TET·응답시간과
관측 최대 주기 TAT도 `summary.json`에 기록한다. 저속 task의 표본 수는
작아 독립적인 worst-case 경계로 해석하지 않는다.

입력·빌드 snapshot·raw·집계는
`.cache/periodic-memory-gap-v1/false-sharing-mixed-period-v2/`에,
진행 로그·PID·종료 코드는 같은 디렉터리의 `supervisor.*`에 둔다.

## L1 cache set 점유 통제 실험 (2026-09-27 완료)

태스크 수만 바꾸면 이용률과 동시 실행 수도 함께 바뀌므로, **같은 태스크 수
안에서 배열 정렬만 바꾼 쌍**을 비교한다. 모든 태스크는 고유한 2 KiB 배열의
64개 캐시 라인을 48회 순회하며 job당 3,072번 읽는다. 4개 코어에 태스크를
같은 수로 배치하고, 각 태스크는 warm-up 20 job과 측정 180 job을 실행한다.
16태스크의 주기는 4 ms, 20태스크는 5 ms이므로 코어당 계획된 접근률은
둘 다 3,072회/ms다. 각 조건에서 G/C/P의 TET·TAT와 job별 CPU 시간,
응답시간·시작 코어 변경을 기록한다.

| 태스크/코어 | 배열 정렬 | 코어당 태스크 데이터 | 실제 ELF 주소의 set당 데이터 라인 수 |
|---:|---:|---:|---|
| 4 | 4 KiB 간격 | 8 KiB | 64개 set에 각 4라인, 나머지 64개는 0라인 |
| 4 | 32 B 밀집 | 8 KiB | 128개 set에 각 2라인 |
| 5 | 4 KiB 간격 | 10 KiB | 64개 set에 각 5라인, 나머지 64개는 0라인 |
| 5 | 32 B 밀집 | 10 KiB | 64개 set에 각 2라인, 나머지 64개는 각 3라인 |

GR740 L1D의 32 B line·128 set·4 way 기준이다. 16태스크의 간격 배치는
사용 데이터만으로 해당 set의 4 way를 채우고, 20태스크는 4 way를 넘는다.
반면 밀집 배치는 같은 작업량과 총 데이터 크기로 set당 최대 2·3라인이다.
동일 태스크 수의 두 C 소스는 배열의 `aligned(4096)`/`aligned(32)` 선언만
다르고 G/C/P ELF에서 해당 배열 주소가 같음을 확인했다. 이 정적 집계는
태스크 배열만 포함하며 RTEMS·스택 등의 점유나 실제 cache miss 수는
측정하지 않는다. 16태스크와 20태스크 간 TET/TAT 절댓값을 같은 workload의
효과로 해석하지 않고, 각 태스크 수 안에서 배치 쌍을 비교한다.

설정 생성·실행기는
`.cache/configs/periodic-memory-gap/l1-set-pressure/run.py`이며, 준비된
빌드와 set 점유 검사 `set_pressure.json`, raw, 결과 `summary.json`은
`.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n{16,20}-{spaced,compact}/`에
둔다. 진행 상황은 다음 명령으로 볼 수 있다.

```sh
tail -f .cache/periodic-memory-gap-v1/l1-set-pressure-v1/supervisor.log
```

4개 조건의 G/C/P 총 12회가 모두 정상 종료했고 `supervisor.exit=0`이다.
각 정책 실행마다 16태스크 조건은 측정 job 2,880개·cohort 180개,
20태스크 조건은 측정 job 3,600개·cohort 180개를 raw 재파싱으로 확인했다.
단위는 ms이며 TET/TAT는 측정 구간의 합계다.

| 태스크 수 | 배열 배치 | TET G / C / P | TAT G / C / P | G/P 격차 TET / TAT |
|---:|---|---:|---:|---:|
| 16 | 4 KiB 간격 | 889.734 / 883.826 / 885.264 | 249.774 / 240.290 / 235.463 | 0.51% / 6.08% |
| 16 | 32 B 밀집 | 885.960 / 875.156 / 865.342 | 248.851 / 237.934 / 230.141 | 2.38% / 8.13% |
| 20 | 4 KiB 간격 | 1114.031 / 1109.356 / 1108.976 | 311.027 / 302.167 / 296.080 | 0.46% / 5.05% |
| 20 | 32 B 밀집 | 1111.485 / 1101.886 / 1091.856 | 314.001 / 300.239 / 291.927 | 1.80% / 7.56% |

같은 태스크 수에서 밀집 배치가 P의 TET를 간격 배치 대비 16태스크 2.25%,
20태스크 1.54% 줄였지만 G의 감소는 각각 0.42%, 0.23%였다. G/P 격차도 두
태스크 수에서 모두 밀집 배치가 더 컸다. G의 연속 측정 job 간 시작 코어
변경은 16태스크 1,788–1,840/2,864회, 20태스크 2,165–2,456/3,580회였고
P는 0회다. 이는 배치와 코어 이동의 관련성을 보여주는 진단 결과이며,
조건당 독립 실행은 1회이고 L1 miss를 직접 세지 않았다. 따라서 L1 상주나
성능 격차의 안정성을 입증한 결과로 해석하지 않는다.
