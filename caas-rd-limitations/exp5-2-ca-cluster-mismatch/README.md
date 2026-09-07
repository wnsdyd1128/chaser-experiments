# Exp5-2: CA Metric Cluster Mismatch

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

`exp5-2-ca-cluster-mismatch`는 [exp5-1](../exp5-1-ca-arch-mismatch/README.md)의
한계를 `CLUSTERED` 아키텍처까지 확장한다. exp5-1은 job 실행시간으로 `GLOBAL`과 `PARTITIONED`를 갈랐다.
클러스터의 이점은 실행시간에 안 잡힌다. 같은 코어에 고정된 co-runner 뒤에서
기다리는 시간은 job 실행 창 밖이기 때문이다. 그래서 이 실험의 판정 지표는
**응답시간**(release -> 완료)이다.

태스크 셋은 victim 4개와 polluter 4개다. victim은 heavy job과 light job을
번갈아 실행하며, victim 0, 1은 위상 0, victim 2, 3은 위상 1이다. 즉 매 release
마다 정확히 두 개가 heavy다. 평균을 내면 넷이 동일하고, U가 보는 것은 그
평균뿐이다. victim의 주기는 1 tick, polluter는 4 tick이라 EDF에서 victim의
deadline이 더 이르고 polluter를 선점한다.

비교하는 배치는 넷이다.

- `GLOBAL`: affinity 없음. victim이 네 코어 아무 데나 가고, 그 코어는 방금
  polluter가 지나간 자리다.
- `PARTITIONED`: 태스크마다 코어 하나. victim은 core 0~2, polluter는 core 3.
  victim 0과 1이 같은 코어를 쓰는데 둘은 같은 위상이라 heavy job이 겹친다.
- `PARTITIONED_ALT`: 같은 아키텍처, 짝만 위상 교차로 바꾼 것.
- `CLUSTERED`: scheduler instance 두 개. 클러스터 A가 core 0~2와 victim을,
  클러스터 B가 core 3과 polluter를 갖는다. victim은 A 안에서 자유롭게
  이동한다.

## 측정 경로에서 확인한 두 가지

**클러스터는 affinity mask로 만들 수 없다.** RTEMS EDF SMP는 one-to-one 또는
전체 집합만 받는다. 코어 두 개짜리 mask를 주면 `rtems_task_set_affinity`가
`RTEMS_INVALID_NUMBER`(10)를 돌려주고 태스크는 네 코어를 그대로 쓴다. 실제로
`cpu_mask`가 15로 찍히는 것을 확인했다. 그래서 클러스터는 scheduler instance
두 개로 구성하며, 프로세서는 부팅 시점에 인스턴스 하나에 귀속되므로
`CLUSTERED`는 별도 바이너리다. `EXP5C_CLUSTERED=1`로 빌드한다.

**두 클럭을 섞어 release 시각을 재구성할 수 없다.** tick 카운터와 uptime
클럭은 이 시뮬레이터에서 같은 속도로 가지 않는다. `uptime_ns - ticks * 1 ms`가
32 ms 동안 최대 -542 us까지 벌어지는 것을 측정했다. 따라서 응답시간은 RTEMS의
rate monotonic 통계에서 가져온다. `rtems_rate_monotonic_get_statistics()`의
wall time은 커널이 CLOCK_MONOTONIC으로 잰 release -> 다음 period 호출 구간이다.
job 실행시간만 `rtems_clock_get_uptime_nanoseconds()`로 직접 잰다.

## 케이스

[exp5-1](../exp5-1-ca-arch-mismatch/README.md)과 같은 방식으로 CA를
footprint에서 분리한다. `distinct`가 같으므로
CA도 같고, stride만 32배 다르다.

| case | distinct | stride | victim footprint | L1 lines | CA | U |
|---|---:|---:|---:|---:|---:|---:|
| CP128 | 128 | 1 B | 128 B | 4 | 7.81e-3 | 0.0411 |
| CV128 | 128 | 32 B | 4 KiB | 128 | 7.81e-3 | 0.0411 |

## 실행

```sh
tools/run_exp5_2_sweep.sh
tools/summarize_exp5_2.py
tools/plot_exp5_2_cluster.py
```

case마다 flat 바이너리와 clustered 바이너리를 각각 빌드해 laysim으로 돌린 뒤
두 로그를 합쳐 요약한다.

## 결과

| case | victim | GLOBAL mean us | PARTITIONED mean us | CLUSTERED mean us | measured best | RF | RF costs |
|---|---:|---:|---:|---:|---|---|---:|
| CP128 | 128 B (4 lines) | 91.80 | 98.80 | 88.87 | CLUSTERED | Global | +3.3% |
| CV128 | 4 KiB (128 lines) | 107.60 | 101.46 | 97.51 | CLUSTERED | Global | +10.3% |

