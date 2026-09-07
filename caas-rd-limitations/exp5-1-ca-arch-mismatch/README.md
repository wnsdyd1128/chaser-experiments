# Exp5-1: CA Metric Architecture Mismatch

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

`exp5-1-ca-arch-mismatch`는 [exp3](../exp3-ca-metric/README.md)이 보인 CA 지표의
한계가 스케줄링 아키텍처 선택을 실제로 그르치는지 측정한다.
[exp2](../exp2-task-interference/README.md)와 실험 골격은 같다. 8개 주기 태스크를
4코어 GR740에서 `ALONE` / `GLOBAL` / `PARTITIONED` 세 case로 돌리고, 각 job을
`rtems_clock_get_uptime_nanoseconds()`로 감아 laysim에서 실측한다. 초점만
다르다. exp2는 feature에 아예 없는 정보(간섭)를 문제 삼았고, exp5는 feature에
있는 정보(CA)가 캐시 현실과 어긋나 있음을 문제 삼는다.

태스크 셋은 victim 4개와 polluter 4개다. polluter는 전 case에서 32 KiB로
고정한다. L1이 16 KiB이므로 polluter의 job 한 번이 victim이 들고 있을 수 있는
모든 라인을 밀어낸다. victim은 case마다 접근 패턴만 바꾼다.

여덟 태스크는 우선순위와 주기(1 tick)가 같고 job은 주기보다 훨씬 짧다. 그래서
release 시점에 실행 중인 job이 선점당하지 않으며, 측정창에는 co-runner의 CPU
시간이 아니라 실행 시간만 들어간다. `PARTITIONED`는 cache-affinity-aware
배치다. victim은 core 0, 1에 두 개씩, polluter는 core 2, 3에 두 개씩 고정해
victim이 polluter와 코어를 공유하지 않게 한다. `GLOBAL`은 affinity를 설정하지
않는다. 실제 배치는 태스크마다 `cpu_mask`로 함께 기록되므로 가정이 아니라
확인 대상이다.

## CA를 footprint에서 분리하는 방법

순환 sweep의 CA는 `1 / distinct`이고 stride와 무관하다
([exp3](../exp3-ca-metric/README.md)의 닫힌 형식).
반면 캐시가 보는 것은 그 주소들이 차지하는 **라인 수**다. 따라서 `distinct`를
고정한 채 stride만 바꾸면 CA는 한 치도 움직이지 않으면서 footprint가 32배
달라진다. 케이스 이름의 접두사가 그 구분이다.

- `P` (packed): stride 1 B. 주소 32개가 캐시 라인 하나를 공유한다.
- `F` (full stride): stride 32 B. 주소마다 캐시 라인 하나를 차지한다.

sweep은 두 축을 걷는다. victim footprint(2 KiB ~ 24 KiB)와 태스크 수(8, 12,
16개). 태스크 수는 `EXP5_VICTIMS`/`EXP5_POLLUTERS`로 정하며, 고정 배치에서 한
코어를 나눠 쓰는 victim 수를 바꾸므로 "쌍이 L1에 들어가는가"의 기준도 함께
움직인다.

| case | distinct | stride | victim footprint | L1 lines | tasks | CA |
|---|---:|---:|---:|---:|---:|---:|
| P064 / F064 | 64 | 1 B / 32 B | 64 B / 2 KiB | 2 / 64 | 8 | 1.56e-2 |
| P096 / F096 | 96 | 1 B / 32 B | 96 B / 3 KiB | 3 / 96 | 8 | 1.04e-2 |
| P128 / F128 | 128 | 1 B / 32 B | 128 B / 4 KiB | 4 / 128 | 8 | 7.81e-3 |
| P192 / F192 | 192 | 1 B / 32 B | 192 B / 6 KiB | 6 / 192 | 8 | 5.21e-3 |
| P256 / F256 | 256 | 1 B / 32 B | 256 B / 8 KiB | 8 / 256 | 8 | 3.91e-3 |
| F384 | 384 | 32 B | 12 KiB | 384 | 8 | 2.60e-3 |
| F768 | 768 | 32 B | 24 KiB | 768 | 8 | 1.30e-3 |
| P128T12 / F128T12 | 128 | 1 B / 32 B | 128 B / 4 KiB | 4 / 128 | 12 | 7.81e-3 |
| P096T16 / F096T16 | 96 | 1 B / 32 B | 96 B / 3 KiB | 3 / 96 | 16 | 1.04e-2 |

각 쌍의 두 케이스는 CA가 소수점까지 같고 측정된 standalone U도 2% 안에서
같다(예: `P128` 0.0188 대 `F128` 0.0190). CAAS가 읽는 입력이 같다는 뜻이다.

## 실행

```sh
tools/run_exp5_1_sweep.sh
tools/summarize_exp5_1.py
tools/plot_exp5_1_collision.py
tools/plot_exp5_1_capacity.py
```

