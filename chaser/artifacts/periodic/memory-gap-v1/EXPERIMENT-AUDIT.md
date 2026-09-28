# G/C/P 메모리 워크로드 실험 점검

기준: 2026-09-27 17:05 UTC. [상세 결과](README.md),
[HW 검증 절차](../../../rtems/periodic/HARDWARE-VALIDATION.md).

## 1. 현재 결론과 적용 범위

현재 결과는 **캐시 배치에 따라 시간이 달라지는 사례는 있으나, G/C/P의 큰
성능 차이를 일반적으로 재현하지는 못했다**는 것이다. 작은 격차와 실패 사례도
결과에 포함한다. 큰 차이를 보인 후보만으로 데이터셋의 대표성을 주장하지 않는다.
이 실험군은 진단용이며 본 데이터셋·RF 학습 label로 동결된 입력이 아니다.

큰 TAT 차이를 보인 5/1/1/1 배치는 부하 불균형의 영향을 포함한다.
False sharing의 공유/독립 라인 차이는 **메모리 배치의 효과**이며 그 자체가
G/P 차이는 아니다. 혼합 주기 false-sharing 실험에서도 공유 라인은 독립 라인보다
TET가 G 15.43%, C 14.72%, P 15.34% 높아, 세 정책 모두 비슷한 손해를 보았다.

## 2. 무엇을 바꿨고 무엇이 함께 바뀌었나

설정 정본의 현재 위치는 `.cache/configs/periodic-memory-gap/`이다.
빌드·원시 로그·집계 snapshot은 `.cache/periodic-memory-gap-v1/`에 있다.
아래 경로는 각각 이 두 디렉터리 기준이며 구체적인 후보와 실패 기록은 README를 따른다.

| 변경 축 | 진행한 범위·대표 실험군 | 해석 시 함께 확인할 조건 |
|---|---|---|
| 태스크 수 | 4·8·12·16·20·24·32; `pattern-task-count`, `task-period-sweep` | 총 작업량·코어당 부하·스택/계측 데이터도 달라짐 |
| 태스크 배치 | 균형, 5/1/1/1, 역할·패턴별 묶음 | 태스크 수 균형과 CPU 수요 균형은 다름 |
| 접근 패턴 | cyclic, paired-pass, window-bank, phase, window-coeff, butterfly-scale | 패턴별 접근 횟수와 RD 분포가 다름 |
| 작업집합 | paired-pass의 4/6/8 KiB 등, 기존 24 KiB; victim 4 KiB/polluter 32 KiB | 할당 바이트·주소 범위·실제로 만진 cache line을 구분 |
| 공간 배치 | stride 1/32/4096, packed/spread, 배열 정렬 32/4096 B | stride와 배열 시작 정렬은 별개 변수 |
| job 내부 작업량 | sweeps 증가, victim/polluter 비율 조정 | 이용률·실행 중 중첩·재적재 비용의 상대 비중도 바뀜 |
| 주기 | 동일/혼합 주기, 주기와 sweeps 비례 확대 | 명목 접근률 고정은 독립 CPU 이용률 보정과 다름 |
| 주기 범위 | false-sharing 동일 5/25/100/500 ms, 혼합 5/8/20/50/500/1000 ms | 긴 주기가 자동으로 캐시를 비우지는 않음 |
| 공유 여부 | reader/writer가 같은 32 B line vs 독립 line | generic private-load workload와 별도 진단군 |
| 측정 길이 | 짧은 pilot, 20 warm-up+200 measured jobs/task, 공통 horizon | 실험별 다름. L1 set 실험은 20+180임 |
| 반복 | 정책당 1회부터 별도 프로세스 5회까지 | 결정적 simulator의 동일 결과는 독립 확률 표본이 아님 |
| 지표 | TET/TAT, makespan, response sum, task별 평균·관측 최대 | 합계의 상쇄와 release horizon 효과를 분리 |

공통 정책 구성은 **G=4-core EDF-SMP, C=1+3 EDF-SMP, P=4개의 single-core
scheduler**다. C를 2+2로 바꾼 비교는 이 실험군의 공통 조건이 아니다.
Scheduler domain은 공유 L2를 물리적으로 분할하지 않는다.
실행용 RTEMS 소스는 `-O0 -g`이며, 별도 LLVM/HARA 분석 결과는 실행 계측값이 아니다.

동일 주기 false-sharing의 짧은 pilot은 네 주기 모두 완료했다
(task당 warm-up 2+측정 6 jobs). 정식 길이 재실험은 task당 20+200 jobs,
정책·배치당 5회다. 기준 시각에 5 ms는 완료했고 25 ms는 진행 중이며,
100/500 ms 정식 길이 결과는 아직 완료 결과로 취급하지 않는다.
혼합 주기 실행은 완료했지만 저속 task의 측정 jobs는 4개·2개로 작다.

