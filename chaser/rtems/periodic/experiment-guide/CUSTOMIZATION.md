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
| v2 배열 크기·타입·offset·GEMM 차원 | 원본 JSON의 `arrays`와 task별 커널 필드 | 자료형·bounds·공유 소유권, 접근 수·출력 검증 |
| 새로운 접근 순서·load/store·산술/FPU 코드 | v2는 `chaser/periodic/kernels/`와 `arrays.py`; legacy는 `patterns.py` 및 패턴별 모듈 | reference stream·횟수·checksum·plan/provenance 및 분석 가정 |
| RTEMS task 생성·phase·계측 경계 | `rtems/periodic/init.c`, `probe.c/h` | source와 Python plan/parser의 계약 일치 |
| G/C/P scheduler 구성 | `build.py::topology_header()`, `init.c::scheduler_index()`, `measurement.py::make_plan()` 및 topology ID | 실제 scheduler와 기대 domain 일치 |
| workload 최적화 | 원본 JSON의 `workload_optimization` (`O0`/`O2`) | workload와 init/probe의 compile_commands, ELF 주소, checksum |
| compiler/BSP·링커 배치 | `rtems/periodic/wscript`, `chaser/periodic/build.py`와 전용 runner의 빌드 설정 | compile_commands, ELF 주소, layout 검사·manifest |
| 분석기의 캐시 형상·정책 | 생성 시 복사하는 `rtems/baseline/cache.yaml` | 분석기 지원 여부; 실제 HW 설정과 구분 |
| 실제 cache/clock/SDRAM 환경 | 보드/BSP 초기화 또는 simulator가 지원하는 설정 | 실제 적용값 기록, 시간 단위·비교 조건 검증 |

<a id="json-input"></a>

### 4.1. JSON: task 수·주기·sweeps·working set·배치

