# Exp1: Cache Hierarchy

standalone RD/CA가 L1/L2 캐시 계층 경계를 인코딩하지 않는다는 것을 보이는
실험이다. 주기 태스크가 working set을 바꿔가며 sweep하고, 그 실행시간을
`rtems_clock_get_uptime_nanoseconds()`로 재서 laysim에서 측정한다.

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

`exp1_workload.h`가 working set 네 개를 정의한다. `EXP1_WS_L1_FIT`(8 KiB),
`EXP1_WS_L1_EXCEED`(24 KiB), `EXP1_WS_L2_FIT`(512 KiB), `EXP1_WS_L2_PRESSURE`
(1536 KiB)이며, 각 case는 그 버퍼를 `EXP1_SWEEPS`(256)번 sweep한다. 접근은
cache-line 간격(`EXP1_L1_LINE_SIZE` = 32 B)의 read-modify-write다.

`exp1_workload.c`는 RTEMS 실행과 YARDA 분석이 공유하는 job 본문이고,
`hierarchy_workload.c`가 주기 태스크로 그것을 호출하며 `RESULT` 라인을 찍는다.

## 실행

```sh
make -C exp1-cache-hierarchy
script -q -c "make -C exp1-cache-hierarchy run" results/exp1.log
tools/parse_results.py results/exp1.log -o results/exp1.csv
```

## 결과를 읽는 법

working set이 L1(16 KiB) 경계를 넘을 때 접근당 시간이 계단으로 뛰고, 같은 L2
계층 안에서는 512 KiB와 1536 KiB가 사실상 같은 값을 낸다. CA는 그 사이에서
매끄럽게만 변한다.

ns/access 환산은 `avg_ns / (working_set / 32 * EXP1_SWEEPS)`다. exp3의 단일
태스크 측정과 계단 위치, 계층 내부 평탄성이 일치하는 것을 확인했으며, 대조표는
[../exp3-ca-metric/README.md](../exp3-ca-metric/README.md)의 "측정 경로 제약"
절에 있다. exp1은 RMW 워크로드라 절대값이 exp3보다 40 ns 높다.

이 저장소에 들어 있는 측정 산출물은 다음과 같다.

```text
results/exp1_periodic_shared_workload.log / .csv
```
