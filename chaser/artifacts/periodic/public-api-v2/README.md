# 공개 API 측정 경로 v2 검증

2026-09-20. 일반 timing·독립 U에서 내부 period/EDF probe를 제거하고, `--trace`에서만
내부 probe와 dispatch extension을 사용하는 경로를 검증했다. 계약 ID는
`chaser-periodic-measurement-v2`이며, backend는 **laysim-GR740 simulator**다.

기존 pilot의 `pilot-02` 구성(6 tasks, 10/20 ms period, 40 ms horizon)을 새 source로
빌드했다. Task별 9,600 loads/job, 고정 data layout, explicit core-order policy를 유지했다.
G/C/P 각각의 최종 ELF에서 6개 wrapper의 접근열·locality 분석 대응을 확인했다.
독립 U는 같은 P ELF의 task 하나만 core 0에서 실행한다. 진단도 같은 ELF를 사용한다.

| 검증 | 결과 |
|---|---:|
| 일반 G/C/P timing | 3 × 10 = 30/30 성공 |
| 독립 U | 6 tasks × 10 = 60/60 성공 |
| G/C/P 및 독립 U 진단 | 4/4 성공 |
| Empty-job | 10/10 성공 |
| 의도적인 마지막 job overrun | 1회, 예상대로 실패 |
| 전체 보존 실행 / job | 105회 / 819개 |
| Timing·U에 포함되는 job | 720개 |
| 전체 verifier | 302 passed in 45.83s |
| 기존 v1 raw 재검사 | 790/790 성공, 기존 합계와 일치 |

105회 중 104회가 정상 완료됐으며 overrun 1회는 `deadline_miss`, `period_state`,
`postponed_job`으로 거부됐다. 해당 실행은 job이 하나라 다음 `period()`의 timeout에
의존하지 않는다. G/C의 공유 domain 내 migration과 P의 singleton 실행을 진단에서 확인했다.
최종 raw log는 `load_batch()`로 다시 읽어 입력·ELF·구현·로그 hash와 저장된 합계를 확인했다.

TET는 모든 job의 CPU 차이 합, TAT는 nominal release부터 completion까지의 합이다.
Elapsed 평균·최댓값은 별도 지표다. Empty-job 40개의 CPU 비용은 5,400–9,104 ns,
평균 6,351 ns였으며 workload 측정에서 빼지 않았다. 일반 실행에는 내부 epoch,
watchdog/EDF 필드가 없고 `ready_ns`는 null이다.

공개 status 호출 전후 uptime과 `since_last_period`로 가능한 epoch 구간을 계산한다.
Job 전후 구간의 교집합이 nominal release와 일관되는지 검사하며, 내부 epoch의 직접
관측으로 해석하지 않는다. 세부 계약은 [harness README](../../../rtems/periodic/README.md)를
따른다. API 의미는 [RTEMS rate-monotonic 문서](https://docs.rtems.org/docs/6.1/c-user/rate-monotonic/directives.html#rtems-rate-monotonic-get-status)에 설명되어 있다.

이 결과는 측정 경로 전환 검증이다. RF 학습·θ 보정·family split 동결·hardware cache
검증을 완료한 것이 아니다. 임시 label은 G이며 4개 표현의 feature를 만들었지만,
독립 taskset은 하나이고 모든 행은 `eligible_for_training=false`다.

## 수정 과정에서 보존한 실패

- 첫 탐색 1회: status 호출 직후 선점으로 한 호출 구간이 1 tick보다 넓어졌다.
  개별 폭을 제한하던 validator가 이를 거부했다. 이후 전후 구간의 교집합으로
  관측 가능 범위를 검사하도록 바꾸고 회귀 테스트를 추가했다.
- 그다음 batch 94회: timing/U 90회와 진단 2회는 통과했지만 C/P 진단 2회에서
  마지막 job 완료 뒤 자원 정리 중 domain 밖 dispatch가 기록됐다. 내부 RTEMS의
  period 삭제는 공용 object allocator lock을 사용한다. 원인이 해당 lock의 scheduler
  helping인지까지 직접 계측하지는 않았다.
- 모든 worker가 job 측정을 끝내고 period를 cancel한 뒤 cleanup barrier에서 기다리게
  했다. Coordinator가 진단 extension을 제거한 다음 삭제·종료를 허용한다. 이로써
  cleanup이 다른 worker의 측정과 겹치지 않게 했고 domain 판정 조건은 유지했다.
  변경된 ELF로 전체 최종 batch를 새로 수집했다.

초기 95회는 최종 105회에 섞지 않았다. 기존 `pilot-v1` archive도 변경하지 않았다.

## 보존 파일과 재검사

- `snapshots.tar.gz`: `pilot-02/`, `overrun/`의 manifest가 참조하는 source·waf 설정·
  object·G/C/P ELF·build log 및 최종 ELF별 분석 자료.
- `measurements.tar.gz`: 15개 batch의 protocol·boot batch·105 raw logs·집계·당시 Python 구현.
- `superseded-attempts.tar.gz`와 `superseded-attempts.json`: 이전 snapshot과 초기 95회 기록.
- `summary.json`, `utilization.json`, `provisional-samples.json`: 최종 집계와 임시 feature.
- `revalidation.json`, `legacy-revalidation.json`, `verification.txt`: 검증 범위·구현 hash·로그.
- `manifest.json`: 보존 파일의 SHA-256.

작업 원본은 `.cache/periodic-public-v2-final`과 `.cache/periodic-public-v2-final-runs`다.
새 빌드·측정에는 새 output 경로를 사용한다. Archive 안의 절대 경로는 당시 provenance다.
Archive를 별도 경로의 `snapshots/`, `runs/`로 풀면 다음처럼 재검사할 수 있다.
현재 저장소 Python 모듈과 설치 SDK가 필요하며 simulator 재실행은 하지 않는다.

```python
from pathlib import Path
from chaser.periodic_dataset import load_batch

root = Path('/tmp/chaser-public-v2-review')
for batch in sorted((root / 'runs').iterdir()):
    name = 'overrun' if batch.name == 'overrun' else 'pilot-02'
    rows = load_batch(root / 'snapshots' / name, batch)
    expected = 'failed' if name == 'overrun' else 'ok'
    assert all(row['execution_status'] == expected for row in rows)
```
