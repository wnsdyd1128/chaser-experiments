# 입력·다중 배열 예제

[전체 실험 안내](../EXPERIMENT-GUIDE.md) · 명령은 workspace root 기준이다.

## 1. 입력과 생성 결과

| 종류 | 입력 | 생성·실행 도구 |
|---|---|---|
| 원본 PolyBench 30종 | `schema_version: 3`, `polybench.benchmark`, `polybench.dataset: MEDIUM` | [원본 소스 예제](../polybench/README.md); 공용 `prepare/analyze/run` 및 독립 검증 |
| 명시적 다중 배열 workload | `schema_version: 2`, `arrays`, 역할별 task binding | `python3 -m tools.rtems_periodic`의 `prepare`, `analyze`, `run`; cyclic/paired-read/gemm-u32/polybench-atax-u32 |
| False-sharing reader/writer | `pairs`, `layouts` 등이 있는 JSON | `.cache/configs/periodic-memory-gap/false-sharing/run.py` |

`configs/periodic-multi-array/`는 버전 관리되는 다중 배열 입력이고,
`.cache/periodic-multi-array/`는 새 worktree의 생성·분석·실행 결과 위치다.
이전 실험의 `.cache/configs/periodic-memory-gap/`는 원본 입력·시나리오 실행기,
`.cache/periodic-memory-gap-v1/`는 그 생성 환경·측정 결과 위치였다(2026-10-06 삭제).
디렉터리 이름이 실험 조건을 결정하지는 않는다.

```text
configuration.json
 → make_plan(): 입력 검증, job 수·warm-up·scheduler domain 계산
 → workload_source(): 패턴에 따른 workload.c 생성
 → init.c/probe.c와 정책별 config.h/topology.h 준비
 → waf + GR740 BSP로 g.exe/c.exe/p.exe 빌드
 → ELF 배열 주소 검사, manifest hash 기록
 → run(): boot flags 설정, laysim 실행, raw 검증·집계
```

관련 구현: [CLI](../../../tools/rtems_periodic.py),
[생성·빌드](../../../chaser/periodic/build.py),
[계획·집계](../../../chaser/periodic/measurement.py),
[배열 검증](../../../chaser/periodic/arrays.py),
[커널 생성·reference stream](../../../chaser/periodic/kernels/__init__.py),
[빌드 옵션](../wscript).

필요 환경은 Python/project imports, `pkg-config`, `/opt/rtems/6`의 SPARC
toolchain·GR740 BSP, `/opt/src/rtems/waf`다. SIM 실행에는
`/opt/laysim-gr740/laysim-gr740-cli`, `script`, `timeout`과 현재 설치에 필요한
접근 가능한 X display가 추가로 필요하다. 기존 `DISPLAY=165.246.44.80:90.0`은
이 환경의 값이며 다른 호스트에서 그대로 사용할 수 있다는 뜻은 아니다.
`prepare` 자체는 simulator/display가 필요 없다. 실행용 빌드는 기본 `-O0 -g`이고,
설정의 `workload_optimization: "O2"`로 workload.c만 O2로 빌드할 수 있다.

## 2. 입력 예시

### 2.1. 기본 읽기 예제

[`configs/periodic-example.json`](../../../configs/periodic-example.json)은
세 cyclic task를 각각 별도의 `uint8_t` 배열에 연결한다.
각 task는 `distinct: 8`과 `sweeps: 1200`을 사용하며,
`stride_bytes`를 1, 32, 4096으로 달리해 접근 간격을 비교한다.
배열은 `initial_value: 1`, `alignment_bytes: 4096`으로 선언하고
`tasks[].arrays.input.array_id`로 연결한다.

<a id="multi-array"></a>

### 2.2. Schema v2: 명시적 배열과 GEMM

다음 입력은 모두 같은 공용 생성기로 실행한다.

| 예제 | 배열·task 구성 |
|---|---|
| [gemm-u32-smoke.json](../../../configs/periodic-multi-array/gemm-u32-smoke.json) | 단일 task, A 2×3와 B 3×2를 곱해 C 2×2에 저장 |
| [gemm-u32-shared-smoke.json](../../../configs/periodic-multi-array/gemm-u32-shared-smoke.json) | 두 task가 A/B를 공유하고 각각 독점 C에 저장 |
| [shared-reads-smoke.json](../../../configs/periodic-multi-array/shared-reads-smoke.json) | cyclic과 paired-read가 입력 배열을 공유 |
| [polybench-atax-u32-medium.json](../../../configs/periodic-multi-array/polybench-atax-u32-medium.json) | A 390×410, x 410개, tmp 390개, y 410개로 y = Aᵀ(Ax) 계산 |

`schema_version: 2`는 **입력 형식**이다. 계측 계약은
`chaser-periodic-measurement-v3`다.

