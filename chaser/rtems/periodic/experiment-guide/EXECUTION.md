# 빌드·SIM 실행·재현

[전체 실험 안내](../EXPERIMENT-GUIDE.md) · 명령은 workspace root 기준이다.

<a id="build-and-run"></a>

## 3. 공용 생성기로 빌드·실행

원본 PolyBench MEDIUM 30종도 같은 명령을 사용한다. 설정은
`configs/periodic-polybench/<benchmark>-medium.json`에 있고, 전체 검증은
[PolyBench 실행 안내](../polybench/README.md)를 따른다. MEDIUM은 smoke보다
오래 걸리므로 `run --timeout`과 설정의 `period_ticks`를 각각 조정한다.

### 소스·ELF 생성

```sh
# 현재 workspace root에서 버전 관리되는 schema v2 예제를 실행한다.
export trial_root=.cache/periodic-memory-gap-v1/my-gemm-v1
python3 -m tools.rtems_periodic prepare \
  configs/periodic-multi-array/gemm-u32-smoke.json \
  --output "$trial_root/prepared"
```

Output은 새 경로여야 한다. 생성되는 구조는 다음과 같다.

```text
my-gemm-v1/prepared/
  configuration.json          입력 snapshot
  source/                     workload.c/h, init.c, probe.c/h
  g/  c/  p/                  각각 plan.json, config.h, topology.h
  build/                      g.exe, c.exe, p.exe, objects
  layout.ld, layout.json      주소 배치·검사 결과
  wscript, waf, build.log     빌드 절차·실제 명령
  cache.yaml                  분석 모델 설정; HW cache enable 설정이 아님
  kernel-inputs/             C 템플릿·Python 계약 snapshot
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
Raw 경로, 레코드 필드, 특정 task/job 조회와 오류 판독은
[raw 로그 가이드](RAW-LOGS.md#raw-logs)를 참고한다.
공용 run은 `summary.json`을 자동 생성하지 않는다. 기존 summary는 시나리오별
실행기가 만든 것이다. 선택적인 locality 분석은 다음과 같으며 timing의 필수 단계는 아니다.
추가로 clang-14와 YARDA 빌드가 필요하다.

```sh
python3 -m tools.rtems_periodic analyze "$trial_root/prepared"
```

<a id="false-sharing"></a>

## 5. false-sharing-uniform-p500-v1 재현

전용 [run.py](../../../.cache/configs/periodic-memory-gap/false-sharing/run.py)가
reader/writer와 공유 배열을 생성한다. 생성된 `prepared/configuration.json`만
공용 prepare에 넣으면 원래 공유 메모리 코드를 재현하지 못한다.
전용 scenario와 생성기를 함께 사용해야 한다.

원본 [uniform-p500.json](../../../.cache/configs/periodic-memory-gap/false-sharing/uniform-p500.json)은
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

<a id="reproducibility"></a>

## 6. 재현의 두 가지 의미

- **동일 ELF 재실행:** 기존 prepared를 보존하고 공용 run의 output만 새 경로로
  지정한다. 원래 manifest 검증이 필요하다. False-sharing의 각 prepared도 가능하다.
- **같은 설정에서 재빌드:** JSON + 생성기/소스 버전 + toolchain을 보존한다.
  생성기나 compiler가 달라지면 같은 JSON에서도 다른 ELF가 나올 수 있다.

지원되는 typed 배열·읽기 공유·정수 GEMM·task 수·주기 조정은 JSON부터 시작한다.
float32·공유 쓰기 등 지원하지 않는 동작은 커널·planner·분석 계약 확장이 필요하다. 입력·생성기·source/ELF·manifest·raw·분석 코드를
함께 보관해야 `.cache` 삭제 이후에도 재현할 수 있다.

입력·실행 절차는 [다중 배열 가이드](INPUTS.md#multi-array),
완료된 검증과 후속 범위는 [검증 기록](INPUTS.md#multi-array-verification)을 따른다.