## 3. 최근 L1 set 점유 통제 결과

`l1-set-pressure-v1`은 4조건×G/C/P=12회 모두 정상 종료했다.
각 task는 서로 다른 2 KiB 배열에서 32 B 간격의 64개 byte를 48번 읽는다.
따라서 job당 배열 load는 3,072회다. N=16은 주기 4 ms, N=20은 5 ms이고
각각 총 200 jobs/task 중 앞 20개를 warm-up으로 제외했다.

| task 수 | 배열 시작 정렬 | P의 코어별 task 데이터 set 점유 | TET G/C/P (ms) | TAT G/C/P (ms) | G/P 격차 TET / TAT |
|---:|---|---|---|---|---|
| 16 | 4096 B | 64 set×4 line | 889.734 / 883.826 / 885.264 | 249.774 / 240.290 / 235.463 | 0.51% / 6.08% |
| 16 | 32 B | 128 set×2 line | 885.960 / 875.156 / 865.342 | 248.851 / 237.934 / 230.141 | 2.38% / 8.13% |
| 20 | 4096 B | 64 set×5 line | 1114.031 / 1109.356 / 1108.976 | 311.027 / 302.167 / 296.080 | 0.46% / 5.05% |
| 20 | 32 B | 64 set×2+64 set×3 line | 1111.485 / 1101.886 / 1091.856 | 314.001 / 300.239 / 291.927 | 1.80% / 7.56% |

격차는 `(G-P)/P×100`이다. 같은 task 수 안에서 정렬만 바꾼 쌍을 비교한다.
4-way는 task 4개의 뜻이 아니라 **같은 set에 동시에 유지할 수 있는 line 4개**다.
위 점유는 ELF 주소로 계산한 P의 task 배열만의 값이며 OS·스택·계측 버퍼는
포함하지 않는다. 2/3 line 조건도 실제 상주를 보장하지 않는다.

밀집 배치로 P의 TET는 간격 배치 대비 N=16에서 2.25%, N=20에서 1.54%
감소했다. 두 경우 모두 G/P 격차도 커졌다. 다만 조건당 실행 1회이며
실제 L1 miss 계측이 없어 캐시 상주의 인과적 입증은 아니다.

## 4. 놓치기 쉬운 변수와 확인 수준

### 실행 명령어와 반복의 영향

N=20 compact의 P ELF `kernel_t12`를 disassemble하면 내부 반복의 배열
`ldub` 1회 외에 stack load 4회와 stack store 2회가 있다. 따라서 배열을
읽기만 하는 C 코드라도 CPU가 실행하는 전체 메모리 접근은 read-only가 아니다.
내부 반복만으로 job당 stack store 6,144회가 추가되고 바깥 루프·함수 호출은
별도다. `-O0`의 공통 비용이 배열 캐시 효과를 희석할 가능성이 있지만,
최적화 대조 실험 전에는 원인으로 확정하지 않는다.

48 sweeps 중 첫 sweep은 배열 접근 횟수의 1/48=2.08%다. 코어 이동의 손해가
주로 최초 재적재에 있다면 이후 반복이 그 비용을 분산할 수 있다.
이는 **시간 격차의 상한이 2.08%라는 뜻도, 나머지 접근이 모두 hit라는 뜻도 아니다.**

### 이동과 miss는 다른 관측이다

G의 연속 측정 job 시작 코어가 달라진 횟수는 N=16 compact에서
1,788/2,864회, N=20 compact에서 2,165/3,580회였다. 분모는 같은 task의
인접 측정 jobs를 비교할 수 있는 횟수 `N×(180-1)`다. 이 값으로 job 내부
migration이나 cache miss를 세지는 않는다.

읽기 전용 task 데이터는 여러 코어에 복제돼 남아 있을 수 있다. 코어가 바뀌어도
그 코어가 이미 해당 데이터를 갖고 있으면 cold miss가 아니다. L1에서 놓쳐도
공유 L2에서 해결될 수 있다. 따라서 migration 횟수만 늘리는 것으로 큰 TET
격차를 보장할 수 없다.

실제로 compact G의 job CPU 평균은 다음과 같다. 최초 측정 job은 비교에서 제외했다.

| task 수 | 이전 job과 같은 시작 코어 | 다른 시작 코어 | 관측 차이 |
|---:|---:|---:|---:|
| 16 | 305.602 µs (1,076 jobs) | 308.849 µs (1,788 jobs) | +1.06% |
| 20 | 307.079 µs (1,415 jobs) | 309.846 µs (2,165 jobs) | +0.90% |

Task별로 비교한 증가율의 median은 각각 약 0.68%, 0.38%였다.
어떤 task·스케줄 상태에서 이동했는지가 다르므로 이 비교도 migration의
순수 비용 추정치는 아니다.

### 부하·phase·스케줄러

