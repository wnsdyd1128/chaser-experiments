# RTEMS 실험 생성·수정·재현 안내

확인: 2026-09-27. 모든 명령은 `/workspace/experiments/chaser`에서 실행한다.
여기서는 소스·ELF 생성과 laysim 실행을 다룬다. 보드 실행은
[HW 절차](HARDWARE-VALIDATION.md)를 따른다.
공용 periodic harness를 기준으로 설명하며 paired-pass와 false-sharing은 적용 예시다.
입력·output 경로는 실험별로 정할 수 있다. False-sharing 생성기는 현재 `.cache`의
시나리오 전용 도구이므로 해당 예시에는 그 도구와 입력이 필요하다.

현재 연구는 **SIM 실험을 먼저 진행해 구성·결과를 확정한 뒤 HW에서 검증**한다
(2026-09-27 사용자 지시). HW 가이드는 후속 검증용이며 다음 작업은 SIM 실험의
재집계·변수 통제·재현성 확인이다.

## 1. 입력과 생성 결과

| 종류 | 입력 | 생성·실행 도구 |
|---|---|---|
| 일반 private-array workload | `tasks` 배열이 있는 JSON | `python3 -m tools.rtems_periodic prepare/run` |
| False-sharing reader/writer | `pairs`, `layouts` 등이 있는 JSON | `.cache/configs/periodic-memory-gap/false-sharing/run.py` |

`.cache/configs/periodic-memory-gap/`는 원본 입력·시나리오 실행기의 위치다.
`.cache/periodic-memory-gap-v1/`는 생성된 환경·측정 결과의 위치다.
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

관련 구현: [CLI](../../tools/rtems_periodic.py),
[생성·빌드](../../chaser/periodic/build.py),
[계획·집계](../../chaser/periodic/measurement.py),
[빌드 옵션](wscript).

필요 환경은 Python/project imports, `pkg-config`, `/opt/rtems/6`의 SPARC
toolchain·GR740 BSP, `/opt/src/rtems/waf`다. SIM 실행에는
`/opt/laysim-gr740/laysim-gr740-cli`, `script`, `timeout`과 현재 설치에 필요한
접근 가능한 X display가 추가로 필요하다. 기존 `DISPLAY=165.246.44.80:90.0`은
이 환경의 값이며 다른 호스트에서 그대로 사용할 수 있다는 뜻은 아니다.
`prepare` 자체는 simulator/display가 필요 없다. 실행용 빌드는 기본 `-O0 -g`이고,
설정의 `workload_optimization: "O2"`로 workload.c만 O2로 빌드할 수 있다.

## 2. 예시: paired-pass 설정의 의미

입력: `.cache/configs/periodic-memory-gap/paired-pass-12-sweeps4-balanced-full.json`.

| 설정 | 의미 |
|---|---|
| tasks 12개 | P에서 코어당 3 task |
| `period_ticks=6` | 현재 1 tick=1 ms, 주기 6 ms |
| `horizon_ticks=1320` | task당 총 220 jobs |
| `warmup_ticks=120` | 앞 20 jobs 제외, 200 jobs/task 측정 |
| `sweeps=4` | job 내부 패턴 반복 수; job 수와 별개 |
| `u_repeats=5` | 독립 U characterization 계획값; G/C/P 5회 자동 실행 아님 |

실제 실행 횟수는 CLI `--runs`로 지정한다. G=4-core, C=1+3, P=4×1
EDF scheduler다. `core`는 P의 고정 코어와 C의 domain 선택에 쓰이며
G의 고정 pinning을 뜻하지 않는다.

## 3. 공용 생성기로 빌드·실행

### 소스·ELF 생성

```sh
cd /workspace/experiments/chaser
export trial_root=.cache/periodic-memory-gap-v1/my-paired-pass-12-v1
python3 -m tools.rtems_periodic prepare \
  .cache/configs/periodic-memory-gap/paired-pass-12-sweeps4-balanced-full.json \
  --output "$trial_root/prepared"
```

Output은 새 경로여야 한다. 생성되는 구조는 다음과 같다.

