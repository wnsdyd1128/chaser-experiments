# Validation 추가 4개 — 측정 전 생성 규칙 v1

최신 사용 소속은 [V2](../validation-supplement-v2/README.md) 및 [V2 manifest](../validation-supplement-v2/active-population.json)다. 사용자 요청으로 V1-0001(window-coefficient)을 제외하고 V2-0001(block-phase)을 새로 생성했다. 보존212개·사용207개이며 원래 family별 개수를 복원했다. V2 새 입력의 ELF/U/G/C/P 검증과 θ/policy 동결은 완료됐다. 최종198개 학습 export와 후속9개 대체 현황은 [현재 dataset 안내](../../../datasets/periodic-v2/README.md)를 따른다. 아래 V1 소속과 검증 결과는 역사적 기록이다.

## 현재 V1 사용 입력

`input-preparation.json`의 현재 사용 목록에서 V1-0001을 삭제했다.
V1에서 유지하는 입력은 **0002(block-phase), 0003(multi-array-reuse),
0004(staged-butterfly)** 세 개다. 새 block-phase는 V2-0001로 연결한다.
[active-population.json](active-population.json)은 V2의 최신207개 사용 소속과 동일하다.
이전 소속 및 준비 기록은 `history/`로 분리했다. 아래 생성·측정 기록과 동결 archive는
당시 실행의 증거이며 현재 사용 목록이 아니다.

## 이전 생성·측정 기록

2026-09-22. **생성 규칙 고정과 실행용 입력 4개 준비 완료.** 고정된 입력 identity와
일치하는 config 및 별도 validation 확장 metadata를 생성했다. 등록 입력은211개,
train/validation/test=126/45/40이며 유효 표본 수가 아니다. θ/policy는 미동결이다.
ELF 분석과 독립 U 수집의 현재 상태는 아래 실행 기록을 따른다.

정본은 [generation-manifest.json](generation-manifest.json)이며,
[추가 실험 계획](../../../system-prompt-extraction/plan/VALIDATION-SUPPLEMENT-V1.md)의
첫 단계에 해당한다. 원본 207개·split·성공/실패 증거를 보존한다.

## 선택 및 생성 규칙

- Version `validation-supplement-v1`, seed **20260922**. 기존 5개 family를
  `sha256(canonical JSON [version, seed, family_id])` 오름차순으로 정렬하고 앞의
  4개에 하나씩 배정한다. 동률은 family_id 순서다. Seed는 family 선택에만 사용한다.
  전체 순위·해시와 빠진 triangular-solve도 manifest에 기록했다. 원본 split seed는 그대로다.
- 공통 조건은 **10 tasks, l1-half, width=8, stride=32 bytes, 목표 총 U=1.0**이다.
  10 tasks는 지원 범위 1..16 안이며, 원본의 4/8/12/16-task 입력과 구분된다.
  기존 L1 경계 프로파일을 사용하며 LLC coverage 확장이나 실패 입력의 대응 표본은 아니다.
- Family별 두 역할을 번갈아 5개씩 배정한다. 완전한 block 단위로 짝수 task는
  `floor(480/block_size)`, 홀수 task는 `ceil(544/block_size)` blocks를 사용한다.
  역할별 실제 distinct·sweeps·period와 모든 ID·입력 해시를 manifest에 고정했다.
- Sweep은 기존 `max(2, ceil(10240 / 한 sweep의 접근 수))`다. Period는 보존 V3의
  개발 비용 추정값 153.96585083007812 ns/load와 margin=2로 계산한다.
  짝수/홀수 period 비율은 1:2, horizon은 base period의 4배, 초기 core는 `i % 4`다.
  이 core 배치는 보정 전 배치다. **목표·추정 U는 실측 U나 실행 가능성의 증거가 아니다.**

