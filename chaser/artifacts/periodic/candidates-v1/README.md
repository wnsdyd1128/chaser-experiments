# Periodic 본실험 입력 후보 v1

2026-09-21. **입력 taskset 240개, 후보 계보 family 9개이며, runtime 실측과 최종 label은
아직 없다.** 이 artifact는 잠정 후보 집합과 split 초안을 보존한다. 실행 순서 4의
완료나 최종 학습 데이터셋 확보를 뜻하지 않는다.

## 후보 구성과 계보

구성은 **접근 구조 10종 × task 수 4종(4/8/12/16) × 메모리 구성 3종(layout/L1/LLC)
× 목표 총 U 2종(0.5/1.5) = 240개 taskset**이다. 접근 구조마다 24개 taskset이 있다.
모든 task는 전용 배열을 사용하고 load만 수행한다. Periodic v2 측정 계약과
11-feature 계약을 유지한다.

**한 taskset 안의 모든 task는 같은 접근 구조를 사용한다.** Task별로 배열 크기,
stride, period가 달라질 수 있지만, 서로 다른 접근 구조를 섞은 후보는 현재 없다.

| 접근 구조 | 접근·재사용 순서 |
|---|---|
| `tile-reuse` | 배열을 4개 구간으로 나누고, 각 구간을 두 번 읽은 뒤 다음 구간으로 이동 |
| `overlap` | 배열의 1/4 크기인 window 7개를 절반씩 겹치게 이동하며 읽음 |
| `lane-scan` | 인덱스를 3으로 나눈 나머지가 같은 원소들을 모아 차례로 읽음 |
| `forward-reverse` | 배열 전체를 정방향으로 읽은 뒤 역방향으로 읽음 |
| `mirrored` | 배열의 양 끝을 번갈아 읽으며 중앙으로 이동 |
| `hub-spoke` | 새로운 원소를 읽을 때마다 원소 0을 다시 읽음 |
| `tile-reverse` | 4개 구간 각각에서 정방향 순회 후 역방향 순회 |
| `hot-per-tile` | 첫 구간을 두 번 읽은 뒤 서로 다른 나머지 구간 하나를 읽음 |
| `region-cycle` | 배열의 세 구간을 A B A C B C 순서로 읽음 |
| `coarse-fine` | 매 4번째 원소를 먼저 읽은 뒤 배열 전체를 읽음 |

크기·stride·period 등의 숫자 변형은 같은 계보로 묶는다. `forward-reverse`와
`tile-reverse`도 보수적으로 같은 `directional-scan` 계보로 묶으므로, 접근 구조
10종이 family 10개를 뜻하지 않는다. 같은 생성 원형(recipe)이나 base task를 공유하면
전이적으로 연결된 전체를 한 family로 묶으며, task/family 이름 변경으로 분리하지 않는다.

Registry에는 기존 개발 probe 11개도 보존하되, 이들이 연결된 개발 family는 primary
후보에서 제외한다. `cyclic`·`hot-cold`·`phase`는 recipe 이름을 바꿔도 개발 계보로
인식한다. 이후 base task를 재사용할 때도 registry에 관계를 기록해야 한다.

이 family들은 합성 생성 원형의 집합이며, 독립적으로 수집한 실제 application들이 아니다.
분리는 명시된 구조별 계보 규칙에 따른 것이며 통계적 독립성을 자동으로 증명한 것은 아니다.

| Split 초안 | Family 수 | Taskset 수 |
|---|---:|---:|
| Train | 6 | 144 |
| Validation | 2 | 72 |
| Test | 1 | 24 |

기존 약 70/20/10 family 분할기에 seed 20260921을 한 번 적용했다.
**Test가 1개 family뿐이라는 점은 한계이며, 데이터 충분성의 근거가 아니다.** 후보 집합,
예산, 충분성 기준이 미확정이므로 split도 초안이다. 이 artifact에서는 θ 선택,
RF 학습 또는 평가에 사용하지 않는다.

## 데이터셋 구성 평가와 보강 과제

**현재 후보는 규칙적인 비교를 시작할 기반은 갖췄지만, 다양한 상황에서 RF를 학습·평가할
본실험 데이터셋으로 충분하다고 확정하지 않는다.** 이 평가는 데이터셋 구성에 관한 것이며
RF 모델의 복잡도나 feature 변경에 관한 결론이 아니다.

Task 수 4/8/12/16, layout·L1·LLC 메모리 조건, 접근 순서·재사용 구조 10종을 비교할 수 있고,
계보 변형과 개발 노출을 관리한다는 점은 장점이다. 보강이 필요한 부분은 다음과 같다.

