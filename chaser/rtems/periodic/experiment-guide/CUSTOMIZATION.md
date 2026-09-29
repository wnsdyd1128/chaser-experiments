# 실험 환경 수정

[전체 실험 안내](../EXPERIMENT-GUIDE.md) · 명령은 workspace root 기준이다.

## 4. 환경 수정하기

수정 위치는 변경하려는 대상에 따라 다르다. 아래 코드 경로는 workspace 기준이다.
**원본 입력/생성 소스를 수정하고 새 prepared를 만드는 것**이 공통 절차다.

| 바꿀 대상 | 수정 위치 | 새 실행 전 확인 |
|---|---|---|
| task 수·주기·sweeps·작업집합·core 배치 | 원본 configuration JSON | `make_plan()` 검증, job 수·접근 수·domain |
| 독립 실행 횟수·timeout·로그 경로 | 공용 CLI의 `--runs`, `--timeout`, `--output` | ELF 재빌드 없이 새 run output 사용 가능 |
| 공유 라인 실험의 쌍 수·주기·작업량·반복 수 | false-sharing 원본 scenario JSON | 전용 prepare 재실행, 두 layout 확인 |
| v2 배열 형상·크기·타입·offset | 원본 JSON의 `arrays[].shape/strides_elements/length`와 task binding | 자료형·bounds·공유 소유권, GEMM 차원 유도·출력 검증 |
| 새로운 접근 순서·load/store·산술/FPU 코드 | `kernels/`의 C 템플릿·Python 계약·등록 표 | reference stream·횟수·checksum·plan/provenance 및 분석 가정 |
| RTEMS task 생성·phase·계측 경계 | `rtems/periodic/init.c`, `probe.c/h` | source와 Python plan/parser의 계약 일치 |
| G/C/P scheduler 구성 | `codegen/project.py::topology_header()`, `init.c::scheduler_index()`, `measurement.py::make_plan()` 및 topology ID | 실제 scheduler와 기대 domain 일치 |
| workload 최적화 | 원본 JSON의 `workload_optimization` (`O0`/`O2`) | workload와 init/probe의 compile_commands, ELF 주소, checksum |
| compiler/BSP·링커 배치 | `rtems/periodic/wscript`, `chaser/periodic/build.py`와 전용 runner의 빌드 설정 | compile_commands, ELF 주소, layout 검사·manifest |
| 분석기의 캐시 형상·정책 | 생성 시 복사하는 `rtems/baseline/cache.yaml` | 분석기 지원 여부; 실제 HW 설정과 구분 |
| 실제 cache/clock/SDRAM 환경 | 보드/BSP 초기화 또는 simulator가 지원하는 설정 | 실제 적용값 기록, 시간 단위·비교 조건 검증 |

<a id="json-input"></a>

### 4.1. JSON: task 수·주기·sweeps·working set·배치