`run_exp5_1_sweep.sh`는 case마다 `EXP5_DEFS`로 다시 빌드해 laysim으로 돌리고
`parse_results.py`로 CSV를 만든다. `summarize_exp5_1.py`는 CA 닫힌 형식과 측정
U로 ML 입력 JSON을 만든 뒤 `tools/rtems_ml_predict.py`를 호출한다. 즉 예측
경로는 exp2와 같은 저장 모델 그대로다.

## 결과

RandomForest는 16개 case 전부에 `GLOBAL`을 예측한다. 그 답이 실제 최적 배치보다
얼마나 비싼지가 `RF costs`다. 6개 case에서 5% 판정 밴드를 넘는다.

| case | victim | tasks | CA | GLOBAL mean us | PART mean us | measured best | RF costs |
|---|---:|---:|---:|---:|---:|---|---:|
| F064 | 2 KiB | 8 | 1.56e-2 | 21.41 | 16.44 | PARTITIONED | **+30.3%** |
| F096 | 3 KiB | 8 | 1.04e-2 | 31.88 | 24.71 | PARTITIONED | **+29.0%** |
| F128 | 4 KiB | 8 | 7.81e-3 | 41.48 | 32.81 | PARTITIONED | **+26.4%** |
| F096T16 | 3 KiB | 16 | 1.04e-2 | 37.72 | 30.32 | PARTITIONED | **+24.4%** |
| F128T12 | 4 KiB | 12 | 7.81e-3 | 44.14 | 36.26 | PARTITIONED | **+21.7%** |
| F192 | 6 KiB | 8 | 5.21e-3 | 61.58 | 57.15 | PARTITIONED | **+7.8%** |
| P064 | 64 B | 8 | 1.56e-2 | 14.90 | 15.79 | GLOBAL | +0.0% |
| P096 | 96 B | 8 | 1.04e-2 | 17.17 | 24.58 | GLOBAL | +0.0% |
| P128 | 128 B | 8 | 7.81e-3 | 21.71 | 33.30 | GLOBAL | +0.0% |
| P192 | 192 B | 8 | 5.21e-3 | 30.65 | 51.75 | GLOBAL | +0.0% |
| P256 | 256 B | 8 | 3.91e-3 | 39.59 | 70.56 | GLOBAL | +0.0% |
| F256 | 8 KiB | 8 | 3.91e-3 | 81.77 | 86.35 | GLOBAL | +0.0% |
| F384 | 12 KiB | 8 | 2.60e-3 | 121.45 | 136.96 | GLOBAL | +0.0% |
| F768 | 24 KiB | 8 | 1.30e-3 | 375.11 | 369.09 | TIE | +1.6% |
| P128T12 | 128 B | 12 | 7.81e-3 | 25.62 | 33.24 | GLOBAL | +0.0% |
| P096T16 | 96 B | 16 | 1.04e-2 | 23.32 | 24.96 | GLOBAL | +0.0% |

모델이 손해를 보는 6개는 전부 spread 케이스다. 그리고 그 각각에는 CA와 U가
같은 packed 짝이 있고, 거기서는 같은 `GLOBAL` 답이 최적이다. 즉 모델이 맞은
쪽은 알아서 맞춘 것이 아니라, 구분할 수 없는 두 입력에 같은 답을 내놓아 한쪽만
우연히 맞은 것이다.

그림 두 장이 각각 다른 한계를 보여준다.

- `exp5_1_collision_bar` — CA가 같은 쌍 중 **모델이 가장 크게 손해 보는 쌍을
  태스크 수마다 하나씩** 골라 그린다(8, 12, 16 태스크). 쌍의 두 케이스는 CAAS
  입력이 같은데 선호 아키텍처가 반대다. 따라서 이것은 모델을 더 잘 학습시켜
  고칠 수 있는 문제가 아니다. `{CA, U}`만 입력으로 받는 어떤 스케줄러도 두
  태스크 셋을 구분할 수 없고, 둘 중 하나에서는 반드시 틀린다.
- `exp5_1_capacity_step` — 8-task의 stride 32 케이스만 그린다. CA는 12배에 걸쳐
  매끄럽게 떨어지는데, 측정된 결정은 pinned pair가 L1(512 lines)에 더는 들어
  가지 않는 지점에서 부호가 바뀐다. CA 축 위에는 그 계단이 없다.

## 그림 캡션

그림 안에는 데이터만 두고 설명은 캡션으로 옮겼다. 논문에 넣을 때 쓸 문장은
다음과 같다.

**Fig. (capacity step).** Capacity sensitivity of the CAAS feature, on the
eight-task sets. Bars give the measured gain of PARTITIONED over GLOBAL for the
victim tasks; the line gives CA. The advantage falls off as the pinned pair
approaches the 512-line L1 and turns to GLOBAL once it no longer fits (dashed
line), while CA falls smoothly by 12x across the sweep and carries no such step.
The RandomForest answers GLOBAL at every point. Case labels give the
configuration name and the victim footprint; F064 to F768 hold 64 to 768 cache
lines, so a pinned pair holds twice that against a 512-line L1.