최근 compact P raw에서 `Σ task별 평균 job CPU / period`는 코어당 약
0.300–0.301(N=16), 0.303–0.304(N=20)이다. 이는 관측 workload 이용률이고
독립 P characterization으로 보정한 U나 OS 포함 코어 이용률이 아니다.
이전 고부하 paired-pass에서도 차이가 작았으므로 낮은 U만으로 전체를 설명할 수 없다.

지금은 공통 시작점에서 task를 기동한다. **같은 주기에서 release phase만
엇갈리게 하는 실험**, 독립 U를 맞춘 뒤 phase/주기를 분리하는 실험,
C=2+2와 1+3의 비교는 추가 가치가 있다. EDF의 실행 순서 변화와 캐시 효과를
분리해야 한다. 우선순위·선점·FPU 연산 비중도 체계적으로 sweep하지 않았다.

### 계측과 캐시 모델

결과 출력은 workers 종료 후지만 job 기록·시계/CPU 시간 읽기는 실행 중에
발생한다. OS·스택·계측 버퍼의 cache set 점유도 고려해야 한다. Empty job으로
계측 부담을 진단할 수 있으나 그 값을 일괄 빼면 캐시 상태 차이까지 제거되지는 않는다.

기존 [ASSETS §5](../../../system-prompt-extraction/plan/ASSETS.md)는 laysim에서
유효한 cache hit/miss ground truth를 얻지 못한 점과 정적 분석기의
write-allocation 정책 차이를 이미 기록한다. GR740 L1D는 16 KiB·4-way·32 B
line이며 write-through/no-write-allocate다.
([GR740 manual §6.3](https://download.gaisler.com/products/gr740/doc/GR740-UM-DS-2-10.pdf))
현재 분석기의 YAML만 `write_allocate: false`로 바꾸는 것은 지원되지 않는다.
정적 RD·set 점유·모델 miss와 HW counter는 서로 다른 근거로 기록해야 한다.

### 지표와 표본

TET는 측정 jobs의 CPU 시간 합이다. TAT는 같은 nominal release를 공유하는
cohort마다 가장 이른 start부터 마지막 completion까지의 시간을 합한다.
Release부터의 cohort 응답시간 합 및 개별 response 합과는 다르다.
Makespan은 release horizon의 영향을 크게 받는다. 서로 다른 주기/측정 job 수의
입력을 비교할 때 합계만으로 캐시 성능을 판단하지 않는다.

Task별로 CPU가 증가/감소하면 총 TET에서 상쇄될 수 있다. Task/역할별 분포와
관측 최대 job CPU·response·cohort TAT를 함께 남긴다. 관측 최대는 WCET/WCRT
보장이 아니다. Warm-up 제외 결과를 주 결과로 쓸 경우 초기 jobs를 포함한 민감도도
남긴다. Job 반복 수와 독립 실행 수를 구분한다.

## 5. 다음 검증의 우선순위

사용자 지시(2026-09-27): **SIM 실험을 먼저 진행하고 구성·결과를 확정한 뒤
HW에서 검증한다.** 보드 확보·접속이나 HW smoke를 SIM 실험의 선행 조건으로 두지 않는다.

1. 진행 중인 SIM 실험의 종료·실패·raw를 확인하고 기존 G/C/P 결과를 재집계한다.
   Task/역할별 TET·response·관측 최대와 합계가 상쇄되는 경우를 함께 정리한다.
2. **SIM에서 최적화와 sweeps의 영향을 분리**한다. 기존 O0 baseline을 보존하고
   workload만 최적화한 경우, 작은/큰 sweeps를 대조한다. 접근 순서·횟수·checksum·
   ELF 배치를 검증하며 계측 코드는 동일하게 유지한다.
3. 독립 P 측정으로 U를 통제하고 phase·주기·C topology 등의 후보를 한 축씩
   검토한다. False-sharing의 같은 코어/다른 코어 배치는 별도 진단군으로 다룬다.
   아직 구현되지 않은 phase 지원 등을 이미 실행한 조건으로 취급하지 않는다.
4. 유효성·반복 재현성을 확인한 SIM 실험의 입력·ELF·계측 경계·비교군·결과를
   확정한다. 작은 격차와 실패 사례도 보존하며 큰 격차만 선별하지 않는다.
5. **그 이후 HW 검증**으로 넘어가 확정된 ELF의 시간·상대 효과를 재현한다.
   필요한 warm/cold 대조군과 HW counter 검증은 이 단계에서 수행한다.

HW 절차는 향후 사용을 위해 문서화한 상태이며 보드 실행은 하지 않았다.
O2·새 패턴·C 2+2 등의 문서 예제는 임시 소스의 빌드 검증까지이며 해당 variant의
정식 SIM 시간 측정이나 프로젝트 구현 완료를 뜻하지 않는다.