입력은 `schema_version: 2`를 사용하며,
배열·커널 필드는 [다중 배열 입력](INPUTS.md#multi-array)을 따른다.
다음은 버전 관리되는 GEMM 예제의 주기와 반복 수를 바꾸는 예다.

```sh
python3 - <<'PYCONFIG'
import json
from pathlib import Path
from chaser.periodic.measurement import make_plan

config = json.loads(Path('configs/periodic-multi-array/gemm-u32-smoke.json').read_text())
config['workload_id'] = 'my-gemm-p12-s8-v1'
config['horizon_ticks'] = 12 * 220
config['warmup_ticks'] = 12 * 20
for task in config['tasks']:
    task['period_ticks'] = 12
    task['sweeps'] = 8
for architecture in range(3):
    make_plan(config, architecture)
destination = Path('.cache/configs/periodic-multi-array/my-study/configuration.json')
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(config, indent=2) + '\n')
PYCONFIG

python3 -m tools.rtems_periodic prepare \
  .cache/configs/periodic-multi-array/my-study/configuration.json \
  --output .cache/periodic-multi-array/my-study-v1/prepared
```

원본 JSON을 수정하고 **새 output에 prepare**를 실행한다. 기존 prepared의
C/header/JSON을 직접 고치면 manifest가 깨진다. 원본 변경은 이미 빌드한 ELF에
자동 반영되지 않는다.

- Task 수 1–32, core 0–3, task_id는 고유한 C identifier다.
- 모든 period는 horizon과 warm-up 구간을 나누어떨어지게 해야 한다.
  `job_count=horizon_ticks/period_ticks`, `warmup_jobs=warmup_ticks/period_ticks`다.
- Warm-up 포함 전체 job 레코드는 최대 4096개다.
- 배열 크기는 `shape`/`length`, 간격은 `strides_elements`, 정렬은 배열별
  `alignment_bytes`(32 또는 4096)로 지정한다. GEMM은 shape에서 차원을 유도한다.
- 읽기 커널의 `distinct`는 역할별 접근 위치 수이고 `stride_bytes`는 바이트 간격이다.
  고유 cache line 수와 접근 횟수는 서로 다르다.
- Task를 복제할 때 읽기 입력은 공유할 수 있지만 쓰기 배열은 별도로 할당해야 한다.

배치만 비교하려면 `task['core']`만 바꾼 별도 입력을 만든다. 주기·sweeps를 바꿀
때 실제 CPU 이용률 U가 유지된다는 보장은 없으므로 독립 P characterization으로
다시 확인한다. Warm-up 20개·측정 200개를 사용하는 위 예제는 task당 220 jobs다.

### 4.2. CLI: 실행 반복·timeout·계측 모드

ELF를 그대로 두고 P를 독립 프로세스 5회, 실행당 최대 7200초로 재측정하는 예다.
새 output을 사용한다. `prepared`는 이미 빌드한 환경이다.

```sh
prepared=.cache/periodic-multi-array/my-study-v1/prepared
batch=.cache/periodic-multi-array/my-study-v1/p-repeat5
nohup python3 -u -m tools.rtems_periodic run "$prepared" \
  --architecture p --runs 5 --timeout 7200 --output "$batch" \
  > "${batch}-supervisor.log" 2>&1 < /dev/null &
echo $! > "${batch}-supervisor.pid"
```

이 변경에는 prepare가 필요 없다. `u_repeats`는 이 CLI의 `--runs`를 대신하지 않는다.
G/C도 각 architecture와 output을 바꾼다. DISPLAY 설정은
[SIM 실행 절차](EXECUTION.md#build-and-run)를 따른다.
정상 완료 후 `load_batch()`로 5개 결과를 검사하고 run 간 분산을 비교한다.

스케줄 전환을 진단하려면 동일 run 명령에 `--trace`를 추가하고 output도
`p-trace`처럼 별도로 지정한다. `--empty`는 workload 대신 empty job을 실행한다.
두 모드의 결과는 일반 timing 결과와 섞지 않는다. Trace overflow라면
`rtems/periodic/probe.c`의 `TRACE_CAPACITY` 확대(예: 8192→16384)를 검토하고
새로 prepare한다. 버퍼가 커지면 메모리 배치도 달라지므로 기존 결과와 구분한다.

### JSON 범위를 넘어서는 수정

현재 공용 JSON에는 임의 C 함수 삽입, FPU 연산 비율, task별 phase,
C의 2+2 topology를 지정하는 옵션이 없다. Workload 최적화는
`workload_optimization: "O0" | "O2"`로 지원한다. v2는 허용하지 않는 필드를
거부한다. 생성된 source·plan·
실제 compile command에서 적용 여부를 확인한다.

새 커널은 `kernels/`의 정규화·source·reference event와
load/store count·checksum·loop budget을 함께 구현한다. 공용 분석은 v2의 typed
load/store와 여러 object를 검증한다. FPU·공유 쓰기는 아직 지원하지 않으므로
별도 수치·소유권·동기화·분석 계약이 필요하다. False-sharing 전용 생성기는
v2의 읽기 공유와 별도 경로다.

Tick 크기 변경은 `period_ticks` 변경과 다르다. Tick 자체를 바꾸려면
`init.c`의 `CONFIGURE_MICROSECONDS_PER_TICK`·`TICK_NS`, Python의 `TICK_NS`와
parser/plan, BSP timer 설정을 함께 맞춘다. Scheduler 변경도 topology.h만
바꿔서는 안 되고 plan의 domain·topology identity·검증을 함께 갱신해야 한다.

`wscript`의 CFLAGS 변경은 workload뿐 아니라 init/probe에도 영향을 준다.
`workload_optimization`은 workload.c에만 적용되고 init/probe는 O0를 유지한다.
SDK/BSP를 변경하면 공용 build와 전용 runner의 경로·pkg-config·manifest 대상도
확인한다. Linker 주소를 바꾸면 `check_layout()`의 기대 주소도 맞춰야 한다.

### 4.3. 생성 코드: 새로운 접근 순서·산술/FPU

<a id="kernel-interface"></a>

#### v3: 원본 PolyBench C 소스

[원본 PolyBench 경로](../polybench/README.md)는 30종의 원본 C·header와 MEDIUM
설정을 보존한다. JSON의 `polybench.benchmark`로 catalog 항목을 선택하며,
자료형을 uint32로 바꾸지 않는다. `chaser/periodic/polybench/sources.py`의
어댑터는 고정 revision의 main을 초기화·kernel 호출·출력 검증으로 나눈다.
커널 배열은 ELF 주소를 갖는 전역 storage로 옮기고 원본 루프는 유지한다.

이 경로는 benchmark 하나당 task 하나를 제공한다. 매 job의 reset과 live-out
검증은 측정 bracket 밖이며, 기존 v2의 Python reference-event 계약을 대신하지
않는다. `trace_validation: not-validated`인 YARDA 결과를 reference 검증 통과로
해석하면 안 된다. upstream 수정 시 revision·native 출력 비교·전체 분석 결과를
함께 갱신하고 새 snapshot으로 `prepare/analyze/run`한다.

#### v2: 직접 작성하는 C 커널과 Python 계약

현재 구현된 인터페이스는 **원본 JSON + 커널 C 템플릿 + Python 계약**이다.
GEMM의 C 루프는 [gemm.c.in](../../../chaser/periodic/kernels/gemm.c.in)에,
검증·reference stream·checksum·stride 값은
[gemm.py](../../../chaser/periodic/kernels/gemm.py)에 있다.
JSON에는 형상·타입·binding·주기·sweeps를 두고, 연산 변경은 원본 C에 작성한 뒤
새 output으로 공용 prepare/analyze/run을 사용한다. prepared/workload.c를 직접
고치거나 JSON 문자열에 임의 C를 넣는 인터페이스는 제공하지 않는다.

추가 구현 예시는 [PolyBench 기반 ATAX](INPUTS.md#polybench-atax)다.
[atax.c.in](../../../chaser/periodic/kernels/atax.c.in)의 행렬·벡터 연산과
[atax.py](../../../chaser/periodic/kernels/atax.py)의 검증·reference stream을
같이 볼 수 있다. `NoParameters`를 사용해 차원을 배열 shape에서 읽고,
`write_roles=('tmp', 'y')`로 임시 배열과 출력의 독점 소유권을 선언한다.
별도 planner 분기나 runner 없이 공용 prepare/analyze/run으로 실행한다.

새 커널은 같은 소유 디렉터리에 `<name>.py`, `<name>.c.in`을 만들고
[kernels/__init__.py](../../../chaser/periodic/kernels/__init__.py)의 `KERNELS`에
명시적으로 등록한다. Python 모듈은 신뢰하는 프로젝트 코드이며 JSON에서 임의
모듈을 import하지 않는다. 보조 코드와 `.h`도 `kernels/` 아래에 두어 snapshot에 포함한다.

| 인터페이스 | 계약 |
|---|---|
| `Kernel(module, roles, parameter_type=NoParameters, write_roles=())` | 매개변수 dataclass의 필드에서 허용/필수 JSON key를 유도. 기본값 없는 필드는 필수. 쓰기 object는 task 간 독점 |
| `module.validate(task, registry)` | `TaskSpec`·`ArrayRegistry`를 받아 타입·shape·bounds를 검증하고 `KernelMetrics` 반환. `task.parameters`의 선택 값 유도 가능 |
| `module.events(task, registry)` | sweeps와 checksum용 접근을 포함한 **한 job 전체**의 실제 순서. `ReferenceEvent(array_id, offset_bytes, access_size_bytes, operation)`을 yield |
| `module.source(task, registry)` | `task_job_<task_id>(void)`를 정의하는 C 문자열 **목록** 반환. C 템플릿을 읽는 `render_template()` 사용 가능 |
| `module.footprint(task, registry)` | 선택적 빠른 계산. `MemoryFootprint(allocation_bytes, unique_accessed_bytes, unique_cache_lines)` 반환. 생략하면 reference events로 계산하며 count·typed bounds·쓰기 권한도 검사 |

내부 모델은 [`workload/model.py`](../../../chaser/periodic/workload/model.py)에 정의한다.
`ArrayRegistry`는 `dict[str, ArraySpec]`, `task.arrays`는 `dict[str, ArrayBinding]`이다.
배열은 `array.symbol`, `array.length`, `array.shape`처럼 속성으로 읽는다. 형상을
선언하면 shape/strides_elements는 tuple이며, 미선언이면 None이다. binding의
`offset_elements`는 바이트가 아닌 원소 단위다. `task.parameters`는 GEMM의
`GemmParameters`, 읽기 커널의 `ReadParameters` 또는 사용자 정의 dataclass다.

`KernelMetrics` 필드는 `source_loads`, `source_stores`, `expected_checksum`,
`checksum_kind`, `loop_iterations`이고 `source_accesses`는 계산된 property다.
`normalize_task()`가 metrics와 footprint를 채운 뒤에 source/events를 호출한다.
validate/events/footprint에서 dict를 반환하던 사용자 모듈은 이 dataclass 반환형으로
수정해야 한다. `KernelImplementation` Protocol이 모듈의 필수 함수 계약을 명시한다.

예를 들어 아래 선언은 JSON의 count를 필수로, increment를 기본값 0인 선택 필드로
정의한다. 커널에서는 `task.parameters.count`, `task.parameters.increment`로 읽고
validate에서 수치 범위·타입·bounds를 확인한다. Dataclass 생성 자체는 입력 검증을
대신하지 않는다. 공통 task 필드나 계산 결과와 겹치지 않는 매개변수 이름을 사용한다.

```python
from dataclasses import dataclass

@dataclass
class CopyParameters:
    count: int
    increment: int = 0
```

JSON 입력과 저장된 plan의 필드 형식은 그대로다. 정규화 때 dataclass로 변환하고
`TaskSpec.to_dict()`/`ArraySpec.to_dict()`로 plan에 기록한다. 저장된 task를 읽을 때는
`task_from_plan()`을 사용한다. `workload_source()`는 저장된 dict와 정규화된
`TaskSpec`/`ArraySpec`을 모두 받을 수 있다. 생성기 내부는 별도
[`codegen/model.py`](../../../chaser/periodic/codegen/model.py)의 `ArrayDeclaration`,
`JobDefinition`, `PolicyHeader`·`TaskSchedule`을 사용한다.

공용 검사기는 job당 10,000,000 source accesses 상한을 적용한다. validate 내부에서
checksum 등 큰 반복을 수행한다면 먼저 이 상한을 검사해야 한다.
분석 단계에서는 빠른 footprint를 제공한 커널도 reference count·bounds·권한을 검사한다.
이는 Python 계약의 자기 일관성 검사이며 C의 정확성 증명을 대신하지 않는다.

`render_template(path, task, registry, **substitutions)`는 다음 값을 치환한다.

- `${task_id}`, `${sweeps}` 등 공통 필드와 매개변수 dataclass·metrics의 필드.
- `${A}`처럼 역할 이름은 기본적으로 물리 배열 symbol, `${A_offset}`은 원소 offset.
- 모듈이 전달한 추가 정수·식별자. GEMM은 `${A_step}` 같은 열 stride를 전달하고
  `${A}[${A_offset} + i * ${lda} + k * ${A_step}]` 주소식은 C 파일에 직접 작성한다.

치환값은 정수 또는 C identifier만 허용하며 C 식·문장 문자열, bool, float는 거부한다.
인덱스 계산·연산자·분기·루프는 C 템플릿에 둔다. `reads.c.in`도 같은 규칙을 따른다.
커널 선택은 `Kernel` 전략으로, 공통 C 파일의 조립은
[`codegen/workload.py`](../../../chaser/periodic/codegen/workload.py)로 분리한다.
[`codegen/project.py`](../../../chaser/periodic/codegen/project.py)는 RTEMS 파일과 정책
header를 생성하고 `build.py`는 빌드·ELF 검사·manifest 절차를 조정한다.
정적 공개 header와 linker script의 원본은 `rtems/periodic/workload.h`, `layout.ld`다.
기존 `build.workload_source()`와 `build.topology_header()` import는 계속 사용할 수 있다.

문자 그대로의 `$`는 템플릿에서 `$$`로 쓴다. 예를 들어 새 커널이 유효한 N개
uint32 입력을 합한다면 C 본문을 아래처럼 직접 작성할 수 있다. validate는 N개
typed 접근의 bounds와 sweeps*N load 수, 초기값 기반 checksum을 확인해야 한다.
events도 이 루프의 순서를 그대로 정의한다.

```c
/** @brief Sum the validated input span. @return Unsigned sum modulo 2^32. */
ANALYZE uint32_t task_job_${task_id}(void) {
    uint32_t sum = 0;
    for (int s = 0; s < ${sweeps}; ++s)
        for (int i = 0; i < ${count}; ++i)
            sum += ${input}[${input_offset} + i];
    return sum;
}
```

생성기는 전역 volatile 배열과 초기화·함수 포인터 등록을 담당한다. C 템플릿은
배열을 다시 선언하거나 RTEMS task/계측 코드를 구현하지 않는다. 반환값은 uint32다.
`ANALYZE` root만 있어도 분석할 수 있다. 보조 함수가 필요하면 `INLINE` annotation과
`kernel_<task_id>` 또는 `kernel_<task_id>_<suffix>` 이름을 사용한다.
APE가 해석할 수 있는 bounded loop·typed 전역 접근이 필요하며, 지원하지 않는
호출·접근은 분석 실패로 다룬다. 커널 추가만으로 FPU·공유 쓰기·RF 적격성을 얻지 않는다.

**기존 GEMM에서 새 접근 순서 커널을 만드는 예:**

1. `gemm.py`와 `gemm.c.in`을 `gemm_ji.py`와 `gemm_ji.c.in`으로 복사한다.
   `source()`는 모듈 옆의 같은 이름 `.c.in`을 읽는다.
2. C 템플릿의 곱셈 루프를 j→i→k로 바꾸고 Python `events()`의 대응 루프도 바꾼다.
   출력 hash 순서는 두 파일에서 기존 i→j를 유지한다.
3. `validate()`의 loop budget은 `sweeps*(1+n+n*m+n*m*k)+m+m*n`으로 변경한다.
   이 예에서는 load/store 수·checksum·footprint는 그대로다.
4. `kernels/__init__.py`에서 모듈을 import하고 아래 항목을 추가한다.

```python
from chaser.periodic.kernels import gemm_ji
from chaser.periodic.workload import GemmParameters

# KERNELS 정의 뒤에 추가
KERNELS['gemm-u32-ji'] = Kernel(gemm_ji, ('A', 'B', 'C'),
    parameter_type=GemmParameters, write_roles=('C',))
```

5. 원본 예제 JSON을 새 이름으로 복사하고 workload_id와 pattern을 변경한다.
   `make_plan()` → host O0/O2 출력·padding 검사 → 새 prepare/analyze에서
   실제 ELF 주소·reference stream 비교 → run의 checksum·raw 재검증 순서로 확인한다.

같은 인터페이스로 새로운 연산도 등록할 수 있으며 이때는 validate/events/C를 모두
정의한다. 공용 planner나 arrays.py에 새 pattern 분기를 추가하지 않는다.
GEMM의 선택적 footprint 수식이 새 연산에도 맞는지 확인하고, 맞지 않으면
해당 hook을 생략해 정확한 event 기반 계산을 사용하거나 새 수식을 검증한다.

prepare는 `kernel-inputs/`와 manifest에 C 템플릿·Python 계약을 함께 보존한다.
원본 커널을 수정했다면 새 prepare가 필요하며 analyze는 이전 snapshot과 현재
계약이 다르면 거부한다. run/load_batch는 저장된 입력과 hash로 검증한다.
header 파일의 hash 보존이 자동 include를 의미하지는 않는다. 필요한 선언을
source()가 생성 소스에 포함해야 하며 커스텀 compiler/linker 옵션은 별도 빌드 변경이다.

### 4.4. RTEMS: task 생성·phase·계측

**Task stack을 16→32 KiB로 바꾸는 예.** `rtems/periodic/init.c`의 대응 위치를 수정한다.

```c
require(rtems_task_create(rtems_build_name('J', 'O', 'B', i), 2, 32768,
                         RTEMS_DEFAULT_MODES, RTEMS_FLOATING_POINT, &tasks[i]));

#define CONFIGURE_MINIMUM_TASK_STACK_SIZE 32768
#define CONFIGURE_INIT_TASK_STACK_SIZE 32768
```

이는 stack 용량 변경이며 priority나 period 변경이 아니다.
Prepare 후 RAM 배치와 task 생성 성공을 확인한다. Stack 주소가 달라지므로
cache 간섭도 달라질 수 있다. Worker만 바꾸려면 Init stack은 유지하고
공통 minimum 설정의 영향을 확인한다.

**Phase 변경에는 계약 확장이 필요하다.** 4 tasks, period=10 ticks,
phase=`[0,2,4,6]`이면 nominal release는 다음과 같다.

```python
release_tick = t0_tick + phase_ticks + job_index * period_ticks
deadline_tick = release_tick + period_ticks
```

이는 설계 예시이며 현재 JSON에 `phase_ticks`만 추가하면 동작하지 않는다.
최소한 다음 항목을 함께 구현한다.

| 위치 | 필요한 변경 |
|---|---|
| `make_plan()` | phase 범위 검증, task별 job 수/warm-up 수, hash 반영 |
| `prepare()` | `CHASER_PHASES` 같은 배열을 config.h에 생성 |
| `init.c` | 전체 task 준비 확인 후 각 phase에서 period를 arm하고 실행하는 시작 방식 |
| raw 출력·deadline 검사 | release와 deadline 모두에 phase 반영 |
| `aggregate()` | arm 시각 검증·release 계산·warm-up 판정·cohort 집계를 새 release에 맞춤 |
| trace 검증 | watchdog/EDF deadline과 nominal release의 대응 갱신 |

현재는 모든 task가 같은 t0에서 arm한 것을 확인하고 공통 barrier를 해제한다.
이 barrier를 유지한 채 worker에 sleep만 삽입하면 이른 phase의 task도 마지막
task를 기다리므로 의도한 release가 되지 않는다.
관측 구간을 `[0,H)`, warm-up을 `[0,W)`로 두면 phase가 있는 job 수는
`max(0, ceil((H-phase)/T))`, warm-up 수는
`min(job_count, max(0, ceil((W-phase)/T)))`다. H=2200, W=200,
T=10과 위 phase에서는 task당 220 jobs 중 20개가 warm-up이다.
이 변경은 새 측정 계약/검증 fixture로 다루고 원래 v3 기록과 혼합하지 않는다.

**계측 추가의 간단한 시작점은 §4.2의 `--trace`다.** 새 측정값을 추가하면
record 구조체·채집 위치·종료 후 출력·Python parser·저장 결과 재검증을 맞춘다.
`job()` 전후 wall time을 추가하는 것과 CPU accounting 변경은 의미가 다르다.
경계를 바꾸면 `measurement_boundary_id`와 대응 검증도 갱신하고
empty job 진단과 정상/비정상 raw 양쪽으로 확인한다.

### 4.5. 빌드: 최적화·SDK/BSP

**Workload만 O2로 빌드하기.** 원본 JSON에 다음 필드를 넣고 새 output으로
`prepare`를 실행한다. 생략하거나 `O0`을 지정하면 기본 O0 빌드다.

```json
{"workload_optimization": "O2"}
```

`wscript`는 workload 객체의 빌드 환경에만 O2를 적용한다. Kernel뿐 아니라
wrapper/초기화까지 `workload.c` 전체가 최적화된다. Init/probe는 O0이다.
`build/compile_commands.json`에서 workload만 O2, init/probe는 O0인지 확인하고
disassembly·checksum·접근 순서를 재검증한다. HARA의 별도 clang 컴파일은 여전히
O0이므로 실행 최적화의 영향을 그대로 재현한다고 가정하지 않는다.

**같은 GR740 BSP를 다른 SDK에서 쓰는 예.** `build.py`의
`SDK = Path('/opt/rtems/6')`를 예를 들어 `Path('/opt/rtems/6-alt')`로 바꾼다.
그 경로에 `bin/sparc-rtems6-gcc`, `bin/sparc-rtems6-nm`,
`lib/pkgconfig/sparc-rtems6-gr740.pc`와 BSP libraries가 필요하다.
공용 prepare는 SDK를 waf의 `--rtems-root`로도 넘긴다. CLI prepare 자체에는
`--rtems-root` 인자가 없다. False-sharing은 runner 내부 SDK 상수도 확인한다.

BSP 자체를 바꾸면 wscript의 pkg-config, manifest의 library/linkcmds 목록,
CPU/FPU flags, memory map, probe의 RTEMS 내부 구조 의존성도 수정 대상이다.
GR740을 다른 BSP 이름으로 치환하는 것만으로 4-core 계측 이식이 끝나지 않는다.
위 SDK 경로는 설명용이며 실제 존재·호환성을 확인한 뒤 사용한다.

### 4.6. Scheduler: C를 1+3에서 2+2로 변경

별도 variant의 수정 예다. G/P는 유지하고 C만 core 0–1과 core 2–3의
두 EDF scheduler로 나눈다. JSON의 `core` 의미는 유지한다.

**① `codegen/project.py::topology_header()`의 할당 배열**

```python
assignments = ([0, 0, 0, 0], [0, 0, 1, 1], [0, 1, 2, 3])[architecture]
```

**② `init.c::scheduler_index()`의 C 분기**

```c
if (ARCHITECTURE == 1) return cores[i] / 2;
```

앞의 `chaser_mode`/G 분기는 유지한다. C 분기를 수정하지 않으면 core 1의
task가 이전 규칙에 의해 잘못된 scheduler에 배치된다.

**③ `measurement.py::make_plan()`의 기대 domain과 ID**

```python
task['domain'] = (list(range(4)) if architecture == 0 else
                  ([0, 1] if task['core'] < 2 else [2, 3]) if architecture == 1
                  else [task['core']])
```

```python
TOPOLOGIES = ('g-edfsmp-4-v1', 'c-edfsmp-2-2-v1', 'p-edfsmp-4x1-v1')
```

새 `policy_id`도 부여한다. Plan은 domain/topology로 mapping hash를 다시 계산한다.
Core 0,1 지정 task의 기대 mask는 `0b0011=3`, core 2,3은 `0b1100=12`다.
Trace 없이도 raw의 `domain_mask`와 job 시작/종료 core를 검사하고 trace 진단으로
실행 중 core도 확인한다. Topology/domain 회귀 검사와 독립 U mode도 확인한다.
기존 테스트에는 1+3 기대값이 있으므로 사양 변경에 맞춘 검증이 필요하다.
이는 scheduler domain 변경이며 L2 cache의 물리 분할은 아니다.

### 변경 후 확인 순서

1. 원본 설정·변경 소스·toolchain 버전을 기록한다. 새 workload/output 이름을 정한다.
2. 새 prepared를 생성하고 `plan.json`, `workload.c`, `compile_commands.json`,
   `layout.json`에서 변경이 실제 반영됐는지 확인한다.
3. 생성기·계측 코드를 바꿨다면 관련 회귀 검증을 실행한다. 분석을 사용할 경우
   새 ELF로 locality 분석도 다시 수행한다.
4. 짧은 별도 smoke 입력으로 checksum·domain·job 수·deadline을 확인한 뒤
   정식 입력을 빌드·실행한다. 실패/timeout은 정상 표본으로 섞지 않는다.

과거 prepared의 manifest만 다시 계산해 수정 사실을 지우지 않는다.
원본과 새 결과의 소스·ELF·입력 차이를 보존한다. 공통 소스 변경은 앞으로
prepare하는 실험 전체에 적용되며, 기존 prepared에는 소급 반영되지 않는다.