```text
my-paired-pass-12-v1/prepared/
  configuration.json          입력 snapshot
  source/                     workload.c/h, init.c, probe.c/h
  g/  c/  p/                  각각 plan.json, config.h, topology.h
  build/                      g.exe, c.exe, p.exe, objects
  layout.ld, layout.json      주소 배치·검사 결과
  wscript, waf, build.log     빌드 절차·실제 명령
  cache.yaml                  분석 모델 설정; HW cache enable 설정이 아님
  manifest.json               소스·ELF·빌드 파일 등의 hash
```

### 백그라운드 SIM 실행

`--timeout`은 한 simulator 실행의 **호스트 경과시간 상한(초)**이다.
RTEMS의 주기나 simulation time이 아니다. 아래 3600초는 예시이며 긴 주기·많은
jobs에는 더 큰 값이 필요할 수 있다. Timeout도 실패 raw로 보존된다.

```sh
# 현재 환경에서 사용 가능한 display로 설정한다.
export DISPLAY=165.246.44.80:90.0
cat > "$trial_root/run.sh" <<'SH'
set -eu
trap 'code=$?; printf "%s\n" "$code" > "$trial_root/supervisor.exit"' 0
for architecture in g c p; do
  printf 'started architecture=%s\n' "$architecture"
  python3 -u -m tools.rtems_periodic run "$trial_root/prepared" \
    --output "$trial_root/$architecture" \
    --architecture "$architecture" --runs 1 --timeout 3600
done
SH
nohup sh "$trial_root/run.sh" > "$trial_root/supervisor.log" 2>&1 < /dev/null &
echo $! > "$trial_root/supervisor.pid"
```

실행 shell은 즉시 돌아온다. 진행 로그와 개별 raw를 필요할 때 본다.

```sh
tail -f "$trial_root/supervisor.log"
# g/0.log가 생성된 뒤 실행한다.
tail -f "$trial_root/g/0.log"
```

RTEMS는 jobs 종료 후 상세 결과를 출력하므로 raw가 한동안 늘지 않을 수 있다.
`tail`을 종료해도 실험은 계속된다. `supervisor.exit`가 생기면 wrapper가 종료한
것이며 0은 성공이다. G/C/P는 위 wrapper에서 순차 실행한다.

각 정책 output에는 `0.log`, `measurements.jsonl`, `protocol.json`,
`boot.batch`, 계측 코드 snapshot `implementation/`이 생긴다.
`--runs 5`이면 별도 simulator 프로세스의 `0.log`부터 `4.log`까지 남긴다.

### 결과 재검증

```sh
python3 - <<'PY'
import os
from pathlib import Path
from chaser.periodic.dataset import load_batch

root = Path(os.environ['trial_root'])
for architecture in ('g', 'c', 'p'):
    for row in load_batch(root / 'prepared', root / architecture):
        if row['execution_status'] != 'ok':
            print(architecture, row['run_id'], 'FAILED', row.get('errors'), row.get('error'))
            continue
        print(architecture, row['run_id'], {
            key.replace('_ns', '_ms'): row[key] / 1e6
            for key in ('tet_ns', 'tat_ns', 'makespan_ns')
        })
PY
```

