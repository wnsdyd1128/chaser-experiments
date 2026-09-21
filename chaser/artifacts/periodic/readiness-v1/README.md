# Periodic 후보 구성·측정 준비 감사

2026-09-21. 입력 archive를 바꾸지 않고 V1/V2의 중복, 추정 부하 coverage와 비용을
감사했다. V2의 경계 구성 3개를 빌드했다. **Runtime·실측 U·label은 수집하지 않았고
최종 membership/split은 동결하지 않았다.**

## 구성·비용 결과

| Panel | 이름이 있는 후보 | 서로 다른 입력 | 중복 추가분 | 계보 | 원래 기본 실행 수 | 중복 제거 시 기본 실행 수 |
|---|---:|---:|---:|---:|---:|---:|
| V1 대조군 | 240 | 200 | 40 | 9 | 31,200 | 26,000 |
| V2 출처 기반 혼합 | 180 | 123 | 57 | 3 | 23,400 | 16,530 |

입력 동치는 workload/task/family 이름과 eligibility metadata를 제외한 생성 입력으로
판정한다. Task 순서·pattern·width·stride·distinct·sweeps·core·period·horizon·policy는
유지한다. 서로 다른 ELF의 CPU 시간이나 label을 복사해 사용할 수 있다는 뜻이 아니다.
목표 U는 생성 요청 tag이며 실행 입력 자체가 아니다. V2 중복은 3개씩 24그룹,
2개씩 9그룹이다. 나머지 90개는 단독 입력이다.

중복 제거 비용은 **새 pool version으로 membership을 선택할 경우의 정적 계산**이다.
이 감사는 원본에서 57개를 삭제하지 않는다. V2 고유 입력의 독립 U는 12,840회,
단일 policy G/C/P는 3,690회다. θ 탐색·다른 policy/α·build·analysis·진단은 별도다.
Runtime 시간과 저장 비용은 아직 새 원형에서 측정하지 않아 날짜로 환산하지 않는다.

| V2 cell | 후보 수 | 고유 입력 수 | 추정 총 U 범위 |
|---|---:|---:|---:|
| layout-half | 36 | 33 | 0.478895~1.496743 |
| l1-half | 36 | 33 | 0.484069~1.499051 |
| l1-skew | 36 | 33 | 0.485300~1.479949 |
| llc-one | 36 | 12 | 0.256535~0.356440 |
| llc-two | 36 | 12 | 0.381379~0.473090 |

LLC cell은 각 recipe/task 수에서 세 목표 U 모두 같은 입력이다. Task별 u_max=0.25가
period를 지배해 목표 U를 높여도 달라지지 않는다. 이는 높은 부하 LLC coverage의
부재이며, 추정치도 최종 실측 U를 대신하지 않는다. Layout/L1의 2중 중복은 4-task
구성의 목표 U=1/1.5에서 나타난다. V1의 40개 중복 추가분도 LLC 구성이다.

Role/core/period 결합 빈도는 `v2-audit.json`에 있다. 일반 1:1 구성의 A/B는
각각 짝수/홀수 core와 결합하고, l1-skew의 B는 core3/period ratio2에 놓인다.
따라서 역할별 인과 효과나 자유로운 task 혼합을 대표하는 설계로 해석하지 않는다.

## 계보 판단과 다음 gate

Read-only 코드 검토에서 완전한 V1/V2 base-task 공유는 확인하지 못했다. 다음 관계는
부분 접근 특성 공유다: overlap↔window 입력, tile-reuse↔paired-pass의 초기 반복 pass,
lane-scan↔row-column의 column phase, mirrored↔row-column-mirrored의 대칭 쌍.
V2는 계수 결합·추가 결합 pass·block별 row/column 재방문을 포함한다.
정확한 계약은 [RECIPES.md](../../../rtems/periodic/RECIPES.md)를 따른다.

현재 registry 규칙의 합집합은 12개 연결 성분이지만 통계적 독립성 증명이 아니다.
V1은 기존 부분 대조군이고 V2만 출처 기반 혼합 원형이다. 이 차이를 없애고
V2의 3-family 부족을 해결했다고 주장하지 않는다. 보존 split 초안은 V1 6/2/1,
V2 1/1/1 family로 유지된다. 완전한 base-task를 섞는 새 recipe는 전이 병합해야 한다.

권장 후속은 TACLeBench 조사에서 아직 반영하지 않은 구조를 근거로 계보를 보강한 뒤,
중복 제거와 역할/period coverage를 새 후보 version에서 확정하는 것이다. 임의 숫자·이름
변형으로 family를 늘리지 않는다. 현재 3계보를 사용하려면 제한 실험으로 범위를 명시해야 한다.
PolyBench는 외부 평가용으로 보존한다.

입력 구성 다음에는 개발용 계보에서 부하 규칙·runtime/analysis 비용을 확인하고,
초기/확장 pool·충분성 기준·membership/split을 동결한다. Held-out 후보를 사전 실행해
성능에 맞춰 수정하지 않는다. Validation θ/policy 동결 → 최종 U/공통 적격성/label → RF
순서를 유지한다. 현 상태에서 PLAN 4 실측 θ 완료나 split 동결을 선언할 수 없다.

## 실제 빌드와 검증

선택 규칙은 각 V2 계보에서 task16·llc-two·목표 U0.5다. 중복 target 태그 중 첫 값을
사용했으며 성능 결과에 따른 선택이 아니다. 후보 ID는 0057/0117/0177이다.

- 세 snapshot의 G/C/P **9 ELF 빌드·linked layout 검사 PASS**.
- 각 36 logical jobs, 64 record slots, padding 포함 배열 4,259,840~4,288,512 bytes.
- 준비 wall time은 각 약 0.61~0.64초, 전체 snapshot은 각각 약 15.3 MB.
  설치된 SDK와 현재 build 환경의 관측이며 cold build/전체 pool 비용 보장이 아니다.
- 180개 전체 build, 큰 후보의 분석 stream/runtime/적격성 검증은 하지 않았다.
- 새 감사 테스트 9개 PASS. 감사 단계 전체 **459 passed in 59.77s**를
  `verification.txt`에 보존한다. 이후 계보 확장 검증은 candidates-v3의506개 결과와 구분한다.

`build-snapshots.tar.gz`는 소스·config·빌드 로그·G/C/P ELF·manifest를 포함한다.
`v1-audit.json`/`v2-audit.json`은 원본 pool/manifest와 감사 구현 hash를 기록한다.
원본 입력은 기존 candidates-v1/v2 archive를 참조한다.

```sh
PYTHONPATH=. python3 artifacts/periodic/readiness-v1/revalidate.py \
  --output /tmp/chaser-readiness-replay-new
```

`implementation/`에 감사 당시 구현도 보존한다. 새 디렉터리에 원본 pool과 build archive를 추출해 입력 hash·감사 결과·선택 membership·
9개 ELF symbol layout을 재검사한다. 현재 SPARC nm가 필요하다. 이는 새 compile이나
runtime 재실행이 아니다. 보존 구현 hash와 현재 구현의 감사 결과를 각각 검사한다.
동작 재검증이 실패하면 보존본을 덮어쓰지 않고 원인을 확인한다.
