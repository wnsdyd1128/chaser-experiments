# Historical dataset calibration v2 — theta/policy frozen

이 문서는 이전 실험의 결과 기록이다. 당시 사용한 보정·이동·재사용 감사 코드는
현재 실험 계약으로 전환하면서 삭제했으며, 아래 수치는 새 실험의 보정 결과가 아니다.

## 보정 완료 (2026-09-23)

Validation 41개·448 tasks로 새 계획을 생성했다. 모든 θ 후보에서 allocation 실패는
0개이며, 세 표현의 공통 비교 대상은 각각 validation 41개 전체다. CLS는 α=0.5다.

| 표현 | θ 후보 | Mapping 수 |
|---|---:|---:|
| CAAS-CA | 30 | 137 |
| CA-CSRD | 32 | 142 |
| CLS(0.5) | 41 | 161 |

표현 간 중복을 제거하면 **189개 P batches·1,890회**다.
[재사용 감사](reuse-audit.json)는 기존 calibration-v1의 **175개·1,750회**가 새 계획의
configuration, source/tool/layout/locality/linked-stream, 원래 U provenance와 일치하고,
현재 raw 재파싱 및 정상 P10회 gate를 통과했음을 기록한다.
[연결표](reuse-links.json)의 symlink로 원래 snapshot과 batch를 그대로 읽으며,
기존 manifest·protocol·measurement·raw hash 2,450개를 재확인했다.
G/C/P census의 P는 이 기존 P 증거를 참조하므로 별도 측정으로 중복 집계하지 않는다.

[추가 예산](budget.json)은 **14개 mapping·P140회·새 G/C/P ELF42개**다.
V1-0002/0003/0004에서 각각3/4/4개, V2-0001에서3개다. 모두 보충 수집의 기본 core
배치와 다르고 policy/plan/ELF identity도 다르므로 기존 기본 P 측정을 옮기지 않는다.
Prepare workers=8, simulator workers=16, process timeout=1,800초를 유지한다.
252,000초의 직렬 timeout 합은 실제 wall-time 예상이 아니다.

준비 단계는 **189/189 PASS**다. 기존175개 snapshot을 재검증하고 신규14개를 빌드·분석했다.
추가 P는 **140/140회 성공**, raw 오류0개다. 전체 **189개·1,890회**의 정상 P 증거를
현재 검증기로 확인한 뒤 validation만 사용하여 [θ/policy](frozen-policies.json)를 동결했다.

| 표현 | 동결 θ | Validation 평균 TAT (ns) |
|---|---:|---:|
| CAAS-CA | 0.00024213793881011828 | 209225339.97560975 |
| CA-CSRD | 0.17815304558548267 | 201318593.53658536 |
| CLS(0.5) | 0.8871558208945556 | 201241571.0 |

선택 순서는 실패 workload 수 최소화 → 공통41개 workload의 P10회 median TAT 평균
최소화 → 작은 θ다. 세 표현 모두 최적 후보의 allocation 실패는0개이고 TAT 동률은 없다.
위 TAT는 validation 보정 목적함수이며 test 성능 개선이나 최종 architecture label 결과가 아니다.
동결 파일은 전체 후보·mapping별 측정값과 evidence hash, 원본 split 및 현재207개 소속
identity, allocator hash를 포함한다. 원래 U ELF identity는 유지했다.
전체 freeze를 재실행해 raw를 다시 검사했으며 동결 파일은 byte-identical이었다.
[완료 기록](completion-summary.json)에 신규140회 raw hash, 단계별 결과, θ 선택값,
동결 재현 및 검증 결과를 보존했다.

새 계획과 상세 실행 증거는 `.cache/calibration-v2/`에 있다. 이 예산은 validation의
P 보정 범위이며, 동결 policy별 최종 G/C/P label과 α sweep을 포함하지 않는다.

다음 단계는 고정된 세 policy를 최종207개에 적용하여 mapping과 실행 identity를 계획하고,
기존 G/C/P 측정과의 재사용 대응표·추가 예산을 산출하는 것이다. 그 후 최종 label을
확보하여 RF/S2~S5 평가를 진행한다. Test 결과를 이용한 θ 재조정은 하지 않는다.

2026-09-24 후속 상태: 최종 세 정책의 배치·G/C/P 측정과 label export가 완료됐다.
[최종 summary](../../../datasets/periodic-final-v1/summary.json)의 공통 적격198개를 사용한다.
대체9개 중5개 확보·4개 미확보이며 보충 export는 없다. CLP export·RF 학습은 미완료다.
[현재 dataset 안내](../../../datasets/periodic-v2/README.md)를 따른다.
최종 mapping 보고서와 `.cache/final-mapping-v1/plan.json` 원본은 이후 캐시 정리 과정에서 삭제됐다.

이번 검증: `python3 -m pytest -q tests/test_periodic_calibration.py` **30 passed**;
`CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify` **621 passed**, skip 없음,
75.81초. Finalize는 명시 요청되지 않아 실행하지 않았다. Git 상태 변경도 수행하지 않았다.

## 이전 loader 연결 기록

2026-09-23: 최종 사용 데이터셋을 보정 loader에 연결했다. 소속 정본은
[V2 active-population](../validation-supplement-v2/active-population.json)이며,
보존212개 중 사용207개(train/validation/test=126/41/40)다.
원본 실패4개와 V1-0001은 제외한다. 보정에는 validation 기존37개와
V1-0002/0003/0004, V2-0001만 사용한다.

