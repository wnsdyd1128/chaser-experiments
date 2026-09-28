# RTEMS 실험의 HW 검증 가이드

확인: 2026-09-27. [실험 생성·수정 가이드](EXPERIMENT-GUIDE.md) /
[Periodic harness](README.md).

이 문서는 **GR740 보드 + RTEMS + GRMON3**를 기준으로 실험에 공통으로 쓰는
HW 검증 절차를 설명한다. 특정 taskset·주기·캐시 배치를 전제로 하지 않는다.
다른 보드에서는 BSP·메모리 map·debug link·타이머·counter를 그 보드에 맞춘다.
현재 사용 보드 모델/revision·연결 방식·GRMON 버전은 확정되지 않았으며,
**이 절차로 실제 보드를 실행한 결과는 아직 없다.**

현재 연구의 진행 순서는 **SIM 실험 → 실험 구성·결과 확정 → HW 검증**이다
(2026-09-27 사용자 지시). 이 가이드는 마지막 단계에서 사용하며, 보드 접속이나
HW smoke를 현재 SIM 실험의 선행 조건으로 요구하지 않는다.

공통 흐름은 다음과 같다.

```text
환경 기록 → 대상 ELF 확인 → 부팅·기능 smoke → 계측 검증
→ 조건별 독립 반복 → raw 검증·비교 → 필요하면 HW counter로 원인 분석
```

§1–7은 일반 RTEMS 실험 절차다. **Chaser periodic ELF를 사용하는 경우 §8의
boot flags 설정과 로그 집계 예제를 함께 적용한다.** 일반 프로그램에는 그 symbol이나
`PERIODIC` 로그 형식이 없어도 된다.

## 1. 비교 조건과 실행 환경 고정

먼저 비교할 효과를 정한다. 예를 들어 scheduler, task mapping, workload,
compiler 최적화 중 한 축을 바꾸고 나머지를 고정한다. 목표는 예상한 큰 격차가
나오는지뿐 아니라 올바르게 실행·측정되고 효과가 반복되는지 확인하는 것이다.

| 항목 | 실행마다 기록·대조할 내용 |
|---|---|
| HW | 보드·칩 revision, 사용 코어 수, CPU/bus/SDRAM 주파수 |
| 메모리 | RAM map·크기, SDRAM timing, EDAC·scrubber 설정 |
| 캐시 | L1/L2 활성 상태, cacheability/MMU, snooping, locking/partition |
| SW | RTEMS/BSP/compiler 버전, SMP 설정, 실제 최적화·CPU/FPU 옵션 |
| 입력 | taskset·배치·주기·작업량, 기대 결과/checksum, 측정 길이 |
| 시간 | BSP timer 설정·해상도, tick 길이, CPU accounting 지원 |
| 수집 | GRMON 버전·접속 방법, UART 장치·baud rate, reset/초기화 절차 |
| 외부 부하 | DMA·통신·다른 프로그램의 동작 여부 |

Simulator와 비교할 때는 가능하면 동일 ELF를 사용한다. 보드에 맞춰 BSP나 코드를
바꿔야 하면 변경점과 hash를 보존한다. 주파수가 다른 실행의 절대 시간만으로
캐시나 scheduler 효과를 판단하지 않는다.

## 2. 보드용 ELF와 메모리 배치 확인