| 필드 | 단위·계약 |
|---|---|
| `arrays[].array_id` | 고유 C identifier; ELF symbol은 `data_<array_id>` |
| `element_type` | `uint8_t` 또는 `uint32_t` |
| `shape` | 선택적 논리 형상. `[2,3]`, `[2,3,4]`처럼 양의 정수 목록 |
| `strides_elements` | shape의 차원별 **원소 간격**. 생략하면 조밀한 row-major |
| `length` | 물리 저장 공간의 원소 수. shape가 없으면 필수, 있으면 마지막 논리 원소까지의 extent로 유도 |
| `alignment_bytes` | 배열별 32 또는 4096 B; 기본값 4096 |
| `initial_value` | 자료형 범위의 정수 상수; 기본값 1 |
| `tasks[].arrays` | 역할 → `{array_id, offset_elements}`; offset은 원소 수, 기본값 0 |
| cyclic/paired-read의 `distinct`, `stride_bytes` | 각 역할에서 읽는 위치 수, 바이트 간격; stride는 자료형 크기의 배수 |
| GEMM의 `m`, `n`, `k` | A m×k, B k×n, C m×n. rank-2 shape에서 유도하며 명시하면 반드시 일치 |
| GEMM의 `lda`, `ldb`, `ldc` | 원소 단위 행 간격. shape가 있으면 첫 stride에서 유도; 기존 length 전용 입력에서는 필수 |
| `sweeps` | 한 job 내부의 커널 반복 수; period에 따른 job 수와 별개 |

역할은 cyclic의 `input`, paired-read의 `a`/`b`, GEMM의 `A`/`B`/`C`다.
paired-read의 두 배열은 같은 자료형이어야 하며 a→b 순서로 한 위치씩 읽는다.
GEMM은 uint32 배열만 받으며 `distinct`·`stride_bytes`·`width`를 받지 않는다.
배열은 workers 시작 전에 한 번 초기화한다. job 사이에 재초기화나 cache flush는 없다.

GEMM 예제 JSON은 A의 `shape: [2,3]`, B의 `[3,2]`, C의 `[2,2]`를 선언한다.
task에는 역할 binding과 sweeps·core·period만 지정해 차원을 중복하지 않는다.
자료형을 명시한 다차원 배열 선언은 1차원 이상을 지원하며 GEMM은 정확히 2차원이다.
cyclic/paired-read는 다차원 배열에도 기존 물리 offset·stride 순서로 접근한다.
shape를 지정했다고 자동으로 다차원 순회나 padding 건너뛰기가 생기지는 않는다.

예를 들어 `[2,3]`에 `strides_elements: [8,2]`를 지정하면 원소 위치는
`0,2,4,8,10,12`이고 최소 length는 13이다. 전체 마지막 행 padding도 확보하려면
`length: 16`을 함께 지정한다. 일반식은
`extent = 1 + sum((shape[d]-1)*strides_elements[d])`이며 `length >= extent`다.
각 외부 stride는 내부 차원 전체 extent 이상이어야 한다. 양의 row-major 간격과
padding은 허용하지만 transpose/음수 stride/겹치는 view/broadcast는 지원하지 않는다.
shape 없이 strides만 지정하거나 bool·0·비정수 차원, rank가 다른 strides는 거부한다.
binding의 offset은 이 형상 전체를 물리 원소 수만큼 이동시키므로, offset을 쓰면
`offset_elements + extent <= length`를 만족하는 저장 공간을 명시한다.
shape와 strides는 plan과 hash에 보존하고 C 저장소는 평탄한 배열로 생성한다.
`length`만 지정하는 평탄 배열도 지원한다. C 템플릿을 수정하면
새 prepared를 만들고 접근 순서·결과를 재검증한다.

