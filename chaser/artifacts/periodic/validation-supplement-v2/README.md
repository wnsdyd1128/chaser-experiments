# Validation 대체분 v2 — family 구성 복원

2026-09-24 상태: 이 문서는 이전 validation 대체4개 중 V2-0001의 완료 기록이다.
이 단계의 사용207개와 이후 최종 측정에서 공통 적격인198개를 구분한다.
후속 실패9개 대체는5개만 확보됐고 학습 export에 반영되지 않았다.
[최종 dataset 현황](../../../datasets/periodic-v2/README.md)을 따른다.

사용자 요청에 따라 성공했던 `validation-supplement-v1-0001`(window-coefficient)을
사용 대상에서 제외하고 새 `validation-supplement-v2-0001`(block-phase)을 생성했다.
V1 입력·U400회·G/C/P120회·manifest는 역사적 증거로 그대로 보존한다.
Window-coefficient 제외 사유는 **family 구성 수정**이며 측정 실패가 아니다.

최신 사용 소속 정본은 [active-population.json](active-population.json)이다.
보존 입력212개 중 원본 실패4개 및 window-coefficient 추가분1개를 제외하여
**사용207개, train/validation/test=126/41/40**을 유지한다. 새 입력1개의 ELF/U/G/C/P 검증은 완료·PASS다.
나머지 성공 추가분 V1-0002/0003/0004의 identity와 측정 증거는 그대로 유지한다.

| Family | 실패 원본 제외 | 최종 대체분 | Validation 전체 |
|---|---:|---:|---:|
| block-phase | 2 | 2 | 8 |
| multi-array-reuse | 1 | 1 | 8 |
| staged-butterfly | 1 | 1 | 9 |
| window-coefficient | 0 | 0 | 8 |
| triangular-solve | 0 | 0 | 8 |

원본의 family별 split 개수와 train/test 소속을 복원했다. 실패한 개별 입력의 task 수·역할 비율·
부하까지 일대일로 맞춘 것은 아니다. 제외된 원본4개는 모든 mapping·표현·G/C/P에서 제외한다.

## 새 입력 규칙 및 상태

[configuration.json](configuration.json)과 [generation-manifest.json](generation-manifest.json)을
실측 전에 저장했다. 기존 recipe generator의 block-phase, l1-half, 10 tasks, width8,
stride32 bytes, 목표 U0.5를 사용한다. 난수나 후보 탐색은 없다.
역할은 row-column/row-column-mirrored 각5개이며 distinct448/576, sweeps12/9다.
이미 성공한 V1 block-phase의 목표 U1.0과 구분되도록 목표 U0.5를 고정했다.
Period는 기존 개발 비용 추정식을 사용해50/100 ticks, horizon200 ticks로 계산된다.
초기 core는 i%4이며 보정 전 배치다. 목표 U는 실측 U가 아니다.

원본207개·중복 alias93개·개발11개·V1 추가4개와 taskset_signature 충돌이 없다.
이름·core·policy만 바꾼 복제본이 아니며 실제 period/horizon이 다르다.
G/C/P 정적 plan3개와 family 계보 검증이 통과했다. 이후 ELF build·linked stream·독립 U·
G/C/P 측정도 완료했다(아래 완료 결과 참조). 기존 window 또는 block-phase의 측정값을
새 입력에 복사하지 않는다. 수행한 기본 측정은 독립 U100회와 G/C/P30회다.
실패하면 기록을 보존하고 자동으로 후보를 교체하지 않는다.

## 재현 및 검증

```sh
PYTHONPATH=. python3 artifacts/periodic/validation-supplement-v2/rebuild.py
```

재현 검사는 저장 config·manifest·소속과 재생성 결과를 비교한다. 별도 경로로 생성하려면
`--output <존재하지 않는 경로>`를 지정한다. 기존 출력은 덮어쓰지 않는다.
재현 검사 PASS, 관련 `test_periodic_pool_v2.py`·`test_periodic_freeze.py` **8 passed**.
Production generator·harness·parser는 변경하지 않았고 finalize는 호출하지 않았다.

이 새 입력의 ELF 준비·분석 → 독립 U → 현재 mapping G/C/P 검증은 완료했다.
최신207개 소속은 [보정 v2 loader](../calibration-v2/README.md)에 연결했다. 다음은 θ 후보/mapping 재계산이다.
V1 소속이나212개 보존 목록을 그대로 보정 입력으로 사용하지 않는다.

## 3단계 실행 기록 (2026-09-22, 완료)