보드에 맞는 BSP로 빌드하고 boot CPU·SMP·메모리 map을 확인한다.
소스·입력·빌드 명령·ELF hash를 보존한다. 로컬 공용 생성기 사용법은
[실험 가이드 §3](experiment-guide/EXECUTION.md#build-and-run)을 따른다.

다음 경로는 **사용자가 실제 ELF 경로로 바꿀 자리**다. 일반 ELF 예제의 output은
Chaser 예제와 별도이며, 실행마다 새 디렉터리를 만든다.

```sh
cd /workspace/experiments/chaser
export HW_ELF=/absolute/path/to/application.exe
export HW_RUN=.cache/hw-validation/my-application/run-001
python3 -c 'import os; from pathlib import Path; Path(os.environ["HW_RUN"]).mkdir(parents=True, exist_ok=False)'

/opt/rtems/6/bin/sparc-rtems6-readelf -h -l "$HW_ELF"
/opt/rtems/6/bin/sparc-rtems6-nm -S --defined-only "$HW_ELF"
sha256sum "$HW_ELF" > "$HW_RUN/elf.sha256"
```

명령의 SDK 경로도 설치 환경에 맞춰 변경한다. LOAD segment뿐 아니라
NOLOAD/BSS·RTEMS workspace·stack·heap을 수용하는 RAM이 필요하다.

현재 로컬 GR740 BSP의 `linkcmds.gr740`은 RAM 시작을 0x00000000으로 둔다.
다른 LEON 환경의 주소를 그대로 적용하지 않는다. 배열의 고정 주소도 실험 ELF에서
확인한다. 특정 실험에서 관찰한 segment 끝 주소는 다른 ELF에 일반화하지 않는다.

`cache.yaml` 같은 분석 입력은 HW cache enable 설정이 아니다. 실제 활성 상태를
확인한다. GR740의 L1D는 코어별 16 KiB/4-way/32 B line이고 공유 L2는 2 MiB다.
L1D는 write-through/no-write-allocate 정책을 사용한다.
([GR740 manual §6.3, §9](https://download.gaisler.com/products/gr740/doc/GR740-UM-DS-2-10.pdf))

## 3. 보드 연결·부팅·기능 smoke

처음에는 짧고 기대 결과를 아는 입력 하나로 확인한다. 현재 설정의 특정 policy나
최소 taskset을 선택할 수 있지만 모든 실험에서 P부터 시작해야 하는 것은 아니다.
보드별 reset/초기화 절차는 해당 보드 매뉴얼을 따른다.

Ethernet debug link가 설정된 보드의 GRMON3 예시:

```sh
grmon -eth BOARD_IP -u -nologtag -nologtime -log "$HW_RUN/grmon.log"
```

`BOARD_IP`를 실제 주소로 바꾼다. FTDI JTAG이면 지원 케이블을 확인하고 `-eth ...`
대신 `-ftdi`를 사용한다. `-u`는 UART forwarding이다. 로그는 기존 파일에 append하므로
실행마다 새 경로를 쓴다. 옵션은 설치 버전에 맞춰 확인한다.
([GRMON3 manual §3, §5](https://www.download.gaisler.com/products/GRMON3/doc/grmon3.pdf))

GRMON prompt의 공통 흐름은 다음과 같다. 여기서는 shell의 `$HW_ELF`가 자동으로
치환되지 않으므로 실제 경로를 쓴다. **Chaser ELF는 §8에서 만든 run.tcl을 사용한다.**

```tcl
info sys
info reg
load /absolute/path/to/application.exe
# 프로그램이 요구하는 실행 전 설정을 적용한 다음 시작한다.
run
```

일반 SMP 애플리케이션은 하나의 ELF를 boot CPU에서 시작하고 RTEMS가 secondary
cores를 시작한다. 네 코어에 같은 ELF를 각각 독립 실행하는 방식과 구분한다.

먼저 정상 부팅·사용 코어 수·task 생성·배치·결과/checksum·완료 marker를 확인한다.
실험의 정의에 따라 deadline miss와 예외도 기록한다. Debugger 복귀 여부만으로
완료를 판단하지 말고 프로그램이 출력하는 명시적 종료 기록을 확인한다.

## 4. 시간 계측과 원시 로그 수집

성능 시간은 **target 내부**에서 측정한다. Host의 load/run 명령 경과시간에는
다운로드·통신·출력이 섞인다. Timer가 실제 clock과 맞는지 확인하고 작은 대조
프로그램으로 해상도와 빈 측정 구간의 비용을 점검한다.

| 지표 | 먼저 정할 경계 |
|---|---|
| Job CPU 시간 | 해당 job이 소비한 CPU accounting 구간 |
| Response time | nominal release부터 완료까지 |
| Wall elapsed | 선택한 실행 bracket 시작부터 완료까지 |
| Makespan | 정의한 전체 시작점부터 마지막 완료까지 |
| TET/TAT | 위 개별 값을 어떤 jobs/cohorts에 대해 집계하는지 명시 |

Wall time과 CPU time은 선점·대기 때문에 다를 수 있다. TAT는 이름만 같다고
다른 실험과 같은 의미가 아니다. Chaser 정의와 raw 필드는
[로그 가이드 §7](experiment-guide/RAW-LOGS.md#raw-logs)을 따른다.

측정 중 printf·breakpoint·single-step·반복 register polling은 측정에 영향을 줄 수 있다.
가능하면 결과를 메모리에 모아 측정 후 출력한다. 첫 smoke는 UART forwarding으로
확인할 수 있지만 최종 성능 측정은 별도 물리 UART 수집 등 debug link의 영향을
줄인 방법을 사용하고 수집 방식을 고정한다. 물리 UART의 장치·baud는 BSP와 보드
설정에 맞춘다. 단순히 특정 serial 장치나 baud를 모든 보드에 적용하지 않는다.

```sh
# 수집 프로그램이 해당 파일을 만들고 쓰는 동안 관찰한다.
tail -f "$HW_RUN/grmon.log"
# 별도 UART로 수집하는 경우:
tail -f "$HW_RUN/uart.log"
```

측정 후 일괄 출력하는 프로그램은 실행 중 raw가 증가하지 않을 수 있다.
출력 종료까지 기다린다. 보드 한 대에서는 한 ELF씩 실행하며, host 수집을
백그라운드로 실행해도 이 원칙은 같다. 전체 자동 queue는 첫 smoke 통과 후 구성한다.

## 5. 반복·성공 판정·결과 보존

실행 단위를 `reset/초기화 → load → 실행 전 설정 → warm-up → 측정 → 출력`으로
고정한다. Warm-up은 정상 상태가 관심 대상일 때 사용한다. 시작 비용이 관심이면
초기 jobs를 별도로 분석한다. 매 job 전 cache flush는 새로운 실험 조건이므로
목적 없이 추가하지 않는다.

처음에는 조건별 5회 정도 독립 기동해 변동을 살핀 뒤 추가 횟수를 정할 수 있다.
이는 통계적으로 충분한 표본 수를 보장하는 기준은 아니다. 조건 순서를 교대하고
보드 설정·reset·수집 방법을 유지한다. 한 실행의 수백 jobs를 독립 부팅 수백 회로
취급하지 않는다.

일반적인 성공 판정은 기대 결과·완료·레코드 수·설정 일치·측정 일관성을 포함한다.
Deadline은 실험의 성공 기준에 따라 판정하며, Chaser periodic의 현재 계약은
miss를 실패로 처리한다. 실패·timeout·부분 로그도 보존하고 정상 결과와 구분한다.

각 run 디렉터리에 다음을 남긴다.

```text
run-001/
  metadata.json        보드·clock/cache·toolchain·reset·조건·시각·수집 방식
  input-sha256.json    ELF·입력·plan·boot script 등의 hash
  run.tcl             사용한 경우 실제 GRMON 실행 명령
  grmon.log           debugger/실행 기록
  uart.log            별도 수집한 경우 원본 UART
  measurement.json    parser 버전·raw hash·검증·측정 결과
```

위 metadata와 UART 파일은 운영자가 기록·수집해야 하며 이 문서가 자동 생성하는
파일은 아니다. §8의 예제는 run.tcl·hash 목록·집계 결과만 생성한다.
Hash 대상 원본과 분석 코드도 함께 보존한다. `.cache`를 지우면 재현 근거가 사라질 수 있다.

## 6. Simulator/HW 비교

입력·실행 코드·계측 경계를 대조한 후 다음을 비교한다.

- Run별 TET/TAT 또는 정의한 지표의 median·범위와 조건 간 상대 변화율.
- Task/역할별 CPU·response 분포, 관측 최대와 deadline miss 수.
- Warm-up 포함/제외에 따른 차이와 측정 jobs/cohorts 수.
- 정책 순위·배치 효과 방향·실행 간 변동의 재현 여부.

관측 최대는 보장된 WCET/WCRT가 아니다. Simulator와 절대 시간이 달라도 조건별
상대 효과가 비슷한지 확인한다. HW에서 효과가 작아지거나 반대로 나오면 그 차이도
결과다. 실패한 jobs를 임의로 삭제해서 같은 표본인 것처럼 비교하지 않는다.
주기/작업량을 조정해야 하면 새 입력으로 SIM/HW 양쪽 조건을 다시 맞춘다.

## 7. 필요할 때 HW counter로 원인 분석

시간 측정이 검증된 뒤 counter를 추가한다. GR740에서는 L4STAT의 지원 event와
설정을 실제 장치에서 확인한다. L1D miss·cache 대기·L2/bus event·CPU active cycle
등을 후보로 두되 지원 여부·정의·CPU filter·폭/overflow·reset 조건을 확인한다.
([GR740 manual §26](https://download.gaisler.com/products/gr740/doc/GR740-UM-DS-2-10.pdf))

Warm/cold-cache처럼 결과 방향을 예상할 수 있는 작은 대조군으로 counter를 먼저
검증한다. Per-core counter에 OS/다른 task가 포함되면 task 고유 miss로 부르지 않는다.
Migration이 있으면 코어별 집계와 task별 집계를 구분한다.

측정 경계에서 target 코드가 counter를 읽는 별도 variant를 만들고 계측 유무를
비교한다. Counter를 추가한 ELF·설정·경계도 보존한다. 기본 시간 재현과 counter를
추가한 원인 분석은 별도 결과로 관리한다. 현재 공용 periodic ELF에는 HW counter
수집이 구현돼 있지 않다.

## 8. Chaser periodic ELF에 적용하기

### 8.1. 공용 예제 준비 또는 기존 prepared 선택

이 절은 프로젝트 전용이다. G/C/P와 PERIODIC 계측 계약을 사용하는 ELF에만 적용한다.
원하는 JSON은 [실험 가이드](EXPERIMENT-GUIDE.md)로 준비한다. 과거 특정 실험 없이
시작하려면 저장소의 작은 예제를 사용할 수 있다.

```sh
python3 -m tools.rtems_periodic prepare configs/periodic-example.json \
  --output .cache/periodic-hw-example/prepared

export CHASER_HW_PREPARED=.cache/periodic-hw-example/prepared
export CHASER_HW_ARCH=p
export CHASER_HW_OUTPUT=.cache/hw-validation/periodic-example/p/run-001
```

작은 예제는 기능 smoke 용도이며 충분한 성능 표본이나 균형 배치를 뜻하지 않는다.
이미 prepared가 있으면 prepare를 생략하고 환경 변수만 해당 경로로 바꾼다.
Architecture를 바꿀 때 output도 새 경로로 바꾼다.

`tools.rtems_periodic run`은 **laysim 전용**이며 보드 실행 옵션이 없다.
`load_batch()`도 그 runner의 protocol/boot/raw 묶음을 기대하므로 HW 로그를
기존 SIM batch에 넣지 않는다. 아래는 수동 GRMON 실행과 `parse_log()` 집계를
연결하는 예제로, 완성된 HW collector는 아니다.

### 8.2. 실행 전 flags와 GRMON script 생성

Periodic ELF에는 `chaser_mode`, `chaser_trace`, `chaser_empty`의 초기 표식값이
들어 있다. 일반 timing 실행은 **load 후 run 전에 모두 0으로 설정**해야 한다.
이 요구는 일반 RTEMS 규칙이 아니라 이 프로젝트의 boot 계약이다.

```sh
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
from chaser.periodic.build import read_symbols
from tools.rtems_smoke import check_inputs

prepared = Path(os.environ['CHASER_HW_PREPARED']).resolve()
arch = os.environ['CHASER_HW_ARCH']
out = Path(os.environ['CHASER_HW_OUTPUT']).resolve()
assert arch in ('g', 'c', 'p')
check_inputs(prepared, json.loads((prepared / 'manifest.json').read_text()))
elf = prepared / f'build/{arch}.exe'
symbols = read_symbols(elf)
flags = ('chaser_mode', 'chaser_trace', 'chaser_empty')
assert all(name in symbols and symbols[name][1] == 4 for name in flags)
# Tcl braced path로 안전하게 표현할 수 있는 경로를 사용한다.
assert not any(char in str(elf) for char in '{}\\\n\r')
out.mkdir(parents=True, exist_ok=False)
commands = ['info sys', 'info reg', f'load {{{elf}}}']
commands += [f'wmem 0x{symbols[name][0]:x} 0x0' for name in flags]
commands += ['run']
(out / 'run.tcl').write_text('\n'.join(commands) + '\n')
paths = [elf, prepared / f'{arch}/plan.json', prepared / 'configuration.json',
         prepared / 'manifest.json', out / 'run.tcl', Path('chaser/periodic/measurement.py').resolve()]
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(out / 'input-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
print('GRMON source path:', out / 'run.tcl')
PY
```

이 예제로 접속할 때는 다음을 사용한다. 일반 예제의 `HW_RUN`과 별도 출력 경로다.

```sh
grmon -eth BOARD_IP -u -nologtag -nologtime \
  -log "$CHASER_HW_OUTPUT/grmon.log"
```

GRMON prompt에서 위 Python이 표시한 절대 경로를 지정한다.

```tcl
source /absolute/path/to/run.tcl
```

하나의 SMP ELF를 실행하고 전체 `PERIODIC` 레코드와 complete end까지 수집한다.
프로그램이 debugger로 복귀하지 않더라도 출력 완료를 확인한 뒤 정지한다.
별도 UART에서 수집한 raw는 이 output의 `uart.log`로 보존한다.

### 8.3. Raw 검증·집계

Raw의 레코드가 `PERIODIC `으로 시작하는지 확인한다. GRMON prefix가 남으면
원본을 보존하고 변환 규칙을 기록한 별도 파일을 사용한다. 누락·중복을 숨기지 않는다.

```sh
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
from chaser.periodic.measurement import parse_log
from tools.rtems_smoke import check_inputs

prepared = Path(os.environ['CHASER_HW_PREPARED']).resolve()
arch = os.environ['CHASER_HW_ARCH']
out = Path(os.environ['CHASER_HW_OUTPUT']).resolve()
raw = out / 'uart.log'  # forwarding 사용 시 행 형식을 확인하고 grmon.log로 변경
check_inputs(prepared, json.loads((prepared / 'manifest.json').read_text()))
for path, expected in json.loads((out / 'input-sha256.json').read_text()).items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
plan = json.loads((prepared / f'{arch}/plan.json').read_text())
parsed = parse_log(raw.read_text(errors='strict'), plan, mode=0, trace=False, empty=False)
record = dict(execution_backend='gr740-hardware',
              source_plan_hash=plan['plan_hash'], source_plan_backend=plan['execution_backend'],
              raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(), measurement=parsed)
(out / 'measurement.json').write_text(json.dumps(record, indent=2) + '\n')
print(parsed['execution_status'], parsed['errors'])
if parsed['execution_status'] != 'ok':
    raise SystemExit('Invalid run: retain raw and diagnose before comparison')
print({k.replace('_ns', '_ms'): parsed[k] / 1e6
       for k in ('tet_ns', 'tat_ns', 'makespan_ns')})
PY
```

동일 ELF를 재사용하므로 원본 plan의 `execution_backend='laysim-gr740'`와 hash를
유지한다. 실제 HW backend는 바깥 record의 `gr740-hardware`로 기록한다.
원본 plan의 backend만 고치면 ELF에 내장된 hash와 일치하지 않는다.
정식 collector 통합에는 workload identity와 실행 provenance 계약 정리가 필요하다.

Parser는 CPU 수 4·flags·plan hash·scheduler domain·전체 job·checksum·deadline·
period/accounting 등을 검사한다. 실제 clock이나 cache enable은 검사하지 않는다.
기대 job 수는 각 plan에서 읽고 특정 실험의 숫자로 고정하지 않는다. 현재 TET/TAT와
warm-up 정의는 [로그 가이드](experiment-guide/RAW-LOGS.md#raw-logs)를 따른다.

독립 U 진단은 P ELF의 `mode=i+1`, empty job은 `empty=1`, dispatch 진단은
`trace=1`인 별도 실행으로 한다. Script의 wmem과 parser 인자를 모두 같은 값으로
바꾸고 일반 timing 결과와 혼합하지 않는다.

## 9. 검증 범위와 실제 보드에서 남은 작업

저장소의 `configs/periodic-example.json`으로 임시 경로에서 G/C/P ELF를 빌드하고
§8의 boot-script 생성 예제를 검증했다. 로그 집계 예제는 기존 SIM raw를 사용해
hash 검사·parser 호출을 검증했다. 문서의 shell 문법과 이동 후 링크도 확인했다.
이 검증은 host의 빌드·script 생성·로그 처리에 한정되며 HW 결과가 아니다.
GRMON 명령은 공식 매뉴얼에 근거하지만 보드 접속·기동·시간 정확도·counter 동작은
아직 검증하지 않았다. 첫 보드 작업은 접속 설정을 확정하고 짧은 smoke를 통과하는 것이다.
과거 개별 시나리오의 결과는 [실험 기록](../../artifacts/periodic/memory-gap-v1/README.md)을 참고한다.