읽기 전용 입력은 여러 task가 공유할 수 있다. 쓰기 배열은 다른 task가 읽거나
쓰도록 binding할 수 없으며, 같은 task의 서로 다른 역할도 동일 array ID를
사용할 수 없다. 사용하지 않는 배열과 범위를 넘는 offset·행 간격은 거부한다.
배열은 1–96개, 입력 순서대로 배치하며 정렬 padding 포함 16 MiB 이내여야 한다.
v2의 job당 source access 상한은 10,000,000이며 load와 store를 모두 센다.
task 수·horizon·warm-up·전체 job 수 제한은 유지되며
[JSON 입력 제약](CUSTOMIZATION.md#json-input)을 따른다.

정수 필드는 bool·float·문자열을 받지 않는다. 읽기 커널은 `distinct` 1–131072,
`stride_bytes` 1–4096을 허용하고, `sweeps`는 1–1,000,000이다.
배열 순서를 바꾸면 배치·plan identity도 바뀌지만 JSON object key 순서는 영향이 없다.
배치는 0x01000000에서 시작해 각 배열 정렬을 맞추며 끝 주소는 0x02000000 이하다.
plan의 주소는 기대값이고 `layout.json`에는 실제 ELF와 일치한 주소만 기록한다.

읽기 커널의 마지막 접근 끝은 다음 범위 안이어야 한다.
`offset_elements*itemsize + (distinct-1)*stride_bytes + itemsize <= length*itemsize`.
GEMM은 각 역할의 행 수 R, 열 수 S, 행 stride L, 열 stride T에 대해
`offset+(R-1)*L+(S-1)*T+1 <= length`를 검사한다. 기존 평탄 입력은 T=1이다.
shape가 있으면 행렬 차원·행 간격 명시값과의 불일치도 거부한다.

단일 GEMM 예제는 A=1, B=2이므로 C의 네 원소가 모두 6이다.
각 sweep이 `C = A × B`를 덮어쓰며 연산은 modulo 2^32다.
마지막 sweep 뒤 유효 C 원소를 한 번씩 읽어 word-wise FNV-1a hash를 반환한다.
**이 hash 계산·재읽기는 job의 계측·분석에 포함**된다. 읽기 커널은 load 값의
uint32 합을 반환한다. 예제의 job당 접근 수는 52 loads + 8 stores = 60이며,
총 4 jobs 중 앞 2개가 warm-up이다. 이는 기능 smoke용 길이다.

GEMM은 row-major, transpose 없이 i→j→k 순서로 계산하고 각 출력을 k 누적 후
한 번 store한다. 입력·출력 배열은 volatile이며 최적화된 BLAS의 성능을 나타내지 않는다.
checksum 계약은 `u32-word-fnv1a-output-v1`이다. `h=2166136261`에서 시작해
논리적 C 원소를 row-major 순서로 읽으며 `h=((h XOR value)*16777619) mod 2^32`를
적용한다. padding은 제외하며 byte 직렬화 FNV와 구분한다. 반환값 비교는 job 호출
이후지만 hash 계산은 호출 내부다. host 테스트는 hash 외에 C의 모든 원소도 검사한다.

GEMM의 job당 load 수는 `sweeps*2*m*n*k + m*n`, store 수는 `sweeps*m*n`이다.
읽기 커널은 `sweeps*distinct*역할 수`만큼 load하고 store는 없다.

<a id="polybench-atax"></a>

#### PolyBench 기반 정수 ATAX

원본 자료형·초기화·MEDIUM 설정을 보존하는 ATAX와 나머지 29종은
[원본 PolyBench 예제](../polybench/README.md)를 사용한다. 아래는 uint32 변형이다.

`polybench-atax-u32`는 [PolyBench/C 4.2.1의 ATAX 소스](https://github.com/MatthiasJReisinger/PolyBenchC-4.2.1/blob/master/linear-algebra/kernels/atax/atax.c)
(`kernel_atax`, 2016-05-10)의 알고리즘을 정수 C 커널로 재구현한 예제다.
`y`를 0으로 만들고 각 행 i마다 `tmp[i] = A[i,:]·x`를 계산한 뒤
`y[:] += A[i,:]·tmp[i]`를 수행한다. 행별 두 순회와 임시 배열의 load/store를
유지하며 volatile load 순서는 C의 개별 문장으로 고정한다.

원본의 기본 double 자료형·초기화 수식·PolyBench timer 대신 `uint32_t`의
modulo 2^32 연산, JSON의 상수 초기값, RTEMS periodic 계측을 사용한다.
배열 크기는 원본 MEDIUM의 M=390, N=410과 같다. 자료형과 초기화가 다르므로
원본 PolyBench 수치 결과나 성능 점수와는 대응하지 않는다.
각 sweep에서 논리적 tmp/y를 초기화하므로 이전 job 결과에 의존하지 않는다.
마지막 sweep 뒤 y의 논리 원소를 순서대로 읽는 FNV-1a hash도 계측·분석에 포함한다.

배열 역할과 필수 shape는 `A: [m,n]`, `x: [n]`, `tmp: [m]`, `y: [n]`이다.
모두 `uint32_t`이며 `m`·`n` 등의 별도 task 매개변수는 받지 않는다.
각 배열의 `strides_elements`와 binding의 `offset_elements`로 padding과
view를 지정할 수 있다. A/x는 읽기 전용으로 공유할 수 있고 tmp/y는 task마다
독점해야 한다. 출력과 임시 배열의 padding은 변경하지 않는다.

예제는 A=1, x=2이므로 tmp의 각 원소는 820, y의 각 원소는 319800이다.
job당 load 수는 `sweeps*6*m*n+n`, store 수는 `sweeps*(n+m+2*m*n)`이며,
기본 1 sweep에서 **959810 loads + 320600 stores = 1280410 accesses**다.
생성·reference 계약은 [atax.py](../../../chaser/periodic/kernels/atax.py),
직접 수정할 C 루프는 [atax.c.in](../../../chaser/periodic/kernels/atax.c.in)에 있다.

```sh
python3 -m tools.rtems_periodic prepare \
  configs/periodic-multi-array/polybench-atax-u32-medium.json \
  --output .cache/periodic-multi-array/my-atax-v1/prepared
python3 -m tools.rtems_periodic analyze .cache/periodic-multi-array/my-atax-v1/prepared
python3 -m tools.rtems_periodic run .cache/periodic-multi-array/my-atax-v1/prepared \
  --architecture p --runs 1 --timeout 60 \
  --output .cache/periodic-multi-array/my-atax-v1/p
```

G/C 실행은 아래 §2.3처럼 architecture와 output을 바꾼다.
이 예제도 cold task-local 진단용이며 RF label 편입 대상은 아니다.

<a id="polybench-kernels-2026-10"></a>

#### PolyBench 기반 정수 커널 9종 (2026-10)

ATAX와 같은 규칙으로 PolyBench/C 4.2.1의 커널 9종을 uint32로 재구현했다(실제 커널 실험 45·46).
공통 규칙은 다음과 같다.
- 자료형은 `uint32_t`이고 연산은 modulo 2^32다. 원본의 실수 상수는 정수로 바꾼다(ALPHA 3, BETA 2).
- 초기값은 JSON의 배열별 상수다. 그래서 checksum을 닫힌식으로 계산할 수 있다.
- volatile load 순서는 원본 연산자 순서대로 C의 개별 문장으로 고정한다.
- 마지막 sweep 뒤 출력 배열을 row-major로 읽는 FNV-1a hash를 job 안에서 계산한다. 주기 실행은 job마다 같은 hash를 요구하므로,
  결과를 제자리에서 갱신하는 커널은 job 시작에 그 배열을 초기값으로 되돌린다(Jacobi는 상수 초기값이 변하지 않아 필요 없다).
- 정사각 크기 n 하나로 모양을 정하며, 별도 task 매개변수는 받지 않는다.

| pattern | 원본 | 상태와 차이 |
|---|---|---|
| `polybench-bicg-u32` | `kernel_bicg` | s, q를 sweep마다 0으로 초기화 |
| `polybench-mvt-u32` | `kernel_mvt` | x1, x2를 sweep마다 0으로 초기화(원본은 입력에 누적) |
| `polybench-gesummv-u32` | `kernel_gesummv` | tmp, y를 sweep마다 초기화 |
| `polybench-jacobi1d-u32` | `kernel_jacobi_1d` | 평균은 정수 나눗셈 3. 한 sweep이 한 time step이고 상태가 이어짐. A, B가 같은 초기값이어야 함 |
| `polybench-jacobi2d-u32` | `kernel_jacobi_2d` | 평균은 정수 나눗셈 5. 그 밖은 JACOBI-1D와 같음 |
| `polybench-2mm-u32` | `kernel_2mm` | job 시작에 D를 초기값으로 되돌림. tmp는 sweep마다 초기화, D는 원본처럼 BETA를 곱하고 누적(한 job의 sweep 사이에 상태가 이어짐) |
| `polybench-syrk-u32` | `kernel_syrk` | job 시작에 C를 초기값으로 되돌림. C의 아래 삼각만 갱신(sweep 사이에 상태가 이어짐). 루프 순서는 원본(k 바깥, j 안쪽) |
| `polybench-trmm-u32` | `kernel_trmm` | job 시작에 B를 초기값으로 되돌림. B를 제자리에서 원본 순서로 갱신(sweep 사이에 상태가 이어짐). A는 대각선 아래만 읽음 |
| `polybench-doitgen-u32` | `kernel_doitgen` | 3차원 A[r][q][p]를 (n²×n) 행렬로 둔다(행 r·n+q). job 시작에 A를 초기값으로 되돌림. A는 제자리 갱신, sum은 임시 |

모양, 접근 수, 닫힌식 checksum은 각 모듈(`chaser/periodic/kernels/<이름>.py`, 2MM은 `twomm.py`)의 `validate`에 있다.
테스트(`tests/periodic/multi_array/test_polybench_kernels.py`)는 커널마다 다음을 확인한다.
- 선언한 접근 수
- 닫힌식 checksum(O0·O2)
- 임의 입력에서 독립 Python 계산과의 일치
- footprint
- 실제 RTEMS 실행 파일에서 YARDA가 본 접근 흐름

<a id="low-locality-kernels-2026-10"></a>

#### 저지역성 전치 커널 (2026-10)

`transpose-u32`는 R×n 입력 `A`를 n×R 출력 `B`로 전치한다.
`cornerturn-u32`는 실수부·허수부를 별도 uint32 배열로 두고,
R×n 입력 `Ar`, `Ai`를 n×R 출력 `Br`, `Bi`로 같은 반복문에서 전치한다.
두 커널은 입력을 행 방향으로 읽고 출력을 열 방향으로 쓴다.
각 sweep이 출력 전체를 덮어쓰므로 job마다 같은 checksum을 낸다.

job 안 checksum은 출력 배열마다 첫 열만 FNV-1a로 해시한다.
출력 전체를 해시하는 행 방향 접근이 전치의 접근 패턴을 바꾸지 않도록 한 계약이다.
전체 출력과 입력·padding 보존은 `tests/periodic/multi_array/test_polybench_kernels.py`의
독립 계산으로 확인하며, checksum 접근도 reference stream에 포함한다.
R=256과 커널별 n 범위는 실험 47의 조건이며 공용 커널의 형상 제한은 아니다.

<a id="self-suspending-jobs-2026-10"></a>

#### job 중간 sleep (2026-10)

schema v2 task에 sleep 항목을 넣으면 job이 계산 도중 스스로 잠든다(I/O 대기를 흉내 낸 self-suspension).
두 가지 형식 중 하나를 쓴다(함께 쓰면 거부).

| 항목 | 뜻 | 범위 |
|---|---|---|
| `suspend_ticks`, `suspend_after_sweeps` | 한 번, 고정 길이 sleep: 앞 k sweep 뒤에 S tick | S ≥ 1, 1 ≤ k < `sweeps` |
| `suspend_points` | 여러 번·가변 sleep: 지점 목록 | 비어 있지 않은 목록, `after_sweeps`가 증가 순 |

`suspend_points`의 각 지점은 `{"after_sweeps": k, "ticks": S}`(고정, S ≥ 1) 또는
`{"after_sweeps": k, "min_ticks": a, "max_ticks": b, "seed": n}`(가변, 0 ≤ a ≤ b, b ≥ 1, `seed` 생략 시 0)이다.
`after_sweeps`는 그 sleep 전까지 끝낸 누적 sweep 수다. 한 job의 sleep 합(가변은 `max_ticks` 합)은 주기보다 작아야 한다.

```json
"suspend_points": [{"after_sweeps": 200, "ticks": 2},
                   {"after_sweeps": 400, "min_ticks": 0, "max_ticks": 6, "seed": 3}]
```

- 가변 길이는 job마다 [a, b]에서 균등하게 뽑는다. 난수는 SHA-256("<task_id>/<지점 번호>/<seed>")로 정하므로
  같은 설정은 언제나 같은 길이를 낸다(`chaser.periodic.kernels.suspend_schedule`가 plan task에서 job별 값을 준다).
  0 tick이 뽑히면 그 job은 그 지점에서 잠들지 않는다.
- 생성 코드는 sleep 사이 구간마다 함수를 만든다. `task_job_<id>`가 첫 구간, `task_job_resume_<id>`,
  `task_job_resume2_<id>`, …가 그다음 구간이다. 구간마다 커널 템플릿 전체(설정·checksum 포함)를 렌더링하므로,
  각 구간은 그 sweep 수의 완전한 job이다(job 시작에 배열을 초기화하는 커널은 다음 구간에서도 초기화한다).
- `init.c`는 측정 구간 안에서 구간 → `rtems_task_wake_after(그 job의 tick)` → 구간을 반복한다. job의 checksum은
  마지막 구간의 것이고, 앞 구간 checksum이 틀리면 checksum 오류로 기록된다. job CPU 시간에는 잠든 시간이 들어가지
  않고, 응답 시간·TAT에는 들어간다. sleep은 tick 경계에서 끝나므로 S tick sleep이 CPU를 떠난 시간은 (S − 1, S] tick이다.
- 정적 분석(`chaser.periodic.analysis`)은 구간마다 빈 캐시에서 분석하고, 접근 수·first-hit 수·
  재사용 거리 histogram을 합쳐 task의 CLP·CLS·CA를 낸다(`cases.<id>.segments`에 구간별 값).
- sleep이 없는 task와 set의 plan, `config.h`, `workload.c`, 실행 파일 코드는 이 기능 전과 같다
  (`init.c`의 `#line`이 `require()`의 줄 번호를 보존한다. 2026-10-15 실험 48 set으로 디버그 정보를 뗀 ELF 4개가 같음을 확인).
- 경량 분석 경로(`policy-mix/kernel_yarda.py`, P ELF·hierarchy-rd만)도 구간마다 분석해 같은 방식으로 합친다.
  `chaser.policy.pfirst.inputs.load_analysis`는 `segments`에 적힌 구간을 모두 읽어 L1 miss 수와 first-hit 수를 더하고,
  작업 집합은 가장 큰 구간의 값을 쓴다(구간들이 같은 배열을 다시 훑는다). 구간 출력이 하나라도 없으면 판단을 미룬다.
  2026-10-15 실제 커널 5개(전치, corner turn, mvt, jacobi1d, gesummv)에 sleep을 넣은 set에서 두 경로의 결과가 같았다.
- 아직 반영하지 않은 것: `chaser.policy.pfirst`(명목 판정·배치·특징)는 sleep 시간을 쓰지 않는다.

<a id="soft-deadline-runs-2026-10"></a>

#### 마감을 놓쳐도 계속 실행 (2026-10)

schema v2 설정의 최상위에 `continue_after_miss: true`를 넣으면, job이 늦거나 release가 밀려도 task를 멈추지 않고
`job_count`까지 모두 실행한다(기본값 false는 이전처럼 첫 위반에서 그 task를 멈춘다).

- `init.c`는 이 모드에서 checksum 오류와 `RTEMS_SUCCESSFUL`·`RTEMS_TIMEOUT`이 아닌 주기 상태에서만 멈춘다.
- 측정 해석은 늦은 완료, 밀린 release(주기 상태 `RTEMS_TIMEOUT`), `EXPIRED` 주기를 run 오류로 보지 않고,
  측정 구간의 `late_jobs`(완료 > release + 주기)와 `postponed_releases`를 결과에 더한다. 응답 시간은 명목 release
  (t0 + j × 주기)부터 센다. 모든 job이 기록되므로 TET·TAT·응답 시간은 늦은 run에서도 정의된다.
- release가 밀리는 동안 RTEMS는 주기의 회계 기준 시각을 마지막 제때 release에 둔다. 그래서 이 모드의 release 검사는
  기준 시각이 그 task의 이전 release(release − m × 주기, m ≥ 0) 중 하나인지 본다.
- 이 모드의 `execution_status: ok`는 "모든 job이 정상 기록됨"이지 "모든 마감을 지킴"이 아니다. 마감은 `late_jobs`로 본다.
- 이 모드를 쓰지 않는 plan·`config.h`·실행 파일 코드는 이전과 같다(`init.c`의 `#line`, 2026-10-14 실험 48 set으로 확인).

<a id="release-offsets-2026-10"></a>

#### release offset (2026-10)

schema v2 task에 `offset_ticks`(0 이상, 주기 미만의 정수 tick)를 넣으면 그 task의 job j는 t0 + `offset_ticks` + j × 주기에
release된다. 기본값 0은 이전처럼 t0에 release한다. 주기가 아주 긴(사실상 비주기) task가 다른 task와 t0에 한꺼번에
release되지 않게 할 때 쓴다. 무작위 시각이 필요하면 set을 만드는 스크립트가 seed로 offset을 뽑아 넣는다(프레임워크는
정해진 값만 받는다).

```json
{"task_id": "t1", "pattern": "cyclic", "period_ticks": 320, "offset_ticks": 137, "...": "..."}
```

- `init.c`: offset이 있는 task는 t0에 길이 `offset_ticks`의 빈 주기로 `rtems_rate_monotonic_period`를 시작하고, 다음 호출부터
  길이를 주기로 바꾼다. 기다리는 동안에도 주기 안에 있어 EDF가 마감을 매긴다. 주기 밖의 task는 EDF에서 배경 우선순위라,
  `rtems_task_wake_after`로 기다린 뒤 주기를 시작하면 코어가 바쁠 때 release가 밀린다.
- 측정 해석: release와 마감 검사, 응답 시간, TAT 묶음(같은 release 시각의 job)은 offset을 더한 release를 쓴다.
  job 수(horizon ÷ 주기)와 warm-up job 수(warm-up ÷ 주기)는 offset과 관계없다. offset이 다른 task는 release 시각이
  겹치지 않아 TAT 묶음이 따로 생긴다.
- 쓰는 경우에만 plan(`offset_ticks`)과 `config.h`(`CHASER_OFFSETS`)에 나타난다. offset이 없는 set의 plan·`config.h`·실행
  파일 코드는 이전과 같다(2026-10-16 실험 48 set으로 디버그 정보를 뗀 ELF 4개 확인).
- laysim 확인(2026-10-16, fixture `tests/periodic/multi_array/fixtures/offset-laysim-p.json`): 주기 20·offset 7 task와
  주기 40·offset 13 task가 정확히 7·27·47·67 ms와 13·53 ms에 release되어 0.03 ms 안에 시작했고, 7 ms에 release된 job은
  10 ms에 release된 더 이른 마감의 job에 선점됐다.

<a id="register-bound-kernels-2026-10"></a>

#### 레지스터 연산 커널과 정적 메모리 집중도 (2026-10)

배열을 거의 읽지 않고 IU·FPU 연산만 하는 job(짧은 주기 제어·필터 task 같은 것)을 위한 커널 두 개다.
sweep마다 `seed` 배열(`uint32_t`)에서 초깃값 하나를 읽고, 이어지는 연산을 `iterations`번 반복한다.
배열이 `volatile`이라 O2 빌드도 sweep마다 초깃값을 다시 읽고 반복 전체를 실행한다.

| pattern | 한 sweep의 연산 | sweep 결과 |
|---|---|---|
| `alu-u32` | `x ^= x << 13; x ^= x >> 17; x ^= x << 5; x *= 2654435761U` | x |
| `fpu-f64` | x0 = (seed mod 1000 + 1) / 1001, 이후 `x = 3.9 * x * (1.0 - x)` | ⌊x × 2³²⌋ |

```json
{"task_id": "t0", "pattern": "fpu-f64", "arrays": {"seed": {"array_id": "s0", "offset_elements": 0}},
 "iterations": 1000, "sweeps": 4, "core": 0, "period_ticks": 2}
```

- job은 sweep 결과의 합(32비트)을 checksum으로 낸다. 기댓값은 Python이 같은 순서의 연산으로 계산한다. FPU는 정확히
  반올림되는 사칙연산만 쓰고 2³² 곱은 오차가 없어, 비트 단위로 같다. laysim 확인(2026-10-16, fixture
  `tests/periodic/multi_array/fixtures/compute-laysim-p.json`): 두 커널 모두 checksum이 맞았고, 반복 4배에 job CPU가
  3.9배였다(1,000번 × 4 sweep에 약 150 µs).
- 메모리 접근은 sweep당 1번이라 HARA의 CLS는 sweep 수로만 정해진다(4 sweep이면 처음 1번만 miss해 0.75, 1 sweep이면 0).
  그래서 분석은 job의 정적 IR 명령 수도 기록한다(`locality.json`의 `ir_instructions`, `chaser.locality.instructions`가 APE의
  블록별 실행 횟수와 명령 종류로 셈, sleep 구간은 합침). IR load·store 수가 HARA 접근 수와 다르면 분석을 멈춘다.
  `chaser.policy.pfirst.inputs`는 이 값으로 MPKI(명령 1,000개당 L1 miss)를 계산하고, 배치는 CLS ≤ 0.5 **그리고**
  MPKI ≥ `placement.MPKI_MIN`(1.2: L1 안에서 끝나는 task의 최대 0.32와 메모리를 쓰는 task의 최소 4.4의 로그 중간,
  개발 자료로 다시 정해 확증 전에 동결)인 task만 캐시 task로 묶는다(MPKI를 모르면 CLS만 본다).
- 반복 횟수가 상수가 아닌 반복문(PolyBench SYRK·TRMM의 삼각형 반복문)은 YARDA가 블록 실행 횟수를 내지 않아
  `ir_instructions`가 `null`이다.
- 관측 MPKI(2026-10-16): 전치·corner turn 58–67, PolyBench(CLS 0.93–0.97) 4.4–8.7, 1 KiB 순환 읽기 0.002–0.32,
  ALU·FPU 0.005–0.03.

### 2.3. 다중 배열 smoke 실행

현재 workspace root에서 실행하고, 이미 존재하지 않는 output 이름을 선택한다.
분석기 준비는 루트의 `sh scripts/verify`를 따른다. SIM에는 §1의 유효한 DISPLAY가 필요하다.

```sh
export multi_trial=.cache/periodic-multi-array/my-gemm-v1
(
set -eu
python3 -m tools.rtems_periodic prepare \
  configs/periodic-multi-array/gemm-u32-smoke.json \
  --output "$multi_trial/prepared"
python3 -m tools.rtems_periodic analyze "$multi_trial/prepared"
for architecture in g c p; do
  python3 -m tools.rtems_periodic run "$multi_trial/prepared" \
    --architecture "$architecture" --runs 1 --timeout 60 \
    --output "$multi_trial/$architecture"
done
# mode=1은 task index 0의 독립 P 실행이다.
python3 -m tools.rtems_periodic run "$multi_trial/prepared" \
  --architecture p --mode 1 --runs 1 --timeout 60 \
  --output "$multi_trial/isolated-1"
)
```

두 task 예제는 prepare의 config 경로와 output 이름을 바꿔 실행한다.
각 task의 독립 U에는 `--mode 1`, `--mode 2`를 각각 새 output으로 실행하고
`--runs`를 해당 입력의 `u_repeats`와 맞춘다. 위 예제의 현재 값은 1이다.
긴 측정은 [SIM 실행 절차](EXECUTION.md#build-and-run)의 supervisor 방식으로 실행한다.
재검증은 [batch 검증](EXECUTION.md#build-and-run)과
[raw 조회](RAW-LOGS.md#raw-logs)의 `load_batch()` 예제에서 root를 `$multi_trial`로 지정한다.

`prepared/layout.json`은 task마다가 아니라 고유 배열마다 실제 ELF 주소·크기를
기록한다. plan task의 `allocation_bytes`, `unique_accessed_bytes`,
`unique_cache_lines`는 각각 참조하는 전체 할당·고유 접근 원소 bytes·고유 32 B lines다.
공유 입력이 있으므로 task별 allocation을 합해 taskset의 고유 할당으로 쓰면 안 된다.
`protocol.json`은 schema/kernel contract/O0·O2와 새 배열·커널 모듈 snapshot hash를
보존한다. `load_batch()`가 필수 hash 누락 및 config/plan/ELF/raw 변조를 거부한다.
새 prepared는 `kernel-inputs/`에 배열 검증 코드와 커널 Python/C/template를 복사하고
manifest에 `kernel_input_hashes`를 보존한다. 분석은 현재 커널 입력과 이 hash가
다르면 새 prepare를 요구한다. run은 저장된 커널 입력을 실행 provenance로 복사하며
`load_batch()`는 C 템플릿 hash의 누락·변조도 검사한다.
직접 작성하는 C 커널의 등록·reference 계약은
[커널 인터페이스](CUSTOMIZATION.md#kernel-interface)를 따른다.

분석은 linked object별 크기·load/store 순서와 checksum용 접근을 검사한다.
clang O0 분석 stream과 SPARC workload O0/O2 provenance는 구분된다.
범위는 계속 **cold task-local job**이며 공유 입력의 coherence·task 간 간섭을
측정하지 않는다. Store는 load와 같은 demand residency로 계산하며 write traffic·
지연은 모델링하지 않는다. 결과의 `dataset_eligible=false`와 `to_measurement()`
guard는 별도 적격성 설계 전 v2 진단 결과의 자동 RF label 편입을 막는다.

<a id="multi-array-verification"></a>

### 2.4. 다중 배열 검증 기록과 후속 범위

2026-09-28 전체 `scripts/verify`는 **511 passed, 3 skipped**다.
skip은 선택적 Cachegrind/PolyBench raw/CLP export 환경 테스트다.
rank-1/2/3 형상, 행·열 padding/offset, 평탄 v2 plan hash,
사용자 매개변수 dataclass의 필수값·기본값과 typed/JSON 왕복 변환을 검사했다.
host C O0/O2에서는 비균일 비정방 GEMM, 여러 sweeps/jobs, uint32 overflow,
전체 출력·입력·padding 보존을 확인했다. 실제 APE와 G/C/P ELF의 typed
load/store·hash 접근 순서, 공유 입력, 혼합 정렬도 검증했다.
사용자 C 커널의 실행·reference stream, 잘못된 store 대상과
커널·모델 snapshot의 누락·변조 거부도 검사했다.

ATAX 전용 테스트 **20개**는 상수 초기값 checksum, 비균일 입력과 overflow,
O0/O2 수치 결과, padding·offset, 반복 job의 scratch/output 초기화,
입력 공유·쓰기 독점 계약을 검사한다. SPARC G/C/P ELF와 실제 APE stream의
작은 회귀 fixture의 109 accesses 일치 및 C/Python snapshot 포함도 O0/O2에서 확인했다.
실제 MEDIUM 크기와 원본 30종의 실행 결과는 [PolyBench 안내](../polybench/README.md)를 참고한다.
ATAX의 SIM/HW 실행은 수행하지 않았다.

SIM은 이번 변경 후 재실행하지 않았다. 앞서 수행한 다중 배열 smoke는
**20/20 성공**했고, 형상 기반 GEMM과 C 생성 모듈 분리 후 G/C/P SIM도
각각 **3/3 성공**했다. 각 결과는 `load_batch()` 재검증을 통과했다.
형상 기반 실행의 prepared·raw·검증 로그는
`.cache/periodic-multi-array/shape-kernel-interface/`에,
C 생성 모듈 분리 후 실행은 `.cache/periodic-multi-array/codegen-refactor/`에 있다.

아래 경로는 `.cache/periodic-multi-array/` 아래의 로컬 검증 산출물이다.
버전 관리되는 예제 JSON과 구분하며 `.cache` 삭제 시 함께 사라진다. 2026-10-06에 삭제해 지금은 없다.

| 경로 | 증거 |
|---|---|
| `verification.log` | 전체 빌드·분석·pytest 검증 로그 |
| `gemm-u32/smoke-002/summary.json` | O0 G/C/P·독립 P·empty/trace 및 O2 G/C/P, 9/9 성공 |
| `shared-smoke-summary.json` | 공유 GEMM·공유 읽기의 G/C/P와 각 task 독립 P, 10/10 성공 |
| `shared-gemm/smoke-001/`, `shared-reads/smoke-001/` | 위 공유 실험의 prepared·raw·protocol과 독립 U 결과 |
| `gemm-u32-overflow/smoke-001/` | A=0xffffffff, B=0xfffffffe, O2의 SPARC P 실행·재검증 성공 |

각 batch를 `load_batch()`로 재검증했으며 독립 P 결과는 해당 실험의
`characterization.json`에 보존했다. 성공한 SIM은 `DISPLAY=165.246.44.80:90.0`을
사용했다. 초기 기본 DISPLAY 연결 실패도 `gemm-u32/smoke-001/p/0.log`에 남겼다.
외부 false-sharing 전용 runner는 이 worktree에 없어 호환성을 검증하지 않았다.

성능 sweep, float32, 공유 쓰기와 HW 검증은 후속 범위다. 정책 비교에서는
독립 P로 U를 확인한 뒤 주기를 정하고, G/C/P에 같은 작업량을 사용한다.
최적화·배치·주기·sweeps를 한 번에 바꾸지 않으며 공유 입력과 private 대조군의
고유 footprint 차이도 기록한다. 기능 smoke를 통계적 성능 결론으로 해석하지 않는다.