**Fig. (collision).** One CAAS input, two answers, at three task-set sizes. The
two cases under a bracket touch the same number of distinct addresses, so CA is
identical and the measured standalone utilization agrees to within 2%; they
differ only in stride. A packed case puts 32 addresses in one cache line
(stride 1 B), a spread case one address per line (stride 32 B). The pairs drawn are P064 and F064 at
eight tasks, P128T12 and F128T12 at twelve, P096T16 and F096T16 at sixteen, which
are the rows of the table above. Bars are the victims' job execution time,
solid for the mean over the victims and hatched for the slowest of them. The
filled dot stands over the placement the measurement picked and the open ring
over the one CAAS predicted, so a misprediction reads as the two marks standing
over different bars and agreement as the dot centred inside the ring. The red figure is
what the prediction costs against the measured best: 21.7% to 30.3% on the
spread member of each pair and nothing on its packed twin. The model is not
right on the twin, it cannot tell the two apart and lands on one of them.

차이의 출처는 분해된다. `GLOBAL`에서 `F128`의 victim은 `P128`보다 19.8 us
느린데, 이는 job마다 128개 라인을 다시 채우는 비용이다(`P128`은 4개 라인이라
같은 비용이 0에 가깝다). `PARTITIONED`에서는 32.8 us와 33.3 us로 같아진다.
배치가 refill을 없앤 대신, polluter를 두 코어에 몰아 생기는 공유 자원 중첩
비용을 모두에게 물린다. 그래서 지킬 라인이 많은 쪽은 이득이고 없는 쪽은
손해다. CA는 이 라인 수를 세지 않는다.

태스크 수를 8에서 12, 16으로 늘려도 실패는 사라지지 않는다. 고정 배치에서 한
코어를 나눠 쓰는 victim이 2개에서 3개, 4개로 늘어나므로 "쌍이 L1에 들어가는
가"의 문턱만 내려갈 뿐이고, 그 문턱 아래에 있는 spread 케이스에서는 여전히
`PARTITIONED`가 21~24% 낫다.

측정된 최적 아키텍처는 CA에 대해 단조롭지도 않다. 8-task 계열의 CA를 큰 값부터
훑으면 PARTITIONED(P/F 쌍에서 각각 GLOBAL/PARTITIONED), ... , GLOBAL 순으로
뒤집히며, CA 축 위의 어떤 단일 임계값도 이 순서를 만들어낼 수 없다.

## 읽는 법과 범위

판정은 victim 기준이다. victim은 배치로 보호하려는 대상이고, real-time 관점의
deadline 위험도 여기서 나온다. 태스크 셋 전체를 평균하면 결론이 달라져서
`PARTITIONED`가 16개 case 전부에서 7.9~33.9% 낫다. polluter를 두 코어로 몰면
서로 주는 shared-L2 압력이 절반이 되기 때문이다. 이 이득 역시 `{CA, U}`에는
없는 정보이므로, 전체 기준으로 읽으면 RandomForest는 16개 case 전부에서
틀린다. 두 관점 모두 `results/exp5_1_arch_mismatch.md`에 있다.

RF 모델 자체의 응답 범위도 확인했다. 동종 태스크 셋에서 예측이 바뀌는 지점은
CA 0.0625와 0.125 사이, 즉 mean RD 8~16 addresses다. GR740의 L1 경계는
512 lines이므로 두 스케일은 250~500배 어긋나 있다. U는 0.005~0.9 전 구간에서
예측을 바꾸지 못했고, 저CA 태스크가 하나라도 섞인 셋은 항상 `GLOBAL`이었다.
학습 데이터의 CA 범위가 0.00234~0.99라 exp3, exp5가 다루는 영역은 그 아래다.

laysim 실행은 결정적이다. 같은 바이너리를 다시 돌리면 `RESULT` 라인이 전부
같은 값으로 나오는 것을 확인했다. 표의 1.6% 같은 작은 차이는 재현되는 값이지
잡음이 아니지만, 아키텍처 선호로 읽기에는 작아서 5% 이내는 `TIE`로 판정한다.

바이너리가 달라지면 절대값은 조금 움직인다. job 함수를 태스크마다 하나씩 두던
구조를 인덱스 호출로 바꾼 리팩터 전후로 spread 케이스는 1% 안에서 같았지만
(`F128` GLOBAL 41.8 -> 41.5 us), packed 케이스는 코드 배치에 민감해 더 움직였다
(`P128` GLOBAL 26.2 -> 21.7 us). 데이터가 4 라인뿐이라 명령어 경로가 시간을
지배하기 때문이다. 방향과 판정은 두 빌드에서 같았다.

결과는 다음에 기록된다.

```text
results/exp5_1_<case>.log / .csv                laysim 원본과 파싱 결과
results/exp5_1_ml_dataset.json                  CAAS 모델 입력 {CA, U}
results/exp5_1_arch_mismatch.csv / .md          case별 요약과 판정
results/exp5_1_collision_bar.png / .pdf          CA가 같은 쌍의 반대 결론
results/exp5_1_capacity_step.png / .pdf          CA는 연속, 결정은 계단
```
