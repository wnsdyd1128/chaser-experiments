# Periodic 입력 후보 v3 — 단계·삼각 계보 확장

2026-09-21. 사용자 결정에 따라 TACLeBench 근거로 계보를 보강했다.
기존 출처 기반 3개 계보에 **staged-butterfly와 triangular-solve**를 추가하여
**5개 계보·207개 고유 입력**을 생성했다. Runtime·실측 U·label·RF는 아직 없다.

| 계보 | Task 역할 | 고유 후보 |
|---|---|---:|
| window-coefficient | window-coeff / window-bank | 41 |
| multi-array-reuse | paired-pass / matrix-reuse | 41 |
| block-phase | row-column / row-column-mirrored | 41 |
| staged-butterfly | butterfly-twiddle / butterfly-scale | 43 |
| triangular-solve | triangular-solve / triangular-solve-transposed | 41 |

새 두 계보는 고정 revision의 FFT stage와 LU forward/back substitution에서 읽기 주소
관계를 일반화했다. [계약](../../../rtems/periodic/STAGED-RECIPES.md)에 source anchors,
주소식·load 수·허용 범위·생략 특성·계보 관계를 명시한다. Triangular 두 역할은 공간 배치
대비이며 같은 temporal reuse다. Butterfly n=2는 정확성 fixture에만 사용하고 후보는 n=8이다.
Benchmark 자체·입력·trace를 학습 표본으로 사용하지 않으며 PolyBench는 외부 평가용이다.

## 중복과 구성

5계보 × task 수4/8/12/16 × 기존5 cell × 목표 U0.5/1/1.5의 **300개 요청**을 열거했다.
이름/eligibility를 제외한 생성 입력이 같은 경우 첫 입력만 남겨 **93개 중복**을 제외했다.
전체 제외 config·target U·대표 ID·제외 사유는 `pool.json`의 `duplicate_candidates`에 있다.
G/C/P 성능이나 label은 선택에 사용하지 않았다. 이름만 다른 ELF 사이 측정값을 재사용하지 않는다.

V1/V2 archive는 그대로 보존한다. V2 생성 결과가 기존 archive와 동치임을 회귀 검사했다.
V3의 ID는 새 namespace이고 V1 control panel은 합치지 않았다. 이전 후보의 123개 고유
구성과 새 구조의 84개가 포함된다. Cell/role/core/period 규칙은 V2에서 이어받았으며
이번 확장은 그 상관이나 모든 LLC 고부하 coverage 공백을 해결한 것이 아니다.

| Split 초안 | 계보 | Tasksets |
|---|---:|---:|
| Train | 3 | 125 |
| Validation | 1 | 41 |
| Test | 1 | 41 |

이는 deterministic splitter의 **초안**이다. 계보 5개도 독립성·학습 충분성·평가 다양성의
증명이 아니며, validation/test 각각 1계보 제한이 남아 있다. `split_frozen=false`,
`dataset_ready=false`, `sufficiency_status=not_assessed`를 유지한다.

- 단일 policy 기본 예산: 독립 U **21,680회** + G/C/P **6,210회** = **27,890회**.
- θ mapping·추가 policy/α·build·analysis·진단 비용은 별도. 실제 수집 0회.
- 최대 48 jobs / 64 slots / padding 포함 배열 **4,317,184 bytes**.
- 추정 총 U 0.256535~1.499052. 기존 ns/load×2 가정을 이어받았으며 실측 U/WCET가 아니다.
- 남은 순서: 추가 구조 coverage·부하/비용·충분성 기준 → 입력/split 확정 →
  validation θ/policy 동결 → 최종 U·공통 G/C/P 적격성·label → RF.

## 검증·재현

새 4개 역할의 width2/8·2 blocks·2 sweeps인 **8개 fixture × G/C/P = 24개 linked streams**가
별도 array-role reference와 일치했다. Architecture당 **1,920 accesses**다. Width2는
수작업 literal trace를 사용한다. 검증 fixture는 후보 membership에 넣지 않는다.
이는 큰 후보 207개 전체의 build/runtime 또는 hardware cache 검증이 아니다.
기존 V2 여섯 역할의 36개 fixture streams는 V2 archive에 보존한다.
전체 repository 검증은 **506 passed in 61.89s**다. Finalize는 호출하지 않았다.

| 파일 | 내용 |
|---|---|
| input-pool.tar.gz | 207 configs, registry/split 초안, 93개 중복, 구현·출처 계약·manifest |
| recipe-correctness.tar.gz | 작은 fixture 8개, reference, G/C/P ELF·APE·분석·manifest |
| summary.json | 후보·split·부하·자원·예산 |
| audit.json | 고유 입력·cell별 추정U·역할/core/period 결합 감사 |
| revalidation.json | 과거 621 plans·중복 관계·24 streams 재검사 결과 |
| verification.txt | 전체 repository 검증 로그 |
| manifest.json | 위 파일 hash |

구 후보 생성·재검증 스크립트는 정리했다. 이 디렉터리는 보존된 입력과 과거 검증
결과의 기록이며, 현재 저장소에서 구 후보를 다시 생성하는 실행 경로는 아니다.