`CV128`에서 최적은 `CLUSTERED`이고, RandomForest가 고른 `GLOBAL`은 victim
응답시간을 10.3% 더 쓴다. 같은 CA, 같은 U를 갖는 `CP128`에서는 `GLOBAL`이
3.3% 차이로 판정 기준(5%) 안에 들어와 모델이 우연히 맞는다. 즉 클러스터가 필요한
태스크 셋과 필요 없는 태스크 셋이 CAAS 입력에서 구분되지 않는다.

이유는 job 실행시간 평균이 보여준다.

| case | exec: GLOBAL | exec: PARTITIONED | exec: CLUSTERED |
|---|---:|---:|---:|
| CP128 | 50.3 us | 50.0 us | 48.3 us |
| CV128 | 63.9 us | 51.0 us | 55.3 us |

`CV128`에서 `GLOBAL`은 job마다 128개 라인을 다시 채우느라 12.9 us를 더 쓴다.
`PARTITIONED`는 그 비용을 없애지만 같은 위상의 victim 둘을 한 코어에 묶어
heavy job을 직렬화한다. `CLUSTERED`는 캐시 온기의 대부분을 유지하면서 그
직렬화를 피하는 중간값이라서 응답시간이 가장 낮다. `CP128`에서는 지킬 라인이
4개뿐이라 온기가 값을 갖지 않고, 세 배치의 실행시간이 같아진다.

## 그림 캡션

그림 안에는 데이터만 두고 설명은 캡션으로 옮겼다. 논문에 넣을 때 쓸 문장은
다음과 같다.

**Fig. (cluster).** The same blindness at the clustered architecture. Bars give
the mean victim response time, release to completion, taken from the RTEMS
rate-monotonic statistics, so they carry both the cache state of the job and the
queueing its placement causes. The two cases carry the same CA and the same U
and differ only in stride: the packed case CP128 puts 32 addresses in one cache
line (stride 1 B), the spread case CV128 one address per line (stride 32 B). The filled dot
stands over the placement the measurement picked and the open ring over the one
CAAS predicted; the figure above each group is what that prediction costs
against the measured best. CLUSTERED is the measured best in both, but the cost of the
model's GLOBAL grows from 3.3% to 10.3% once a victim holds 128 cache lines
instead of 4. PARTITIONED_alt is the same partitioned architecture with the
victims paired across phases; nothing in {CA, U} distinguishes it from
PARTITIONED.

## 읽는 법과 범위

`PARTITIONED_ALT`는 같은 아키텍처에서 짝만 위상 교차로 바꾼 것이다. 평균
응답시간은 `PARTITIONED`와 거의 같고(98.2 / 101.6 us) 최악값에서만 낫다.
중요한 것은 값이 아니라, 어느 짝이 옳은지가 위상에 달려 있고 위상은 어떤
CAAS feature에도 없다는 점이다. victim 넷은 CA도 U도 같다.

최악 응답시간은 표에 함께 기록하지만 판정에 쓰지 않는다. 128 release 중 드물게
victim의 절대 deadline이 실행 중인 polluter의 그것보다 뒤에 놓이는 release가
있고, 그 EDF 특성이 최악값을 지배한다. 배치의 성질이 아니다.

한 바이너리 안에서 laysim은 결정적이지만, 코드 배치가 바뀌면 값이 1% 안팎으로
움직인다. 모듈 분리 리팩터링 전후로 평균 응답시간이 0.2~0.9 us 달라지는 것을
확인했다. 결론(최적 배치와 RF의 손해 폭)은 바뀌지 않는다.

응답시간 절대값에는 계측 상수가 들어 있다. 단독 실행에서 응답시간이 실행시간
보다 약 22 us 크다. RTEMS가 재는 구간이 release부터 다음 period 호출까지라
job 앞뒤의 클럭 읽기와 루프가 포함되기 때문이다. 이 상수는 모든 배치에 동일
하게 붙으므로 비교에는 영향이 없다.

결과는 다음에 기록된다.

```text
results/exp5_2_<case>.log / .csv                flat 빌드 원본과 파싱 결과
results/exp5_2_<case>_clustered.log / .csv      clustered 빌드 원본과 파싱 결과
results/exp5_2_ml_dataset.json                  CAAS 모델 입력 {CA, U}
results/exp5_2_cluster_mismatch.csv / .md       case별 요약과 판정
results/exp5_2_cluster_bar.png / .pdf           배치별 평균 응답시간
```