이 절의 수정 예제는 legacy 입력이다. v2 배열·커널 필드는
[다중 배열 입력](INPUTS.md#multi-array)을 따른다.

```sh
mkdir -p .cache/configs/periodic-memory-gap/my-study
cp .cache/configs/periodic-memory-gap/paired-pass-12-sweeps4-balanced-full.json \
  .cache/configs/periodic-memory-gap/my-study/configuration.json
```

복사한 파일의 `workload_id`를 새 이름으로 바꾸고 task 수·core·pattern·distinct·
stride·sweeps·period·horizon·warm-up 등을 수정한다. 최상위
`array_alignment_bytes`는 32 또는 4096이며 생략 시 4096이다.
수정한 입력으로 **새 output에 prepare**를 실행한다.

기존 prepared의 C/header/JSON을 직접 고치면 manifest가 깨진다.
원본 JSON 변경이 이미 빌드한 ELF에 자동 반영되지는 않는다.

두 입력 형식에 공통인 task·job 제한과 legacy 패턴의 제약:

- Task 수 1–32, core 0–3, task_id는 고유한 C identifier.
- 모든 task period는 horizon과 warm-up 구간을 나누어떨어지게 해야 한다.
- `job_count=horizon_ticks/period_ticks`, `warmup_jobs=warmup_ticks/period_ticks`.
  혼합 주기는 공통 horizon에서 task별 job 수가 달라진다.
- Warm-up 포함 전체 job 레코드는 최대 4096. 예를 들어 32×220 jobs는
  7040이므로 현재 공용 생성기의 제한을 넘는다.
- Legacy pattern마다 추가 제약이 있다. 예를 들어 paired-pass를 cyclic으로 바꾸면
  cyclic에서 허용하지 않는 `width`도 제거한다.
- Legacy의 `distinct`는 논리적 byte 위치 수다. Stride에 따라 고유 line 수·set 배치가
  달라지므로 주소 범위와 캐시 working set을 구분한다.

다음은 원본 12-task 예시를 주기 6→12 ms, sweeps 4→8로 바꾸되
task당 warm-up 20개·측정 200개를 유지하는 예다. Horizon과 warm-up tick도
함께 바꾼다. 위에서 복사한 `my-study/configuration.json`을 덮어쓰므로
다른 수정본이 있으면 새 파일명을 사용한다.

```sh
python3 - <<'PY'
import json
from pathlib import Path
from chaser.periodic.measurement import make_plan

source = Path('.cache/configs/periodic-memory-gap/paired-pass-12-sweeps4-balanced-full.json')
destination = Path('.cache/configs/periodic-memory-gap/my-study/configuration.json')
config = json.loads(source.read_text())
config['workload_id'] = 'my-paired-pass-12-p12-s8-v1'
config['horizon_ticks'] = 12 * 220
config['warmup_ticks'] = 12 * 20
for task in config['tasks']:
    task['period_ticks'] = 12
    task['sweeps'] = 8
for architecture in range(3):
    plan = make_plan(config, architecture)
    print(architecture, plan['warmup_jobs'], plan['measurement_jobs'])
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(config, indent=2) + '\n')
PY

python3 -m tools.rtems_periodic prepare \
  .cache/configs/periodic-memory-gap/my-study/configuration.json \
  --output .cache/periodic-memory-gap-v1/my-study-v1/prepared
```

이 예시는 단위 시간당 명목 접근 횟수를 유지하지만 실제 CPU 이용률 U가 같다는
보장은 없다. U를 통제하려면 변경한 workload의 독립 P characterization이 필요하다.

Task 수와 working set도 바꾸려면 위 Python 예제에서 `make_plan()`을 호출하기
전에 다음 블록을 적용한다. `config`는 원본 JSON을 읽은 dict다.

```python
from copy import deepcopy

template = deepcopy(config['tasks'][0])
config['workload_id'] = 'my-paired-pass-16-wss4k-p10-s8-v1'
config['horizon_ticks'] = 10 * 220
config['warmup_ticks'] = 10 * 20
config['array_alignment_bytes'] = 32
config['tasks'] = [
    dict(template, task_id=f't{i:02d}', core=i % 4,
         distinct=128, stride=32, sweeps=8, period_ticks=10)
    for i in range(16)
]
```

결과는 16 tasks, P의 코어별 4 tasks, task당 128개의 32 B line=4 KiB,
주기 10 ms, warm-up 20+측정 200 jobs다. 총 기록은 3520개로 현재 제한 이하다.
`paired-pass/width=8`의 블록 크기 16이 distinct=128을 나누어떨어지게 한다.
접근 수는 단순히 `distinct*sweeps`가 아니라 패턴식에 따라 3072 loads/job이다.
P의 코어당 task 데이터 합 16 KiB는 OS·stack까지 포함한 상주 보장이 아니다.

배치만 비교하고 싶으면 같은 config에서 `task['core']`만 바꾼 별도 입력을 만든다.
예를 들어 `core=i//4`는 연속된 네 task를 같은 코어로 묶는다. Task가 모두 같다면
이 순서 변경만으로 큰 효과가 생긴다고 기대할 수 없고, 이질적인 task의 배치 비교에
유용하다. Task 수를 늘릴 때는 ID 중복·기록 한도·총 데이터 크기·deadline도 확인한다.

### 4.2. CLI: 실행 반복·timeout·계측 모드

ELF를 그대로 두고 P를 독립 프로세스 5회, 실행당 최대 7200초로 재측정하는 예다.
새 output을 사용한다. `prepared`는 이미 빌드한 환경이다.

```sh
prepared=.cache/periodic-memory-gap-v1/my-study-v1/prepared
batch=.cache/periodic-memory-gap-v1/my-study-v1/p-repeat5
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
거부하며, legacy는 모든 미사용 key를 거부하지는 않는다. 생성된 source·plan·
실제 compile command에서 적용 여부를 확인한다.

새 legacy 패턴은 C 생성뿐 아니라 `job_access_count()`, `access_offsets()`와
checksum 기대값을 맞춘다. v2 커널은 `kernels/`의 정규화·source·reference event와
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

아래 코드는 **원본에 적용할 수정 예시**다. 문서를 추가하면서 생성기 자체를
변경한 것은 아니다. 새 이름을 JSON에 넣기 전에 대응 코드를 구현해야 한다.

**예 A: `reverse-cyclic` 패턴 추가.** 기존 cyclic과 접근 수는 같고 순서만
역순으로 바꾼다. `chaser/periodic/patterns.py`에서 다음 다섯 부분을 맞춘다.

1. `validate_pattern()`의 허용 패턴과 cyclic의 region-field 금지 조건에
   `reverse-cyclic`을 함께 넣는다. `width`는 기존처럼 허용하지 않는다.

```python
# validate_pattern()의 기존 대응 조건을 교체한다.
if pattern not in ('cyclic', 'reverse-cyclic', 'hot-cold', 'phase'):
    raise ValueError('Invalid workload pattern')
fields = ('hot_distinct', 'hot_repeats', 'cold_repeats')
if pattern in ('cyclic', 'reverse-cyclic'):
    if any(key in task for key in fields):
        raise ValueError('Region parameters are not valid for cyclic workloads')
    return
```

2. `job_access_count()`에서 cyclic의 수식 분기를 공유한다.

```python
if task.get('pattern', 'cyclic') in ('cyclic', 'reverse-cyclic'):
    return task['sweeps'] * task['distinct']
```

3. `access_offsets()`의 region 처리 전에 다음 분기를 추가한다.

```python
if pattern == 'reverse-cyclic':
    for _ in range(task['sweeps']):
        yield from range((task['distinct'] - 1) * task['stride'],
                         -1, -task['stride'])
    return
```

4. `kernel_body()`의 region 처리 전에 다음 분기를 추가한다.

```python
if pattern == 'reverse-cyclic':
    last = (task['distinct'] - 1) * stride
    return [f'    for (int i = {last}; i >= 0; i -= {stride})',
            f'        sum += data_{name}[i];']
```

5. `loop_iterations()`도 cyclic과 같은 비-region 패턴으로 취급한다.
   기존 `overhead` 계산부터 함수 끝까지 다음과 같이 바꾼다.

```python
overhead = task['sweeps']
if pattern not in ('cyclic', 'reverse-cyclic'):
    overhead += task['sweeps'] * (task['hot_repeats'] + task['cold_repeats'])
    if pattern == 'phase':
        overhead += task['sweeps'] + 1
return job_access_count(task) + overhead
```

JSON 예시는 `pattern=reverse-cyclic, distinct=8, stride=32, sweeps=2`다.
기대 offset은 `[224,192,160,128,96,64,32,0]` 두 번, checksum은 배열을 1로
초기화하므로 16이다. 수정한 `loop_iterations()`의 비-region 경로는 이 경우
18을 반환한다. 이 세 값을 회귀 검사하고 generated C의 순서와 비교한다.
Prepare 및 analyze로 실제 ELF의 주소·byte-load stream까지 확인한다.

**예 B: load와 FPU 연산을 섞은 전용 job.** 아래는 생성해야 할 C 함수의 예시다.
배열 선언·초기화·함수 포인터 등록은 전용 생성기가 수행해야 한다.

```c
uint32_t task_job_example(void)
{
    uint32_t sum = 0;
    float fp = 0.0f;
    for (int i = 0; i < 64; ++i) {
        uint8_t value = data_example[i * 32];
        sum += value;
        fp += (float)value * 1.5f;
    }
    return sum + (uint32_t)fp;
}
```

전제는 `volatile uint8_t data_example[64 * 32]`의 전체 요소를 1로 초기화하는 것이다.
이 job은 64번 load하고 checksum은 64+96=160이다. legacy private-byte plan의
checksum=load 수 규칙과 다르므로 전용 planner/생성기와 `workload_expected[]`를
모두 160에 맞춘다. `job_access_count()`를 160으로 바꿔 맞추면 안 된다.
`sum`만 반환하면 최적화로 불필요한 FPU 연산이 제거될 수 있어 결과에 포함한다.

현재 `init.c`는 worker를 `RTEMS_FLOATING_POINT`로 생성하고 wscript도 hard-float를
지정한다. 다른 BSP에서는 이를 재확인한다. Disassembly에서 FPU 명령과 load 수를
확인하고 checksum·G/C/P 동일 코드를 검증한다. Store도 추가하면 쓰기 대상·기대값·
read/write 분석을 함께 설계해야 한다. 기존 private-load 분석 적격성은 이월하지 않는다.

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

**① `build.py::topology_header()`의 할당 배열**

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
