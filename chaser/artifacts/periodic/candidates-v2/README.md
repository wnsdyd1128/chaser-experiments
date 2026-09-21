# Periodic 본실험 입력 후보 v2

2026-09-21. **입력 taskset 180개를 생성했다. Runtime·실측 U·label은 아직 없다.**
TACLeBench에서 관찰한 접근 특성을 일반화한 6개 합성 원형을 사용한다.
원본 benchmark 프로그램·입력·trace는 학습 표본에 넣지 않는다.
**PolyBench는 외부 평가용으로 예약하며 패턴 도출·입력 선정·튜닝에서 제외했다.**

## 원형·후보 구성

정확한 주소식·허용 범위·출처와 생략 동작은 [recipe 계약](../../../rtems/periodic/RECIPES.md),
원본 revision·파일 SHA-256은 [출처 목록](../../../rtems/periodic/recipe-sources.json)에 있다.

| 보수적 계보 | Task 역할 A / B | 후보 수 |
|---|---|---:|
| window-coefficient | window-coeff / window-bank | 60 |
| multi-array-reuse | paired-pass / matrix-reuse | 60 |
| block-phase | row-column / row-column-mirrored | 60 |

각 taskset에 같은 계보의 두 역할을 섞는다. Task별 전용 byte 배열을 읽기만 하며,
원본의 쓰기·연산·자료형을 보존한 application 실행이 아니다. B 역할이 단순 이름 변경이
되지 않도록 후보 width는 8로 고정했다. 숫자·역할·혼합 비율로 family를 늘리지 않는다.

구성은 **3개 계보 × task 수 4종(4/8/12/16) × 아래 5개 cell × 목표 U 3종(0.5/1/1.5)**다.

| Cell | A:B | 메모리 조건 | Period 비율 |
|---|---|---|---|
| layout-half | 1:1 | 각 2 blocks, stride 1/32/4096 반복 | 1:2 |
| l1-half | 1:1 | L1 전후 크기 교대, stride32 | 1:2 |
| l1-skew | 3:1 | L1 전후 크기 교대, stride32 | 1:2:4:2 |
| llc-one | 1:1 | 첫 task의 working set만 LLC 초과 | 1:2 |
| llc-two | 1:1 | 첫 두 task의 working set이 각각 LLC 초과 | 1:2:4:2 |

모든 조합의 factorial 설계는 아니며 역할·core·period·크기 사이 상관이 남아 있다.
V1의 240개 후보와 archive는 보존했으며 v2에 자동 합치거나 재분류하지 않았다.
새 원형과 과거 가설 F1~F6의 관계는 recipe 계약에 기록했다.

## Split·부하·비용과 한계

| Split 초안 | Family 수 | Taskset 수 |
|---|---:|---:|
| Train | 1 | 60 |
| Validation | 1 | 60 |
| Test | 1 | 60 |

세 family를 기존 deterministic splitter에 넣어 얻은 **초안**이다. 후보 수 180개가
독립 family 180개를 뜻하지 않으며, train/test 각각 한 family라는 제한이 크다.
RF 충분성이나 최종 평가 다양성을 확보했다고 선언하지 않는다. 기존 개발 probe 11개를
registry에 포함하되 개발 계보 전체를 primary에서 제외한다. 서로 다른 그룹을 섞으면
전이 병합하는 규칙은 유지하며, 정확성 fixture는 후보 membership에 넣지 않는다.

- 최종 eligibility·실측 U·label·θ/policy는 pending, `dataset_ready=false`, `split_frozen=false`.
- V1의 개발 ns/load×2 비용과 sweep 계산 규칙을 재사용했다. 새 구조에서 검증된 CPU
  상한이나 WCET가 아니다. 추정 총 U 범위는 **0.256535~1.499052**이며 목표 U와 구분한다.
- 최대 **48 jobs / 64 record slots / 4,288,512 bytes**의 정렬 포함 배열 메모리.
  RTEMS 전체 메모리나 전체 분석/실행 시간의 보장은 아니다.
- 단일 policy 기본 예산은 **독립 U 18,000회 + G/C/P timing 5,400회 = 23,400회**.
  θ mapping 탐색·추가 policy·build·analysis·실패 진단 비용은 제외했다. 실제 실행 수는 0이다.
- 최종 입력/family 고정 → validation θ/policy 동결 → 최종 U·공통 G/C/P 적격성·label
  확보 → RF 순서로 진행한다. Test 결과로 입력/period/모델을 조정하지 않는다.

## 보존·검증

| 파일 | 내용 |
|---|---|
| input-pool.tar.gz | `pool/configs/`의 taskset JSON 180개, pool·registry·split 초안·구현/계약 사본·manifest |
| recipe-correctness.tar.gz | width2/8의 12개 fixture, 독립 기준 접근열, SPARC G/C/P ELF·분석·events·manifest |
| summary.json | 구성·계보·추정 U·비용 요약 |
| verification.txt | 전체 repository 검증 로그: 450 passed |
| revalidate.py / revalidation.json | 새 디렉터리 추출 후 입력·plan·기준 접근열·무결성 재검사 |
| manifest.json | artifact 파일 hash |

**180개 config / 540개 G/C/P plan**, 작은 fixture의 **36개 linked streams**를 검사했다.
Fixture의 접근 수는 architecture당 7,360개이며 모두 기준 접근열과 일치했다.
이는 후보 180개 전체의 build/runtime 또는 hardware cache 검증은 아니다.

```sh
# Workspace root에서 실행. Output은 존재하지 않는 경로를 사용한다.
python3 -m tools.rtems_periodic_pool --version 2 --output .cache/periodic-candidates-v2-new
PYTHONPATH=. python3 artifacts/periodic/candidates-v2/revalidate.py \
  --output /tmp/chaser-candidates-v2-replay-new
python3 -m pytest -q tests/test_periodic_recipes.py tests/test_periodic_pool_v2.py
CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify
```

`revalidate.py`는 보존한 원본 hash와 현재 구현의 plan/접근열을 함께 검사한다.
코드 동작이 바뀌어 실패하면 archive를 덮어쓰지 않고 원인을 확인한다. 원래 구현과
출처 계약은 `pool/implementation/`에 남아 있다. Git commit과 최종 split 동결은 수행하지 않았다.
