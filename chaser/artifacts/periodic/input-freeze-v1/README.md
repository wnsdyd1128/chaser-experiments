# 본실험 입력·split 동결 v1

2026-09-21. [V3 후보](../candidates-v3/README.md)의 **고유207개 입력**을 변경 없이
고정하고, 5개 워크로드군 각각을 train/validation/test 60/20/20으로 분할했다.
알려진 워크로드군의 새 taskset에 대한 평가다. 기존 V1~V3 archive는 보존한다.

| 워크로드군 | 고유 입력 | Train | Validation | Test |
|---|---:|---:|---:|---:|
| window-coefficient | 41 | 25 | 8 | 8 |
| multi-array-reuse | 41 | 25 | 8 | 8 |
| block-phase | 41 | 25 | 8 | 8 |
| staged-butterfly | 43 | 26 | 9 | 8 |
| triangular-solve | 41 | 25 | 8 | 8 |
| 합계 | **207** | **126** | **41** | **40** |

## 고정한 규칙

- Policy: `taskset-stratified-60-20-20-v1`, schema2, seed **20260921**.
- 군별 입력을 canonical JSON `[policy_id, seed, family_id, input_signature]`의 SHA-256
  오름차순으로 섞는다. 입력 순서와 Python 난수 구현에 의존하지 않는다.
- 정수 배정은 3/5·1/5·1/5의 내림값에 나머지가 큰 순서로1개씩 더한다.
  동률은 **train→validation→test**다. 군당 고유 입력3개 이상을 요구한다.
  빈 split이 생기면 가장 큰 split에서1개 옮긴다(동률 동일 순서). 따라서3개는1/1/1이다.
- Taskset 식별자는 이름·eligibility·policy·core 배치를 제외한다. Task 순서, 접근 구조,
  크기·stride·sweep·period·horizon은 보존한다. 배치까지 포함한 실행 입력 hash도 별도로
  남기며, 동일 taskset의 G/C/P·반복·표현·policy별 결과는 같은 split을 사용한다.
- 300개 요청 중 중복93개는 대표ID·원본 config·사유를 보존하고 대표의 split을 참조한다.
  개발 probe11개는 제외한다. Policy 변형과 이름 변경을 새 독립 표본으로 세지 않는다.
- 입력/소속을 추가·교체하거나 test 결과로 재분할하지 않는다. 부하 초과·deadline miss·측정
  실패는 원래 membership과 사유를 유지한다. 이 동결본에 자동 확장 pool은 없다.

Membership hash:
`92574a43fe183e6b3652d894bc97758a9c90b200d638225437fd20d543c1a50f`.
[split.json](split.json)은 모든 입력의 소속·signature·군별 수를,
[population.json](population.json)은 config hash·실행 입력 hash·중복 대표 관계를 담는다.

## 입력 범위·예산·남은 검증

V3의 task·sweep·period·horizon과 원형 출처를 그대로 고정했다. 기존 추정 부하 설계의
`u_max=0.25`, `U_max=2.0`을 이후 독립 실측 U에 적용할 사전 상한으로 채택했다.
이는 deadline 보장이 아니다. Snapshot의 초기 core 배치와 policy는 보정 전 상태이며,
후속 policy는 별도 실행 snapshot을 만든다. 작업량과 split identity는 그대로 유지한다.
Source config의 `eligible_for_training=false`와 `test_eligible=false`는 원형 보존 값이다.
Split membership은 schema2 manifest가 정하고 실제 학습 적격성은 후속 실측으로 판정한다.

- 독립 U: task별10회, 합계 **21,680회**.
- G/C/P timing: architecture별10회, 단일 policy **6,210회**.
- 기본 합계 **27,890회**. θ 후보·추가 policy/α·build·analysis·진단은 별도다.
- 전체 wall-time·저장량과 보정 탐색 예산은 아직 미확정이다.
- 후보 runtime·실측 U·label·RF는 아직 없다. `inputs_frozen=true`, `split_frozen=true`,
  `dataset_ready=false`, `sufficiency_status=not_assessed`다.

LLC 고부하 구간 공백과 역할/core/period 상관은 남아 있다. 현재 동결은 입력·분할 단계의
완료이며 통계적 충분성, 실제 deadline 적격성 또는 원 계획 순서4의 모든 비용 검토 완료를
뜻하지 않는다. TACLeBench를 일반화한 합성 입력이며 PolyBench는 외부 평가용으로 유지한다.

## 이후 순서

1. 입력·split 고정 — 이 산출물로 완료.
2. 최종 ELF 분석·layout 검증과 독립 U·정적 feature 수집.
3. Validation mapping별 TAT 측정으로 θ·policy 보정·동결.
4. 동결 policy별 G/C/P 측정으로 최종 적격성·label 확정.
5. Train RF/scaler 학습, validation 모델 선택, test 평가.

θ 보정에는 RF나 architecture label이 필요하지 않다. θ 변경은 C/P 배치와 최적 label을
바꿀 수 있다. 고정한 baseline policy로 S2부터 수행하는 경로는 선택 사항이며, 이후 변경된
allocator의 label·RF까지 대신하지 않는다. [운영 문서](../../../rtems/periodic/README.md)를 따른다.

## 검증·재현

전체 `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify` 결과는
**532 passed in 72.92s**다. 분할 재현성·군별 정수 배정·작은 군 처리·복제본과 policy 변형·
반복 측정·dataset 연결·동결 재사용·입력 변경과 변조 거부를 검증했다.
기존 V3 재검증은207 configs/621 plans/24 linked streams에 대해 PASS다.
새 동결 archive 재검증은 source hash·registry·621 plans·93개 중복·split·공개 metadata를
다시 검사한다. 이 작업에서 후보 simulator 실행과 finalize는 수행하지 않았다.

| 파일 | 내용 |
|---|---|
| frozen-inputs.tar.gz | 동결 입력, source V3 원본, split/population/summary, 구현 snapshot과 manifest |
| split.json / population.json / summary.json | 검토용 동결 metadata; archive 내용과 바이트 일치 검사 |
| source-revalidation.json | 보존 V3 archive·작은 fixture 재검증 결과 |
| verification.txt | 전체 빌드·테스트 로그 |
| revalidate.py / revalidation.json | 새 경로에서 동결 산출물 재검증 |
| manifest.json | 위 산출물 hash |

새 경로에서 재검증:

```sh
PYTHONPATH=. python3 artifacts/periodic/input-freeze-v1/revalidate.py \
  --output /tmp/chaser-input-freeze-replay-new
```

동일 동결을 재생성할 때도 기존 출력은 덮어쓰지 않는다:

```sh
PYTHONPATH=. python3 artifacts/periodic/candidates-v3/revalidate.py \
  --output /tmp/chaser-v3-source-new
python3 -m tools.rtems_periodic_freeze freeze \
  --pool /tmp/chaser-v3-source-new/pool --output /tmp/chaser-frozen-new
python3 -m tools.rtems_periodic_freeze verify /tmp/chaser-frozen-new
```