| 고정 ID | Family | Period ticks (역할 A/B) | Horizon ticks | 추정 총 U |
|---|---|---:|---:|---:|
| validation-supplement-v1-0001 | window-coefficient | 30 / 60 | 120 | 0.968137 |
| validation-supplement-v1-0002 | block-phase | 25 / 50 | 100 | 0.981440 |
| validation-supplement-v1-0003 | multi-array-reuse | 26 / 52 | 104 | 0.985381 |
| validation-supplement-v1-0004 | staged-butterfly | 25 / 50 | 100 | 0.993819 |

각 taskset은 30 jobs·40 record slots로 기존 운영 한도 64 이하다. 기본 후속 예산은
독립 U **400회**와 단일 policy G/C/P **120회**다. θ 탐색·추가 mapping·build·분석 비용은
별도이며, 이 수치는 전체 보정 예산이나 wall-time 예측이 아니다.

## 중복·계보·split·실패 처리

`taskset_signature`로 이름·policy·core를 제외하고 순서·작업량·접근 구조·period·horizon을
비교한다. 원본 train/validation/test 전체 207개, 중복 alias 93개, 개발 입력 11개 및
추가분 서로 간의 충돌은 0이다. 원본과 합친 registry에서도 기존 family ID가 유지되고
개발 계보 노출은 없다. 같은 family의 parameter 변형이며 새로운 독립 family가 아니다.

추가 네 개의 소속은 전부 **validation**이다. 별도 확장 metadata의 등록 수는
211개, train/validation/test=126/45/40이다. 이 manifest는 기존 schema2 split을
대체하거나 실행 도구에 바로 전달하는 파일이 아니다. 원본 무작위 분할의 일부였다고
기술하지 않으며, 유효 표본 수는 후속 측정·공통 유효집합 판정과 구분한다.

중복·정적 검사 실패 시 중단하고 기록을 남긴다. 재추첨·자동 후보 교체는 없다.
측정 실패도 보존하며 성공 네 개를 얻을 때까지 추가하지 않는다. 기존 실패 40회와
추가 결과를 원본 raw 행에 덮어쓰지 않는다. 최신 결정에 따라 실패 taskset 전체는 사용
데이터셋에서 제외한다. 이 소속과 보정 loader·freeze gate의 연결은 남아 있으며,
추가 네 개의 성공만으로 θ/policy를 동결하지 않는다.

## 검증·다음 단계

과거 입력 재검증 결과는 [revalidation.json](revalidation.json)에 보존했다.
구 후보군 관련 스크립트는 정리했으므로 이 archive를 현재 코드로 재생성하지 않는다.
원본 membership hash는
`92574a43fe183e6b3652d894bc97758a9c90b200d638225437fd20d543c1a50f`로 유지됐다.

원본 후보·동결 archive 전체의 기존 manifest hash 일치와 생성 코드 변경·원본 중복 입력의
거부를 확인했다. `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify`는
**609 passed, skip 0 (79.62초)**다. [검증 기록](verification.json)과
[전체 로그](verification.log)를 보존한다. Finalize는 명시 요청이 없어 실행하지 않았다.

## 입력 준비 및 독립 U 실행

[입력 준비 기록](input-preparation.json), [확장 소속](extension.json),
[입력 archive](prepared-inputs.tar.gz)를 보존했다. 작업 경로는
`.cache/validation-supplement-v1-inputs/`다. 원본207개는 복제 측정하지 않으며,
기존 성공 증거의 재사용 적격성은 보정 계획을 연결할 때 별도로 판단한다.

`supplement_inputs.py`는 고정된 네 개 config를 복원해 입력·plan hash를 검증하고,
부모 split을 그대로 복사한 별도 extension을 만든다. 기존 schema2 분할기를 재실행하지
않고, 기존 frozen-input verifier가 추가 입력을 받도록 완화하지도 않는다.
확장 metadata의 보정 도구 연결과 공통 유효집합·freeze gate 정합성은 후속 작업이다.

