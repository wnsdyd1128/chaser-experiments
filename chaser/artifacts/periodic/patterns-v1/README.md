# Hot/cold·phase 패턴 확장 검증

2026-09-21. 새 패턴을 생성한 동일 source/object로 G/C/P SPARC ELF를 빌드하고,
각 최종 ELF의 YARDA 접근열과 공개 RTEMS API 측정을 검증했다. Backend는
laysim-GR740이다. **개발용 taskset 하나의 구현 검증이며 최종 RF 학습 데이터가 아니다.**

## 구성과 결과

[예제 구성](../../../configs/periodic-patterns-example.json)은 독립 데이터 배열을 사용하는
hot/cold task와 phase task로 구성된다. 각 task는 H=64, C=1024 lines, stride=32 B,
hot_repeats=4, cold_repeats=1, sweeps=8을 사용한다. 활성 working set은 34 KiB,
job당 접근 수는 10240이다. Period=20 ms, horizon=40 ms로 task당 두 job을 측정했다.
Policy는 명시적 core 0/1 배치이며 보정된 θ가 아니다.

Hot/cold는 H 4회 → C 1회 블록을 8번 반복한다. Phase는 H 32회를 모두 수행한 뒤
C 8회를 수행한다. 동일 접근 수·working set에서 순서가 다르며, cache는 job 사이에도
유지된다. 분석 feature는 한 cold job의 task-local 결과다.

| 항목 | 결과 |
|---|---:|
| G/C/P timing | 3 × 10 = 30/30 성공 |
| 독립 U | 2 tasks × 10 = 20/20 성공 |
| 별도 G/C/P 진단 | 3/3 성공 |
| 독립 empty-job | 10/10 성공 |
| 전체 실행 / job | 63회 / 192 jobs |
| Timing·U job | 160개 |
| 전체 verifier | 329 passed in 48.32s |

독립 U는 hot=0.0724755, phase=0.0712914이며 모든 독립 실행 job을 포함했다.
Empty 20 jobs의 CPU 비용은 5496–9200 ns, 평균 7348 ns다. 측정값에서 차감하지 않았다.
모든 배치는 `load_batch()`로 raw log와 hash를 다시 확인했다.

| 한 cold job의 분석 지표 | Hot/cold | Phase |
|---|---:|---:|
| L1 hit ratio | 0.15 | 0.19375 |
| LLC first-hit ratio | 0.74375 | 0.7 |
| Memory ratio | 0.10625 | 0.10625 |
| CLS(0.5) | 0.2157388336 | 0.2556218434 |

이는 접근 순서 차이가 분석 결과에 반영된다는 확인이다. Runtime cache counter,
architecture 우열, 학습 데이터 충분성 또는 일반화 성능을 입증하지 않는다.
최종 label/RF는 생성하지 않았고 `eligible_for_training=false`로 보존했다.
설계안의 11개 probe 전체와 task 수·capacity 경계 수집은 후속이다.

## 검증 범위

- Logic 테스트는 패턴·region 범위 거부, checksum, literal 접근 순서, 순서/주소/크기/
  종류/object 변조 거부와 16 MiB 한도를 확인한다. 구현 전 14개 실패를 확인했다.
- 실제 waf/APE 통합 테스트는 작은 수작업 접근열을 G/C/P의 최종 ELF와 대조한다.
  `cold_repeats=1/2` 모두 검증하고, 중첩 loop 전체의 iteration budget을 적용한다.
- 기존 공개 API v2 `pilot-02`의 G/C/P plan(dict와 hash), 생성 `workload.c`가 새 생성기와
  동일함을 확인했다. 기존 archive는 변경하지 않았다.
- 일반 측정에는 내부 probe가 없고, 진단에는 별도 trace를 사용했다. Runtime checksum은
  load 수를 확인하며 실제 접근 순서 증거를 대신하지 않는다.
- `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify`가 exit 0으로 끝났다.
  Finalize는 실행하지 않았다.

## 보존 파일과 재검사

- [summary.json](summary.json): 구성, batch별 집계·protocol hash, 독립 U, locality, 계측 비용.
- `snapshots.tar.gz`: configuration, source, object, G/C/P ELF, APE, 분석 event, manifest 전체.
- `measurements.tar.gz`: 63회 raw log, measurement records, boot/protocol, 실행 구현 snapshot.
- `implementation.tar.gz`: 생성기·분석기·테스트·예제 구성과 관련 구현.
- [verification.txt](verification.txt): 전체 verifier 출력.
- [manifest.json](manifest.json): 보존 파일 SHA-256.

작업 원본은 `.cache/periodic-patterns-v1`, `.cache/periodic-patterns-v1-runs`다.
Archive 내 절대 경로는 당시 provenance이며 재측정 시 새 output 경로를 사용한다.
Archive를 별도 디렉터리에 풀면 `snapshot/`, `runs/`에서 다음을 실행할 수 있다.

```python
from pathlib import Path
import json
from chaser.periodic_dataset import characterize, load_batch

root = Path('/tmp/chaser-patterns-review')
snapshot = root / 'snapshot'
batches = {p.name: load_batch(snapshot, p) for p in (root / 'runs').iterdir()}
assert sum(len(rows) for rows in batches.values()) == 63
assert all(r['execution_status'] == 'ok' for rows in batches.values() for r in rows)
plan = json.loads((snapshot / 'p/plan.json').read_text())
utilization = characterize(plan, [batches['u0'], batches['u1']])
```
