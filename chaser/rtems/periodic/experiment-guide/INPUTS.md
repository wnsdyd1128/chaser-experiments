# 입력·다중 배열 예제

[전체 실험 안내](../EXPERIMENT-GUIDE.md) · 명령은 workspace root 기준이다.

## 1. 입력과 생성 결과

| 종류 | 입력 | 생성·실행 도구 |
|---|---|---|
| 명시적 다중 배열 workload | `schema_version: 2`, `arrays`, 역할별 task binding | `python3 -m tools.rtems_periodic`의 `prepare`, `analyze`, `run`; cyclic/paired-read/gemm-u32 |
| False-sharing reader/writer | `pairs`, `layouts` 등이 있는 JSON | `.cache/configs/periodic-memory-gap/false-sharing/run.py` |

`configs/periodic-multi-array/`는 버전 관리되는 다중 배열 입력이고,
`.cache/periodic-multi-array/`는 새 worktree의 생성·분석·실행 결과 위치다.
이전 실험의 `.cache/configs/periodic-memory-gap/`는 원본 입력·시나리오 실행기,
`.cache/periodic-memory-gap-v1/`는 그 생성 환경·측정 결과 위치다.
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

SIM은 이번 변경 후 재실행하지 않았다. 앞서 수행한 다중 배열 smoke는
**20/20 성공**했고, 형상 기반 GEMM과 C 생성 모듈 분리 후 G/C/P SIM도
각각 **3/3 성공**했다. 각 결과는 `load_batch()` 재검증을 통과했다.
형상 기반 실행의 prepared·raw·검증 로그는
`.cache/periodic-multi-array/shape-kernel-interface/`에,
C 생성 모듈 분리 후 실행은 `.cache/periodic-multi-array/codegen-refactor/`에 있다.

아래 경로는 `.cache/periodic-multi-array/` 아래의 로컬 검증 산출물이다.
버전 관리되는 예제 JSON과 구분하며 `.cache` 삭제 시 함께 사라진다.

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