`collect_supplement.py`는 기존 prepare/analyze/run/load_batch/characterize 함수를 호출한다.
4개 taskset·12개 ELF의 layout·전체 linked stream 분석이 모두 통과해야 U를 시작한다.
U는40 tasks ×10회=400회, workers16, timeout600초다. 각 task는 동일한 최종 P ELF에서
core0에 단독 실행한다. Raw 로그를 다시 파싱해 U·feature를 만들며 실패 batch는
덮어쓰거나 재시도하지 않는다. 일반 G/C/P timing·θ 보정·label 생성은 실행하지 않는다.

실행 결과 경로는 `.cache/validation-supplement-v1-characterization/`이며,
`collection.log`, `pid`, `launch.json`, `progress.json`, `summary.json`, `exit.json`을 사용한다.
완료 여부는 summary/exit로 확인한다. 수집기 시작 기록이 측정 완료나 실측 적격성을
뜻하지 않는다. 준비 실패 시 U를 전부 차단하고, U 실패 시 해당 raw를 보존한다.

2026-09-22T19:28:11Z에 분리 프로세스 PID **1282987**을 시작했다.
19:28:31Z 상태에서 준비4/4·ELF12개·분석이 모두 통과했고 독립 U400회 수집에 진입했다.
[시작 기록](launch.json)을 보존하며 반복 polling이나 완료 대기는 하지 않는다.

```sh
tail -f .cache/validation-supplement-v1-characterization/collection.log
```

당시 전용 실행 검사는 입력 identity·변조·덮어쓰기 거부, 준비 실패 gate,
실패 batch 재파싱과 재시도 금지, 두 번째 수집 호출 거부를 확인해 **6 passed**였다.
구 후보군 관련 테스트 파일은 이후 정리했다.
이번 실행 스크립트 추가 후 전체 `scripts/verify`도 **609 passed, skip0 (77.71초)**다.
[실행 검증 기록](execution-verification.json)과 [로그](execution-verification.log)를 보존한다.
입력 archive의 모든 파일은 작업 입력과 바이트 일치 검사를 통과했다. Finalize는 실행하지 않았다.

## 현재 고정 mapping의 G/C/P 검증

독립 U 수집은 2026-09-22T19:30:35Z에400/400 성공·exit0으로 완료됐다.
네 taskset 모두 U 상한을 충족하고 undefined feature·제외 항목이 없다.
사용자 요청에 따라 θ 후보 재계산 전에 현재 고정 mapping의 일반 G/C/P를 먼저 검증한다.
Policy는 `validation-supplement-v1-explicit-core-order-not-calibrated`이며,
C는 기존 core{0}/{1,2,3} EDF SMP다. 이 결과로 θ/policy가 동결되지는 않는다.

2026-09-22T20:01:09Z, PID **1293156**으로 백그라운드 수집을 시작했다.
사전 검사에서 입력·ELF plan12개·linked 분석과 독립 U raw400회를 재검증했다.
4 tasksets × G/C/P ×10회 = **120회**, workers16, 실행당 timeout1800초다.
당시에는 구 G/C/P collector를 사용했으며 준비된 ELF나 harness/parser를 변경하지 않았다.
수집기 관련 테스트20개와 wrapper 구문 검사가 통과했다.

[실행 기록](gcp-execution.json)과 [시작 기록](gcp-launch.json)은 남겼다.
당시 `.cache/validation-supplement-v1-gcp/` raw와 wrapper는 이후 정리했다.

```sh
tail -f .cache/validation-supplement-v1-gcp/collection.log
```

`collection/run-progress.json`은12개 batch의 진행 상태다. 종료 후 `summary.json`에
architecture·taskset별 성공/실패, 실패를 포함한 raw parser 오류, 기존 U 파일 hash
불변 여부를 기록하고 `exit.json`에 종료 코드를 저장한다. 검증 예외로 summary가
생성되지 않은 경우에도 exit/log를 확인한다. 실패는 재시도·대체하지 않는다.