사용자는 문서화·handoff와 함께 ELF → U100회 → G/C/P30회까지 실행하도록 지시했다.
`collect.py`가 위 순서를 자동 실행한다. 입력 재현·hash 확인 후 G/C/P ELF와 전체 linked
stream을 분석하고, 독립 U100회의 raw를 재검증해 feature를 생성한다. U 상한·undefined
feature gate가 통과해야 일반 G/C/P30회를 시작한다. G/C/P 실패도 raw를 재파싱하며,
끝에서 U를 다시 계산해 기존 증거 불변을 확인한다. θ 보정·label 생성은 수행하지 않는다.

20:26:16 UTC에 PID **1302613**으로 백그라운드 실행을 시작했다. 당시 시작 확인은
`phase=prepare`였으며, 최종적으로 20:31:30 UTC에 exit0으로 완료했다.
독립 U workers16·timeout600초, G/C/P workers16·timeout1800초다.

```sh
cat .cache/validation-supplement-v2-validation/summary.json
```

동일 경로의 `progress.json`, `gcp/run-progress.json`은 단계·G/C/P 진행 상태이며,
`summary.json`·`exit.json`이 최종 결과다. 예외 발생 시 `failure.json`과 로그를 확인한다.
실패 시 후속 gate를 통과시키거나 자동 재시도하지 않는다. 같은 launcher를 다시 실행하지 않는다.
관련 기존 수집기 검사 `python3 -m pytest -q tests/test_periodic_gcp.py
 tests/test_periodic_characterization.py`는 **40 passed in 0.59s**이고 V2 입력 재현 및
wrapper 구문 검사도 통과했다. 수집 실행 당시 전체 verifier와 finalize는 실행하지 않았다.

## 완료 결과 및 증거 보존 (2026-09-23 문서화)

2026-09-22 20:31:30 UTC에 검증을 완료했다. 수집기를 재실행하지 않고 기존 실행 결과를
대조하여 기록했다. [summary.json](validation-evidence/summary.json)의 status는 `pass`,
[exit.json](validation-evidence/exit.json)의 exit_code는 `0`이다.

| 검증 | 결과 |
|---|---|
| ELF 준비·linked stream 분석 | G/C/P 3개 검증 후 U 단계 진입 |
| 독립 U | 100/100회 성공 |
| G / C / P | 각각 10/10회 성공, raw_errors 모두 빈 배열 |
| Raw 재검증 | raw_revalidated=true |
| U·feature gate | within_u_bounds=true, undefined_features={} |
| G/C/P 이후 U 증거 불변 | u_evidence_unchanged=true |
| θ/policy 동결 | false — 보정과 최종 label 생성은 후속 |

`validation-evidence/`의 summary·exit·[source-hashes.json](validation-evidence/source-hashes.json)은
`.cache/validation-supplement-v2-validation/`에서 바이트 그대로 복사한 비-raw 실행 증거다.
Source hash는 수집 당시 입력·코드의 identity를 기록하며 문서 수정 후 재생성하지 않았다.
생성 당시 `generation-manifest.json`과 `active-population.json`의 pending 표기는 당시의
검증 상태로 보존한다. 최신 사용 소속은 계속 active-population이며, 실행 완료 상태는
위 summary·exit를 참조한다. 이 문서 변경은 측정 identity를 바꾸지 않는다.

Raw logs, ELF/linked-stream 분석 산출물, U/feature 상세 자료는 기존 ignored cache에
그대로 남는다. 이 세 JSON의 버전 관리만으로 전체 측정 증거를 백업하는 것은 아니며,
이관 시 cache를 별도로 보존해야 한다. 기존 수집기나 출력 디렉터리를 재실행·덮어쓰지 않는다.

기본 mapping의 검증 PASS는 새 θ 후보의 모든 mapping 검증이나 calibration 완료를 뜻하지
않는다. 최신207개 소속 연결은 완료했으며, 다음은 θ 후보/mapping 재계산 → 실행 동등성에 따른 기존 측정 재사용
판별 및 추가 예산 산출 → 필요한 측정 → θ/policy 동결 순서로 진행한다.

이번 문서화 검증: 증거 JSON 3개 원본 바이트 일치, 수집 당시 source hash 전체 일치,
V2 입력 재현 및 두 README의 로컬 링크 검사 PASS. `sh scripts/verify`는 빌드 성공,
**608 passed, 1 skipped**(선택적 cold-Cachegrind 검사)로 종료했다. Finalize는 호출하지 않았다.