`load_batch()`는 manifest·raw hash와 원시 레코드를 재검증한다.
Raw 경로, 레코드 필드, 특정 task/job 조회와 오류 판독은 [§7](#7-raw-로그-위치와-읽는-법)을 참고한다.
공용 run은 `summary.json`을 자동 생성하지 않는다. 기존 summary는 시나리오별
실행기가 만든 것이다. 선택적인 locality 분석은 다음과 같으며 timing의 필수 단계는 아니다.
추가로 clang-14와 YARDA 빌드가 필요하다.

```sh
python3 -m tools.rtems_periodic analyze "$trial_root/prepared"
```

## 4. 환경 수정하기

수정 위치는 변경하려는 대상에 따라 다르다. 아래 코드 경로는 workspace 기준이다.
**원본 입력/생성 소스를 수정하고 새 prepared를 만드는 것**이 공통 절차다.

| 바꿀 대상 | 수정 위치 | 새 실행 전 확인 |
|---|---|---|
| task 수·주기·sweeps·작업집합·core 배치 | 원본 configuration JSON | `make_plan()` 검증, job 수·접근 수·domain |
| 독립 실행 횟수·timeout·로그 경로 | 공용 CLI의 `--runs`, `--timeout`, `--output` | ELF 재빌드 없이 새 run output 사용 가능 |
| 공유 라인 실험의 쌍 수·주기·작업량·반복 수 | false-sharing 원본 scenario JSON | 전용 prepare 재실행, 두 layout 확인 |
| 새로운 접근 순서·load/store·산술/FPU 코드 | `chaser/periodic/patterns.py`, 패턴별 `recipes.py`/`structures.py`/`staged_recipes.py`, 또는 전용 생성기 | 접근 순서·횟수·checksum 및 분석 가정 |
| RTEMS task 생성·phase·계측 경계 | `rtems/periodic/init.c`, `probe.c/h` | source와 Python plan/parser의 계약 일치 |
| G/C/P scheduler 구성 | `build.py::topology_header()`, `init.c::scheduler_index()`, `measurement.py::make_plan()` 및 topology ID | 실제 scheduler와 기대 domain 일치 |
| workload 최적화 | 원본 JSON의 `workload_optimization` (`O0`/`O2`) | workload와 init/probe의 compile_commands, ELF 주소, checksum |
| compiler/BSP·링커 배치 | `rtems/periodic/wscript`, `chaser/periodic/build.py`와 전용 runner의 빌드 설정 | compile_commands, ELF 주소, layout 검사·manifest |
| 분석기의 캐시 형상·정책 | 생성 시 복사하는 `rtems/baseline/cache.yaml` | 분석기 지원 여부; 실제 HW 설정과 구분 |
| 실제 cache/clock/SDRAM 환경 | 보드/BSP 초기화 또는 simulator가 지원하는 설정 | 실제 적용값 기록, 시간 단위·비교 조건 검증 |

### 4.1. JSON: task 수·주기·sweeps·working set·배치

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

현재 입력 계약의 주요 제한:

- Task 수 1–32, core 0–3, task_id는 고유한 C identifier.
- 모든 task period는 horizon과 warm-up 구간을 나누어떨어지게 해야 한다.
- `job_count=horizon_ticks/period_ticks`, `warmup_jobs=warmup_ticks/period_ticks`.
  혼합 주기는 공통 horizon에서 task별 job 수가 달라진다.
- Warm-up 포함 전체 job 레코드는 최대 4096. 예를 들어 32×220 jobs는
  7040이므로 현재 공용 생성기의 제한을 넘는다.
- Pattern마다 추가 제약이 있다. 예를 들어 paired-pass를 cyclic으로 바꾸면
  cyclic에서 허용하지 않는 `width`도 제거한다.
- `distinct`는 논리적 byte 위치 수다. Stride에 따라 고유 line 수·set 배치가
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
G/C도 각 architecture와 output을 바꾼다. DISPLAY 설정은 §3을 따른다.
정상 완료 후 `load_batch()`로 5개 결과를 검사하고 run 간 분산을 비교한다.

스케줄 전환을 진단하려면 동일 run 명령에 `--trace`를 추가하고 output도
`p-trace`처럼 별도로 지정한다. `--empty`는 workload 대신 empty job을 실행한다.
두 모드의 결과는 일반 timing 결과와 섞지 않는다. Trace overflow라면
`rtems/periodic/probe.c`의 `TRACE_CAPACITY` 확대(예: 8192→16384)를 검토하고
새로 prepare한다. 버퍼가 커지면 메모리 배치도 달라지므로 기존 결과와 구분한다.

### JSON 범위를 넘어서는 수정

현재 공용 JSON에는 임의 C 함수 삽입, FPU 연산 비율, task별 phase,
C의 2+2 topology, compiler 최적화 수준을 지정하는 옵션이 없다.
임의 key를 추가한다고 반영되지 않는다. Validator가 모든 미사용 key를 거부하는
것도 아니므로, 생성된 source·plan·실제 compile command에서 적용 여부를 확인한다.

새 패턴을 구현하면 C 생성뿐 아니라 `job_access_count()`, `access_offsets()`,
checksum 기대값과 locality 분석의 접근 종류·크기 검증도 맞춰야 한다.
기존 공용 분석은 private byte-load stream을 기대하므로 store/FPU/shared-memory
코드를 추가하고 그대로 적격하다고 볼 수 없다. 전용 진단 생성기는 기존
false-sharing처럼 별도로 구성할 수 있다.

Tick 크기 변경은 `period_ticks` 변경과 다르다. Tick 자체를 바꾸려면
`init.c`의 `CONFIGURE_MICROSECONDS_PER_TICK`·`TICK_NS`, Python의 `TICK_NS`와
parser/plan, BSP timer 설정을 함께 맞춘다. Scheduler 변경도 topology.h만
바꿔서는 안 되고 plan의 domain·topology identity·검증을 함께 갱신해야 한다.

`wscript`의 CFLAGS 변경은 workload뿐 아니라 init/probe에도 영향을 준다.
Kernel만 최적화하려면 빌드 target별 옵션을 분리하는 코드 변경이 필요하다.
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
이 job은 64번 load하고 checksum은 64+96=160이다. 현재 generic plan의
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

## 5. false-sharing-uniform-p500-v1 재현

전용 [run.py](../../.cache/configs/periodic-memory-gap/false-sharing/run.py)가
reader/writer와 공유 배열을 생성한다. 생성된 `prepared/configuration.json`만
공용 prepare에 넣으면 원래 공유 메모리 코드를 재현하지 못한다.
전용 scenario와 생성기를 함께 사용해야 한다.

원본 [uniform-p500.json](../../.cache/configs/periodic-memory-gap/false-sharing/uniform-p500.json)은
4쌍=8 tasks, 128 lines/pair, 8 sweeps/job, 주기 500 ms,
총 8 jobs/task 중 warm-up 2개·측정 6개인 **짧은 pilot**이다.
`uniform-p500-full.json`과는 측정 길이가 다르다.

### 두 환경 생성

```sh
export fs_trial=.cache/periodic-memory-gap-v1/my-false-sharing-p500-v1
PYTHONPATH=. python3 -u .cache/configs/periodic-memory-gap/false-sharing/run.py \
  --scenario .cache/configs/periodic-memory-gap/false-sharing/uniform-p500.json \
  --output "$fs_trial" --prepare-only
```

`shared-line/prepared/`와 `separate-line/prepared/`가 생성된다.
각각 G/C/P ELF, 실제 workload.c, 원본 `scenario.json`, 생성기 snapshot
`scenario_runner.py`, manifest를 포함한다.

### 준비한 환경 실행

앞 절의 유효한 DISPLAY 설정을 상속해야 한다.

```sh
nohup env PYTHONPATH=. python3 -u \
  .cache/configs/periodic-memory-gap/false-sharing/run.py \
  --scenario .cache/configs/periodic-memory-gap/false-sharing/uniform-p500.json \
  --output "$fs_trial" --run-only \
  > "$fs_trial/supervisor.log" 2>&1 < /dev/null &
echo $! > "$fs_trial/supervisor.pid"
tail -f "$fs_trial/supervisor.log"
```

한 layout의 G/C/P를 동시에 실행하고 모두 완료하면 다음 layout을 실행한다.
반복 수는 scenario의 `repeats`(생략 시 1), 실행 상한은 `timeout_seconds`다.
정상 완료 시 최상위 `summary.json`과 로그의 `finished status=ok`를 확인한다.
이 간단한 nohup 예제는 `.exit` 파일을 만들지 않는다.

두 stage 옵션을 생략하면 생성부터 측정까지 실행한다. `--run-only`는 중단 지점
자동 재개 기능은 아니다. 기존 측정 output과 충돌하면 새 디렉터리에서 재현한다.
준비/실행 사이에 scenario를 수정하지 않는다. Runner는 ROOT/HERE를 자신의
경로에서 계산하므로 다른 위치로 복사한 script를 그대로 실행하지 않는다.

## 6. 재현의 두 가지 의미

- **동일 ELF 재실행:** 기존 prepared를 보존하고 공용 run의 output만 새 경로로
  지정한다. 원래 manifest 검증이 필요하다. False-sharing의 각 prepared도 가능하다.
- **같은 설정에서 재빌드:** JSON + 생성기/소스 버전 + toolchain을 보존한다.
  생성기나 compiler가 달라지면 같은 JSON에서도 다른 ELF가 나올 수 있다.

공유-memory 등 새 동작은 전용 생성기 변경도 필요하다. 기존 패턴·task 수·주기
조정은 JSON부터 시작한다. 입력·생성기·source/ELF·manifest·raw·분석 코드를
함께 보관해야 `.cache` 삭제 이후에도 재현할 수 있다.

검증: 위 paired-pass 원본에서 임시 경로의 G/C/P ELF 빌드·manifest 검사를
통과했다. 12 tasks, warm-up 240 jobs, 측정 2400 jobs를 확인했다.
False-sharing prepare-only로 두 배치의 ELF 6개·manifest 검사도 통과했다.
문서의 shell 문법·링크와 Python 집계 예제의 기존 raw 재검증을 확인했다.
새 장시간 SIM 측정이나 HW 실행은 시작하지 않았다.

§4 예시 추가 검증: 임시 소스에서 workload O2·stack 32 KiB·reverse-cyclic·
C 2+2 variant의 G/C/P 빌드를 통과했다. Compiler 옵션 분리, 16-task JSON의
job/접근 수, 역순 offset·checksum·분석 반복 수, C의 domain/ID를 확인했다.
FPU 예제는 호스트 checksum=160과 SPARC object의 부동소수점 명령을 확인했다.
이는 build/정적 검증이며 변경 variant의 RTEMS 실행·시간 결과 검증은 아니다.
Phase 확장과 다른 SDK/BSP 사용은 설계 예시로, 구현·실행하지 않았다.
프로젝트의 실제 생성기·계측 코드는 이 문서 예시에 맞춰 변경하지 않았다.

## 7. Raw 로그 위치와 읽는 법

### 7.1. 어느 파일을 열어야 하나

| 파일 | 내용 |
|---|---|
| `supervisor.log` | 어떤 조건·정책·반복을 시작/종료했는지, host 경과시간 등 진행 상황 |
| `supervisor.pid` / `supervisor.exit` | 실행 관리용 PID / 종료 코드. Wrapper에 따라 없을 수 있음 |
| 정책별 `0.log`, `1.log`, … | Simulator 출력과 RTEMS의 원시 `PERIODIC` 레코드 |
| `measurements.jsonl` | 독립 실행마다 한 줄의 집계·검증 결과. 파일 전체가 하나의 JSON은 아님 |
| `protocol.json`, `boot.batch` | 실행 옵션·hash와 boot 설정 |
| `summary.json` | 시나리오별 요약. Raw가 아니며 공용 runner는 자동 생성하지 않음 |
| `set_pressure.json` | ELF 배열 주소의 정적 cache set 점유. 실행 로그나 HW miss 측정값 아님 |
| `prepared/build.log` | 소스 생성 후 compiler/linker 실행 기록 |

예를 들어 L1 set 실험의 위치는 다음과 같다.

```text
.cache/periodic-memory-gap-v1/l1-set-pressure-v1/
  supervisor.log / supervisor.pid / supervisor.exit
  n16-spaced/  n16-compact/  n20-spaced/  n20-compact/
    prepared/
    set_pressure.json
    summary.json
    g/0.log                   G의 첫 독립 실행 raw
    c/0.log                   C의 첫 독립 실행 raw
    p/0.log                   P의 첫 독립 실행 raw
```

현재 N=20 spaced의
[G raw](../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/g/0.log),
[C raw](../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/c/0.log),
[P raw](../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/p/0.log)를
직접 열 수 있다. `0.log`의 0은 task 번호가 아니라 **독립 실행 index**다.
한 raw에 그 실행의 모든 task/job이 들어 있다.

False-sharing처럼 한 번의 runner 호출 안에서 여러 조건을 비교하면 경로가 더 깊다.
현재 전용 runner는 repeats=1에서 `<output>/<layout>/<g|c|p>/0.log`,
repeats>1에서 `<output>/<layout>/<g|c|p>/r0/0.log`, `r1/0.log` 등을 사용한다.
공용 CLI의 `--runs 5`는 같은 정책 디렉터리에 `0.log`부터 `4.log`를 만든다.
실행기마다 다를 수 있으므로 위치를 찾을 때는 다음과 같이 검색한다.

```sh
rg --files --hidden --no-ignore .cache/periodic-memory-gap-v1/l1-set-pressure-v1 \
  -g '[0-9]*.log'
```

### 7.2. 진행 중 관찰과 완료 로그 검색

아래 명령은 workspace에서 실행한다. `case_root`만 원하는 조건으로 바꾸면 된다.

```sh
export case_root=.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced

# 진행 상황: Ctrl-C로 tail만 종료해도 실험은 계속된다.
tail -f .cache/periodic-memory-gap-v1/l1-set-pressure-v1/supervisor.log

# 파일이 존재할 때 raw 추적. 아직 생성 전이면 tail -F로 생성 후까지 추적할 수 있다.
tail -f "$case_root/g/0.log"

# 완료 로그를 페이지 단위로 보기. q로 종료한다.
less "$case_root/g/0.log"

# run header, 완료 marker, target error만 찾기.
rg -n '^PERIODIC .*"kind":"(run|end|error)"' "$case_root/g/0.log"

# task 0의 앞 다섯 job, 그리고 job 20 하나를 찾기.
rg -n -m 5 '"kind":"job","task":0,' "$case_root/g/0.log"
rg -n '"kind":"job","task":0,"job":20,' "$case_root/g/0.log"
```

RTEMS 결과는 task별 job 기록을 버퍼에 모았다가 workers 종료 후 출력한다.
따라서 측정 중 raw가 늘지 않는 것만으로 hang이라고 판단하지 않는다.
출력도 task 순서이므로 **파일의 인접 행이 전체 시스템의 시간 순서는 아니다.**
`tail -f`는 사용자가 필요할 때 관찰하는 명령이며 실험 실행 자체를 기다리는 busy loop가 아니다.

### 7.3. PERIODIC 레코드 읽기

각 줄은 `PERIODIC ` 접두어 뒤의 JSON object다. Simulator banner·ELF loading·
shutdown 문구는 그 밖에 섞여 있다. Raw 원본의 줄을 수정하거나 삭제하지 않는다.

| `kind` | 읽을 내용 |
|---|---|
| `run` | plan hash, 계약 ID, CPU 수, mode/trace/empty, t0, tick 길이 |
| `task` | task index, RTEMS thread ID, scheduler domain mask, arm 시각 |
| `job` | task/job index, release/start/completion, CPU accounting, core, checksum, 상태 |
| `switch` | `--trace`일 때의 core별 dispatch 기록 |
| `end` | `complete=1`이면 target의 결과 출력 완료 marker |
| `error` | target이 보고한 오류. 정상 결과로 취급하지 않음 |

`task`와 `job`은 모두 0부터 시작한다. Task 이름은 해당 정책의
`prepared/g/plan.json` 등에서 `tasks[task]['task_id']`로 찾는다.
위 사례의 task 0은 `t00`이고, jobs 0–19는 warm-up, 20–199가 측정 구간이다.
다른 실험은 task별 `warmup_jobs`를 읽어야 하며 20을 일괄 적용하면 안 된다.

시간 필드의 기본 단위는 ns다. `ns/1000=µs`, `ns/1_000_000=ms`다.

| 필드/계산 | 의미 |
|---|---|
| `release_ns` | 계획된 nominal release |
| `start_ns`, `completion_ns` | workload 계측 bracket의 시작·종료 시각 |
| `cpu_after_ns - cpu_before_ns` | 해당 job의 TET 기여분인 CPU-accounting 차이 |
| `completion_ns - release_ns` | job response time |
| `completion_ns - start_ns` | bracket의 wall elapsed. 선점·대기 영향이 있어 CPU 시간과 다름 |
| `start_core`, `end_core` | bracket 양 끝의 실행 core. 두 값이 같아도 중간 migration이 없었다는 보장은 아님 |
| `checksum` | 실행 내용이 기대값과 맞는지 검증하는 값 |
| `period_status`, `state_*`, `postponed_*` | period 호출·활성 상태·밀린 job의 검사에 사용 |
| `wall_before_ns`, `wall_after_ns` | RTEMS status API의 period 경과시간 snapshot. 별도의 aggregate TAT 값이 아님 |

실제 `n20-spaced/g/0.log`의 task=0, job=20은 다음 값을 갖는다.

```text
release_ns    = 125000000
start_ns      = 125141775
completion_ns = 125457843
cpu_before_ns = 111080
cpu_after_ns  = 419120
checksum      = 3072
```

따라서 job CPU 시간은 **308.040 µs**, response는 **457.843 µs**,
bracket wall elapsed는 **316.068 µs**다. `cpu_after_ns` 자체를 job CPU 시간으로
쓰면 안 된다. CPU 계측은 RTEMS status 호출 경계이고 wall bracket과 정확히 같지 않다.

현재 aggregate TET는 **측정 jobs의 CPU 차이 합**이다. TAT는 같은 nominal
release의 cohort마다 **가장 이른 start에서 마지막 completion까지**의 span을
합한다. Release부터 마지막 completion까지의 합은 별도
`cohort_response_sum_ns`, 개별 job response 합은 `response_sum_ns`다.
`makespan_ns`는 현재 구현에서 `마지막 측정 completion - t0_ns`이므로
초기 warm-up/release horizon의 영향도 포함한다.

### 7.4. 특정 task의 측정 jobs를 Python으로 보기

완료된 batch에 적용한다. 단순 JSON 열람보다 `load_batch()`로 raw·manifest를
재검증한 뒤 읽는 것이 좋다. 진행 중에는 아직 measurements가 완성되지 않을 수 있다.

```sh
python3 - <<'PY'
import json
import os
from pathlib import Path
from chaser.periodic.dataset import load_batch

root = Path(os.environ['case_root'])
architecture, run_index, task_index = 'g', 0, 0
plan = json.loads((root / 'prepared' / architecture / 'plan.json').read_text())
row = load_batch(root / 'prepared', root / architecture)[run_index]
print('status:', row['execution_status'], 'errors:', row.get('errors'), row.get('error'))
if row['execution_status'] != 'ok':
    raise SystemExit('Invalid run; retain raw and inspect errors')
task = plan['tasks'][task_index]
jobs = [j for j in row['jobs']
        if j['task'] == task_index and j['job'] >= task['warmup_jobs']]
print('task:', task['task_id'], 'measured_jobs:', len(jobs))
for j in jobs[:5]:
    print('job', j['job'], {
        'cpu_us': (j['cpu_after_ns'] - j['cpu_before_ns']) / 1000,
        'response_us': (j['completion_ns'] - j['release_ns']) / 1000,
        'elapsed_us': (j['completion_ns'] - j['start_ns']) / 1000,
        'start_core': j['start_core'], 'end_core': j['end_core'],
    })
cpu = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in jobs]
print('task CPU mean/max (us):', sum(cpu) / len(cpu) / 1000, max(cpu) / 1000)
print('run TET/TAT (ms):', row['tet_ns'] / 1e6, row['tat_ns'] / 1e6)
PY
```

이는 해당 batch의 index를 선택한다. 전용 runner의 `r0/0.log` 구조라면
`load_batch()`의 두 번째 인자도 해당 `r0` 디렉터리로 바꾸고 run_index=0을 사용한다.

### 7.5. 성공·실패 구분

`supervisor.exit=0`이나 `end complete=1`만으로 모든 결과의 적격성을 판단하지 않는다.
공용 runner의 process `returncode=0`, `execution_status=ok`, `errors=[]`와
raw 재검증을 함께 확인한다. Checksum·job 누락·domain·deadline 등의 오류가 있으면
부분 시간 합계가 있어도 정상 표본이 아니다.

| 오류 예 | 우선 확인할 것 |
|---|---|
| `completion_marker`, `job_completeness` | 출력 완료 여부, timeout·중단, 예상 job 수 |
| `checksum` | job 코드·입력 초기화·기대 checksum |
| `domain`, `trace_domain` | scheduler 배치와 plan domain |
| `deadline_miss`, `postponed_job` | 주기 대비 작업량, 부하·선점 |
| `process_exit` | simulator 종료 코드와 timeout 여부; timeout이면 통상 124 |
| `provenance`, hash 관련 예외 | 다른 ELF/plan/raw 혼합 또는 snapshot 수정 여부 |

현재 N=20 spaced raw에는 `end complete=1`과 `RTEMS shutdown` 이후
`CORE#0 halts because of Error Mode`가 출력된다. 이 사례는 process 종료 코드가 0이고
G/C/P 모두 재검증이 정상이다. 따라서 이 문자열만으로 실패라고 단정하지 않는다.
반대로 실행 중 예외나 완료 marker 누락까지 같은 정상 종료로 일반화하지 않는다.

위 세 raw의 확인 결과는 정책별 총 4000 jobs 중 warm-up 400개, 측정 3600개,
cohort 180개다. `supervisor.exit=0`도 확인했다. 이 절의 조회·집계 예제는 기존
로그만 읽으며 새 실험을 시작하거나 raw를 수정하지 않는다.
