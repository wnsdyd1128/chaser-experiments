# Exp3: CA Metric Saturation

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

`exp3-ca-metric`은 캐시 간섭 없이 CA 지표 자체의 한계를 보이기 위한 실험이다.
단일 태스크가 `distinct`개의 서로 다른 주소를 cache-line 간격으로 순환
접근하고, 그 순환을 `sweeps`번 반복한다.

이 접근 패턴에서는 재사용 히스토그램이 `RD = distinct - 1` 한 점으로 축약되므로
CA가 닫힌 형식으로 떨어진다. 따라서 수백만 접근 트레이스에 reuse-distance
analyzer를 돌리지 않고도 CA를 정확히 계산할 수 있다.

```text
CA(D) = 1 / D
```

접근은 store 없는 순수 read다. store를 섞으면 그 직후 재사용이 `RD = 0` 점을
만들어 식이 `(2S - 1) / ((2S - 1) + (D - 1)(S - 1))`로 복잡해지는데, 얻는 것이
없다. store는 명령어 10 사이클을 쓰면서 메모리 stall은 만들지 않고(GR740 L1이
write-through이고 store buffer가 흡수한다), 비용 축이 이미 read miss rate를
보고 있어 정의도 어긋난다. CA counting은 cache-line이 아니라 **주소 단위**이며,
이는 CAAS 논문의 계산 방식을 따른 것이다.

비용은 두 경로로 측정한다. 둘 다 바이너리가 스스로 재지 않는다.

```sh
# miss rate 축: 호스트 빌드에 GR740 캐시 형상을 강제한 cachegrind
make -C exp3-ca-metric
tools/run_cachegrind_sweep.sh
tools/plot_ca_saturation.py

# 시간 축: GR740 타깃 빌드를 laysim에서 실행
make -f Makefile.rtems -C exp3-ca-metric
script -q -c "make -f Makefile.rtems -C exp3-ca-metric run" results/exp3_time_domain.log
tools/parse_results.py results/exp3_time_domain.log -o results/exp3_time_domain.csv
tools/plot_ca_saturation.py --axis ns
tools/plot_ca_saturation.py --axis stall
```

GR740은 코어당 L1 16 KiB, 공유 L2 2 MiB이며 둘 다 4-way / 32 B line이다.
`ACCESSES`는 케이스마다 고정한다. 그래야 프로세스 시작 트래픽과 cold miss
비중(`1/sweeps`)이 working set 사이에서 비교 가능한 상태로 유지된다.
케이스 목록은 cachegrind 쪽은 `DISTINCT_LIST` 환경 변수로, RTEMS 쪽은
`-DEXP3_DISTINCT_LIST=` 컴파일 플래그로 덮어쓴다. 후자는 한 케이스를 갓 부팅한
머신에서 단독 재실행해 배치 결과와 대조할 때 쓴다.

## 시간 축 지표의 정의

플롯의 `Average time per array access`는 다음과 같이 계산한다. 루프는 반복마다
load 하나만 내보내고 store는 없으므로, load 횟수와 반복 횟수가 같은 수다.

```text
D = distinct,  S = sweeps = floor(ACCESSES / D),  J = EXP3_JOBS = 3
T_j = job j 의 측정 시간

average time per array access = (sum_j T_j) / (J * D * S)
```

`T_j`는 `sweep()` 호출 전체를 감싼 벽시계 시간이고, 그 안에는 안쪽 루프 `D*S`회,
바깥 루프 `S`회, 그리고 그 구간에 뜬 인터럽트가 전부 들어간다. `RESULT` printf와
부팅·`.bss` 0채우기는 창 밖이라 들어가지 않는다. 분모는 `buf[]` read만 센다.

**이 값은 메모리 지연시간이 아니다.** 분모가 접근 1개인데 분자는 안쪽 루프
13개 명령어 전부를 담는다. `-O0`이라 루프 변수가 스택에 있어 반복마다 다시
읽히기 때문이다. 그래서 L1 구간에서도 68 ns(17 사이클)가 나온다. 이 상수는
16개 케이스가 같은 명령어 시퀀스를 돌기 때문에 모두에게 동일하게 붙으며,
계단 위치와 계층 내부 평탄성은 건드리지 않고 계단 **비율만 압축한다**.

`--axis stall`은 그 상수를 뺀 축이다. L1 상주 케이스에서 `floor(D) = a + b/D`를
피팅해 빼며, `b/D` 항은 sweep마다 한 번 치르는 바깥 루프 비용이다.