| 항목 | 현재 한계와 보강 방향 |
|---|---|
| Task 조합 | Taskset 내부가 단일 접근 구조다. 서로 다른 접근 구조·역할을 가진 task의 혼합을 보강해야 한다. |
| 부하 | 목표 총 U가 0.5/1.5뿐이고 추정값과 차이가 있다. 부하 구간을 보강하고 목표·추정·실측 coverage를 구분해야 한다. |
| Period | 비율이 1:2로 고정되어 있다. 실행 빈도의 조합을 다양화하되 horizon과 job/출력 예산을 함께 관리해야 한다. |
| 메모리 조합 | LLC 초과 task가 항상 하나다. 큰 working set의 수·비율과 작은 task의 조합을 자원 한도 안에서 보강해야 한다. |
| 평가 범위 | Test가 1개 family다. 여러 구조·역할의 미지 workload를 평가할 family 다양성이 필요하다. |

가장 먼저 **이질적인 task 조합과 평가 family 다양성을 함께 설계**한다. 기존 task를
섞으면 공유 계보로 인해 여러 family가 하나로 연결될 수 있으므로, 혼합 후보 수 증가를
독립 family 증가로 세지 않는다. 새 혼합 비율·부하/period 범위·최종 규모는 아직 미정이다.

보강안은 새 candidate version/output으로 구현한다. 이 artifact의 240개 입력, registry,
split 초안은 당시 상태로 보존한다. 자세한 설계·검증 순서는
[workload 설계 §4.2](../../../system-prompt-extraction/plan/WORKLOAD-FAMILY-DESIGN.md#42-candidates-v1-구성-평가와-보강-방향)에
기록했다. 현재 보강안은 문서화 단계이며 구현 또는 충분성 검증을 완료한 것이 아니다.

## Task 접근 패턴의 C 스타일 의사코드

아래 각 패턴의 코드는 **한 task가 한 sweep에서 수행하는 접근 순서**를 나타낸다.
구현 정본은 [periodic_structures.py](../../../chaser/periodic_structures.py)다.

- `D`: 서로 다른 접근 위치 수. 현재 새 구조는 모두 24 이상의 24 배수만 허용한다.
- `stride`: 접근 위치 사이의 바이트 간격. 실제 byte 배열의 할당 크기는 `D * stride`다.
- `READ(i)`: 해당 task의 전용 배열에서 `data[i * stride]` 한 byte를 읽어 checksum에
  더한다. 배열에 쓰거나 다른 task의 데이터에 접근하는 동작은 없다.
- `B = D / 4`: tile 또는 window 하나에 포함되는 접근 위치 수.
- `q`: 한 job의 sweep 반복 횟수. 아래 코드를 `q`번 반복하면 한 job이다.

공통 job 구조는 다음과 같다. `pattern_one_sweep()` 자리에 아래 패턴 하나가 들어간다.

```c
uint32_t sum = 0;
for (int s = 0; s < q; ++s) {
    pattern_one_sweep();  // READ(i)는 sum += data[i * stride]를 뜻함
}
return sum;
```

배열은 실행 준비 시 초기화하며, sweep이나 job 사이에 배열·cache를 초기화하지 않는다.
의사코드의 `D`, `B`, `stride`, `q`는 실제 생성 C에서 고정 상수로 반영된다.

### `tile-reuse`: 구간 안에서 반복 재사용

배열을 겹치지 않는 4개 tile로 나눈다. 각 tile을 두 번 연속 읽고 다음 tile로 이동한다.
한 sweep의 load 수는 `2D`다.

```c
for (int b = 0; b < 4; ++b) {
    for (int r = 0; r < 2; ++r) {
        for (int i = 0; i < B; ++i) {
            READ(b * B + i);
        }
    }
}
```

### `overlap`: 겹치는 window 순회

길이 `B`인 window를 `B / 2`씩 이동한다. 이웃 window가 절반씩 겹치므로 일부 위치를
다시 읽는다. 7개 window가 배열 전체를 덮으며, 한 sweep의 load 수는 `7D / 4`다.

```c
for (int w = 0; w < 7; ++w) {
    for (int i = 0; i < B; ++i) {
        READ(w * (B / 2) + i);
    }
}
```

### `lane-scan`: 나머지별로 분리한 순회

`0, 3, 6, ...`을 끝까지 읽은 뒤 `1, 4, 7, ...`, 마지막으로 `2, 5, 8, ...`을 읽는다.
모든 위치를 한 번씩 읽지만, 연속 순회와 순서가 다르다. 한 sweep의 load 수는 `D`다.

```c
for (int lane = 0; lane < 3; ++lane) {
    for (int i = 0; i < D / 3; ++i) {
        READ(3 * i + lane);
    }
}
```

### `forward-reverse`: 전체 정방향·역방향 순회

배열 전체를 정방향으로 읽은 직후 역방향으로 읽는다. 정방향 순회의 끝부분이 먼저
재사용된다. 한 sweep의 load 수는 `2D`다.

```c
for (int i = 0; i < D; ++i) {
    READ(i);
}
for (int i = 0; i < D; ++i) {
    READ(D - 1 - i);
}
```

### `mirrored`: 양 끝 교대 접근

`0, D-1, 1, D-2, ...` 순서로 양 끝에서 중앙을 향해 읽는다. 한 sweep에서는 모든 위치를
한 번씩 읽으며 load 수는 `D`다.

```c
for (int i = 0; i < D / 2; ++i) {
    READ(i);
    READ(D - 1 - i);
}
```

### `hub-spoke`: 한 위치와 순차 접근의 교대

원소 0을 반복해서 읽고, 그 사이에 원소 1부터 끝까지 차례로 읽는다.
접근 순서는 `0, 1, 0, 2, 0, 3, ...`이며, 한 sweep의 load 수는 `2(D-1)`이다.

```c
for (int i = 0; i < D - 1; ++i) {
    READ(0);
    READ(i + 1);
}
```

### `tile-reverse`: 구간별 정방향·역방향 순회

배열 전체가 아니라 각 tile 안에서 정방향·역방향 순회를 마친 뒤 다음 tile로 이동한다.
한 sweep의 load 수는 `2D`다. 계보 감사에서는 `forward-reverse`와 같은 family로 묶는다.

```c
for (int b = 0; b < 4; ++b) {
    for (int i = 0; i < B; ++i) {
        READ(b * B + i);
    }
    for (int i = 0; i < B; ++i) {
        READ(b * B + B - 1 - i);
    }
}
```

### `hot-per-tile`: 반복 구간과 서로 다른 구간의 교대

첫 tile을 hot 구간으로 삼는다. 첫 tile을 두 번 읽고 두 번째 tile을 읽은 뒤,
첫 tile을 두 번 읽고 세 번째 tile을 읽는 식으로 진행한다. 한 sweep의 load 수는
`9D / 4`다. 여기서 hot/cold는 접근 반복 구조를 뜻하며 실제 cache hit/miss 판정이 아니다.

```c
for (int b = 0; b < 3; ++b) {
    for (int r = 0; r < 2; ++r) {
        for (int i = 0; i < B; ++i) {
            READ(i);
        }
    }
    for (int i = 0; i < B; ++i) {
        READ((b + 1) * B + i);
    }
}
```

### `region-cycle`: 세 구간의 교차 재사용

배열을 같은 크기의 A·B·C 세 구간으로 나누고 `A B A C B C` 순서로 읽는다.
각 구간을 두 번씩 읽지만 재사용 사이에 다른 구간이 들어간다. 한 sweep의 load 수는
`2D`다. 아래 `D / 3`은 이 패턴의 구간 크기이며 공통 tile 크기 `B = D / 4`와 다르다.

```c
for (int i = 0; i < D / 3; ++i) READ(i);               // A
for (int i = 0; i < D / 3; ++i) READ(D / 3 + i);       // B
for (int i = 0; i < D / 3; ++i) READ(i);               // A
for (int i = 0; i < D / 3; ++i) READ(2 * (D / 3) + i); // C
for (int i = 0; i < D / 3; ++i) READ(D / 3 + i);       // B
for (int i = 0; i < D / 3; ++i) READ(2 * (D / 3) + i); // C
```

### `coarse-fine`: 성긴 순회 후 전체 순회

먼저 인덱스 `0, 4, 8, ...`만 읽은 뒤 모든 위치를 연속해서 읽는다. 두 번째 순회는
첫 번째 순회의 위치를 포함한다. 한 sweep의 load 수는 `5D / 4`다.

```c
for (int i = 0; i < D / 4; ++i) {
    READ(4 * i);
}
for (int i = 0; i < D; ++i) {
    READ(i);
}
```

## 잠정 부하·비용 규칙

| 메모리 구성 | Task별 설정 |
|---|---|
| Layout | 모두 D=96, stride는 task 순서대로 1/32/4096 반복 |
| L1 | D=504/528 교대, stride=32 |
| LLC | 첫 task는 D=65544, 나머지는 D=96, 모두 stride=32 |

보조 task도 같은 후보의 접근 구조를 사용한다. 기존 cyclic 개발 task를 재사용해
후보 family가 개발 계보와 연결되는 일을 피한다.

- Sweep 수는 `max(2, ceil(10240 / loads_per_sweep))`다. 정확성 검증에 사용하는
  작은 고정 입력은 이 후보 집합의 입력과 별도다.
- CPU 추정값은 개발 측정에서 가장 큰 평균 ns/load의 두 배에 새 task의 load 수를
  곱한 값이다. **새 구조로의 적용 타당성이 검증되지 않은 추정 방식**이며,
  새 실측값·WCET 상한·스케줄 가능성 보장이 아니다.
- Task별 U 상한 0.25와 총 U 상한 2.0은 잠정값이다. 공통 정수 base period를 정해
  추정 task별 상한과 목표 총 U(0.5 또는 1.5)를 넘지 않도록 한다. Task별 period는
  base와 2×base를 교대로 사용하며 공통 실행 구간은 4×base다.
  Task별 상한과 tick 단위 올림 때문에 추정 총 U가 목표보다 작아질 수 있다.
  현재 후보의 추정 총 U 범위는 약 0.2671~1.4983이다.
- Task별 job 수는 4 또는 2다. 한 실행의 논리 job 수는 최대 48개이며, 정적으로
  할당하는 record slot은 최대 64개다. 알려진 4096-job 출력 한도를 실용적인 수집
  예산으로 사용하지 않는다.
- 각 새 후보는 최종 P ELF에서 task별 독립 U 측정을 10회씩 수행해야 한다.
  추정 CPU/U 값을 실측 U feature에 넣으면 안 된다.
- 단일 policy의 기본 실행 수는 **독립 U 24,000회 + timing 7,200회 = 31,200회**다.
  θ mapping 탐색, 추가 policy/α, build·analysis·진단 비용은 포함하지 않는다.
  후보 집합 전체의 실행 시간이나 저장 공간 상한을 확보했다고 주장하지 않는다.

모든 입력 구성은 최종 준비 전까지 training/test 부적격 상태이며, 보정된 allocator 대신
명시적인 core 순서에 따른 임시 배치를 사용한다. Registry의 task 식별 정보에는
workload/configuration hash가 포함되지만 최종 snapshot hash는 아직 없다.
이후 독립 U 특성화나 G/C/P 적격 판정에서 탈락하더라도 원래 membership과 실패 raw
근거를 보존해야 한다.

## 검증과 보존 파일

| 파일 | 내용 |
|---|---|
| `input-pool.tar.gz` | 240개 입력 구성, 전체 pool·registry, split 초안, 요약, 구현 사본과 hash manifest |
| `structure-correctness.tar.gz` | 별도의 작은 검증 입력, SPARC G/C/P ELF, APE·분석·event, 고정 reference 접근열과 비교 결과 |
| `summary.json` | 후보 수·split 초안·기본 측정 예산 요약 |
| `verification.txt` | 전체 repository 검증 실행 기록 |
| `revalidation.json` | 새 디렉터리에 압축 해제한 뒤 해시·입력 plan·접근열을 재검사한 결과 |
| `manifest.json` | 나머지 artifact 파일의 무결성 해시 |

**30개 구조×ELF 접근열이 독립적으로 작성한 고정 reference 접근열과 일치했다.**
검증 입력은 정확성 확인용이며 simulator timing·U·label 수집이나 성능 튜닝을 수행하지
않았다. 여러 구조를 합친 검증용 task 목록은 본실험 생성 원형이나 split 구성원이 아니다.
기존 feasibility 및 pilot archive는 변경하지 않았다.

새 디렉터리에 후보 입력을 재생성하고 검증하는 명령은 다음과 같다.

```sh
python3 -m tools.rtems_periodic_pool --output .cache/periodic-candidates-new
python3 -m pytest -q tests/test_periodic_structures.py tests/test_periodic_pool.py
CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify
```

Archive는 새 디렉터리에 압축 해제한다. `tools.rtems_smoke.check_inputs`에 압축 해제된
입력 manifest와 정확성 검증 snapshot/analysis manifest를 각각 전달하면 파일 해시를
재검사할 수 있다. 고정 접근열 비교는
`test_new_structures_match_literal_traces_in_all_final_elfs`로 재현한다.

남은 작업은 생성 부하 상한과 CPU 추정 적용 타당성 확인, 제한된 held-out family 범위
검토, 초기·확장 예산과 충분성 기준 결정, 후보 집합의 build·runtime·저장 비용 확인이다.
그 뒤 최종 membership/split을 동결하고 validation θ 보정과 최종 label 수집을 진행한다.
