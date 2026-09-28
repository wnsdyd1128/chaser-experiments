# Raw 로그 조회·해석

[전체 실험 안내](../EXPERIMENT-GUIDE.md) · 명령은 workspace root 기준이다.

<a id="raw-logs"></a>

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

이전 실험의 N=20 spaced raw 경로는
[G raw](../../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/g/0.log),
[C raw](../../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/c/0.log),
[P raw](../../../.cache/periodic-memory-gap-v1/l1-set-pressure-v1/n20-spaced/p/0.log)를
이다. 이 worktree에는 없으므로 원본을 확보한 경우에 열 수 있다.
`0.log`의 0은 task 번호가 아니라 **독립 실행 index**다.
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