## 입력 및 증거 연결

[input-sources.json](input-sources.json)은 소속 파일·원본 population/split의 hash와
대체4개의 snapshot, U batch, utilization/features 경로 및 증거 hash를 고정한다.
경로는 workspace root 기준이다. 원본 frozen 입력과 cache를 수정하거나 측정 증거를
다른 ELF identity로 복사하지 않는다. 원본과 V1은 `runs/<workload>/uN`, V2는 `u/uN`의
기존 로그를 직접 읽는다.

Loader는 전체 소속·family별 split 개수와 train/test identity를 먼저 확인한다.
그 후 validation만 로드하여 config hash, snapshot/source 및 analysis manifest,
raw U, utilization, feature, U 상한과 undefined feature 검사를 수행한다.
Toolchain/simulator identity도 보정 계획 작성 시 기존과 동일하게 검사한다.
Mapping 준비 단계의 source/tool/layout/locality/linked-stream 비교도 유지한다.

원본 frozen split hash와 새 active membership/assignments hash는 구분하여 기록하며,
active identity를 후속 보정 계획과 동결 policy에 포함한다. `--input-sources`를 생략하면
역사적 원본 데이터셋 경로이므로 현재 데이터셋 보정에는 반드시 아래 연결 파일을 지정한다.
기존 calibration-v1 출력은 재사용하거나 덮어쓰지 않는다.

## 데이터셋 저장 위치 분리 완료 (2026-09-23)

사용207개 입력·characterization과 validation 보정 증거를
[`datasets/periodic-v2/`](../../../datasets/periodic-v2/README.md)로 이동했다.
현재 구조와 데이터 경로는 그 디렉터리의 README와
[dataset.json](../../../datasets/periodic-v2/dataset.json)을 기준으로 읽는다.

- `inputs/`: 사용207개 설정, train/validation/test=126/41/40.
- `characterization/<workload_id>/`: 실제 ELF·분석·feature·독립 U 및 보충 입력4개의 기본 G/C/P.
- `calibration/`: mapping189개, 기존175개 G/C/P와 신규14개 P, θ/policy·측정·감사 기록.
- `provenance/`: 원본 frozen 계보, 보충 생성·수집 기록, 이전 목록·hash 및 새 위치 연결표.

이동·복사 대상으로 고정한 payload는 **215,631개 파일·7,445,536,325 bytes(약7.45GB)**다.
데이터셋 내부에는 symlink가 없으며, 제외된 원본4개와 V1-0001의 실행·측정 증거는 기존에
보존한다. 전체 원본 frozen manifest 검증을 위해 제외 입력의 config도 provenance에 포함하지만
사용 population에는 포함하지 않는다. 이동 당시에는 최종 label이 없었으며, 현재는 별도 `datasets/periodic-final-v1/`에 198개가 export됐다.

기존 `.cache` 루트·snapshot·U 디렉터리는 실제 디렉터리로 유지하고, 자식16,655개를 새 위치로
향하는 상대 symlink로 연결했다. 기존350개 calibration 재사용 링크도 그대로 동작한다.
`Path.resolve()`에 포함되는 디렉터리 identity를 유지하므로 기존 보정 CLI는 아래 명령을
계속 사용한다. 이 문서의 `.cache` 경로는 현재 같은 파일을 읽는 호환 경로다.

기존 artifacts의 소속·입력 연결 파일과 모든 측정·policy 바이트 및 hash는 보존했다.
새 위치 정보는 별도로 기록했으며 역사적 절대경로를 일괄 치환하지 않았다.
다른 workspace로 이 디렉터리를 복사하면 payload는 함께 보관할 수 있지만, 기존 CLI 실행에는
역사적 경로 연결 및 toolchain/simulator 환경이 추가로 필요하다.

당시 이동 스크립트는 plan→move→verify 순으로 실행했다. 이동 전후 파일 hash와
기존 경로의 동일성을 검증하며, rename과 링크 생성 사이에 중단돼도 이동된 바이트를 확인하고
연결을 복구한다. 검증 결과는 [relocation-summary.json](relocation-summary.json)에 보존한다.
대용량 payload는 Git에서 제외하며 새 README와 `dataset.json`만 관리한다.

## 연결 검증 결과

[loader-validation.json](loader-validation.json)은 실제 기존 cache에 대한 검증 기록이다.
Validation **41개·448 tasks·독립 U raw 4,480회** 재검증 및 tool identity 검사가 PASS다.
기존 U characterization ID와 U ELF hash를 입력별로 보존했다. Train/test의 feature/raw는
보정 입력으로 로드하지 않았다. 이 기록은 새 timing 수집이나 θ 선택 결과가 아니다.

## 당시 계획 및 감사

당시 계획은 `input-sources.json`의 연결 자료를 사용해 생성했다. 관련 CLI와 감사 스크립트는
삭제했다. 보존한 연결 파일과 검증 기록만으로 raw 측정을 다시 수행할 수는 없다.

## Loader 연결 당시 구현 검증

- `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify`: 빌드 및 전체 **620 passed**, skip 없음.
- 전체 검증 시작 후 추가한 active policy identity 검사까지 포함한
  `python3 -m pytest -q tests/test_periodic_calibration.py`: **30 passed**.
- 실제 loader 검증 기록의 구현 hash, 문서 로컬 링크, `git diff --check`: PASS.
- Finalize는 호출하지 않았다.