## 읽는 법

CA는 D에 반비례해 단조 감소하지만 실측 비용은 L1(16 KiB)과 L2(2 MiB) 경계에서만
계단식으로 변한다. 같은 계층 안의 두 워크로드는 CA가 수십~수백 배 차이나도
실측이 동일하다.

| working set | 계층 | CA | laysim ns/load | stall | cachegrind |
|---:|---|---:|---:|---:|---|
| 4~12 KiB | L1 | 7.8e-3 ~ 2.6e-3 | 68.3 ~ 68.8 | 0.0 | L1 miss 0.0% |
| 16 KiB | L1 경계 | 2.0e-3 | 69.4 | 1.2 | L1 miss 0.0% |
| 24 KiB ~ 1.5 MiB | L2 | 1.3e-3 ~ 2.0e-5 | 120.4 ~ 120.6 | 52.2 ~ 52.5 | L1 miss 99.6% |
| 2 MiB | L2 경계 | 1.5e-5 | 121.3 | 53.2 | L1 miss 99.6% |
| 3 ~ 32 MiB | RAM | 1.0e-5 ~ 9.5e-7 | 292.805 ~ 292.808 | 224.7 | L2 miss 99.6% |

계층 내부에서 CA는 85배(L2), 10배(RAM) 갈라놓는데 실측 시간 차이는 각각 1%,
0.001%다. 반대로 두 캐시 경계에서 CA는 각각 1.5배씩만 움직이는데 stall은
0 -> 52.2 -> 224.7 ns로 뛴다. 결과는 다음에 기록된다.

```text
results/exp3_ca_saturation.csv                  cachegrind miss rate
results/exp3_time_domain.log / .csv             laysim 원본과 파싱 결과
results/exp3_ca_saturation[_ns|_stall].png/pdf         곡선
results/exp3_ca_saturation[_ns|_stall]_ratios.png/pdf  계층 내 쌍 비율
```

## 측정 경로 제약

두 경로가 재는 것이 다르다. cachegrind는 SPARC 바이너리가 아니라 같은 접근
패턴을 갖는 호스트 빌드를 실행한다. 이전되는 것은 접근 패턴과 명령줄로 강제한
캐시 형상이고, SPARC ISA와 메모리 컨트롤러 타이밍은 이전되지 않는다. 또한
cachegrind는 last-level cache를 단일 캐시로 모델링하므로 L2를 4코어가
공유한다는 사실이 반영되지 않는다. exp3은 단일 태스크 실험이라 여기서는 문제가
되지 않지만, 간섭 변형을 만들 때는 문제가 된다.

laysim 측정은 16개 케이스를 각각 갓 부팅한 머신에서 단독 실행한 값이다. 한
번에 이어 돌리면 직전 케이스가 L2에 남긴 데이터가 다음 케이스의 첫 sweep을
빠르게 만든다. 실제로 배치 실행에서 D=98304(3 MiB)만 0.134% 빨랐고, 단독
실행하면 RAM 평탄면에 정확히 올라앉는다.

stall 축은 L1 히트 기준 **상대값**이지 절대 지연시간이 아니다. floor에 L1 히트
비용이 이미 포함돼 있다. 또한 stride-32 순차 접근이라 메모리 시스템이 미스를
겹쳐 처리할 수 있으므로, 이 값은 지연시간이 아니라 처리율에 가깝다. 진짜
지연시간을 재려면 pointer chase가 필요하고, 순환 체인이면 `RD = D - 1`이
보존되므로 CA 모델은 그대로 쓸 수 있다.

[exp1](../exp1-cache-hierarchy/README.md)의 독립 측정과 교차 확인된다. exp1은 RMW 워크로드라 절대값이 40 ns
높지만(store 명령어 몫), 계단 위치와 평탄성이 일치한다.

| working set | 계층 | exp1 ns/access (RMW) | exp3 ns/load (load-only) |
|---:|---|---:|---:|
| 8 KiB | L1 | 108.676 | 68.456 |
| 24 KiB | L2 | 160.508 | 120.474 |
| 512 KiB | L2 | 160.398 | 120.359 |
| 1.5 MiB | L2 | 160.394 | 120.627 |

exp1 값은 `avg_ns / (working_set / 32 * EXP1_SWEEPS)`로 환산했으며
`EXP1_SWEEPS`는 256이다.
