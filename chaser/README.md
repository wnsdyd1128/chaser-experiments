<a id="chaser-rtems--gr740-baseline-test"></a>

# CHASER RTEMS / GR740 기준 실험

`rtems/baseline/`에는 검증용으로 작성한 C 워크로드와 RTEMS 초기화 태스크가 있다.
같은 `workload.c`를 서로 분리된 SPARC RTEMS 6 / GR740 실행 파일 3개와
APE 추출용 LLVM IR로 컴파일한다. 모든 RD 분석은 **yarda_cpp**가 수행한다.
Python은 APE 레코드 선택, 스칼라·특성 계산, 테스트를 담당하며 RD/CSRD는 계산하지 않는다.

Python 코드는 `chaser/` 아래에 책임별로 배치한다. `locality/`는 캐시 분석과 표현,
`dataset/`은 구성원과 라벨, `policy/`는 할당과 RF, `periodic/`은 RTEMS 주기적 계측,
`s1/`은 S1 평가 시나리오를 담당한다. 최상위에는 패키지 메타데이터만 둔다.

<a id="cases"></a>

## 실험 사례

각 작업은 volatile 바이트 8개의 값을 65,537번 순회하며 증가시킨다.
최종 바이트 값이 0이 아닌 1이므로, 실행 검사는 접근하지 않은 0 초기화 배열을 거부할 수 있다.

| 사례 | 접근 간격 | 32바이트 라인 수 | GR740 L1 매핑 |
|---|---:|---:|---|
| packed | 1바이트 | 1 | 라인 하나 |
| spread | 32바이트 | 8 | 서로 다른 세트 8개 |
| conflict | 4096바이트 | 8 | 세트 하나에 집중해 4웨이 용량 초과 |

세 사례 모두 원소 RDH는 `{0: 524296, 7: 524288}`, 재사용은 1,048,584회,
최초 접근은 8회이며 CA는 `131073 / 589825`(약 0.222224)다.
CA는 최초 접근을 제외한다. packed의 라인 CA는 1이고 spread와 conflict는
라인 Global RD가 같다. 이는 Global RD 표현이 세트 매핑을 구분하지 못함을 보여준다.
캐시 미스를 측정하거나 실행 시간 차이를 증명하는 결과는 아니다.

각 ELF는 선택된 작업 하나를 실행하고 경과 시간을 나노초로 보고하며 해당 작업의
바이트만 검사한다. 선택하지 않은 작업과 배열은 링커가 제거한다.
이는 워크로드 통합 테스트이며 SMP 스케줄링 비교가 아니다.
`cache.yaml`은 GR740 캐시 형상과 YARDA가 지원하는 LRU·쓰기 할당 정책을 제공하며,
GR740 쓰기 정책을 정확히 재현하는 모델은 아니다.

<a id="verify"></a>

## 검증

```sh
sh scripts/verify
```

기존 RTEMS 툴체인, LLVM 14, CMake, YARDA 의존성, pytest와
scikit-learn이 필요하다. scikit-learn은 기존 CAAS RF 프레임워크도 사용한다.
소스 작업 트리 위치를 바꾸려면 `YARDA_DIR`를 지정한다. 스크립트는
`rtems/baseline/build/yarda`에 C++ 분석기를 새로 빌드하고 RTEMS ELF 3개를 빌드한 뒤,
C에서 APE를 추출하고 원소·캐시 라인 RD를 분석하며 검사를 실행한다.
APE 프런트엔드 플러그인의 기본 경로는
`rtems/baseline/build/yarda/libMemoryAccessPatterns.so`다.

루프 전개 한도 수정 `8b12a00`을 포함한 YARDA `6059896`으로 검증했다.
SPARC ELF 검사와 각 ELF가 선택된 작업·검사기만 포함하는지 확인하는 검사를 포함해
**pytest 테스트 12개가 통과**했다. 워크로드가 기본 누적 한도를 초과하므로
한도를 명시적으로 2,000,000으로 지정했다.
기존 YARDA `build-release/backend/yarda_cpp`는 오래된 빌드여서 재빌드가 필요했다.

YARDA 출력은 `exports/element.rdh.json`과 `exports/line.rdh.json`에 저장한다.
생성된 ELF·APE·빌드 로그는 `rtems/baseline/build/`에 둔다.
작업용 출력은 다시 생성할 수 있으며, 검증된 기준 스냅샷은
`artifacts/baseline/rtems-v1/`에 별도로 보존한다.

<a id="separate-builds-and-runs"></a>

## 개별 빌드와 실행

```sh
make -C rtems/baseline all
# 사례 하나만 빌드하려면:
make -C rtems/baseline build/packed.exe
```

출력은 `build/packed.exe`, `build/spread.exe`, `build/conflict.exe`다.
아래 명령은 각각 별도의 시뮬레이터 프로세스를 시작한다.

```sh
cd rtems/baseline
script -q -e -c 'make run-packed' build/laysim-packed.log
script -q -e -c 'make run-spread' build/laysim-spread.log
script -q -e -c 'make run-conflict' build/laysim-conflict.log
```

성공하려면 선택된 사례의 양수 경과 시간을 담은 `RESULT` 한 줄 뒤에
`CHASER PASS`가 있어야 한다. 분리된 각 실행 파일은 새 laysim 프로세스에서
RESULT 한 줄, CHASER PASS, RTEMS 종료를 기록하고 완료했다.
명시적 준비 실행이나 반복은 추가하지 않았다.
Init 태스크는 특정 코어에 고정하지 않으며 `-core0`은 ELF를 적재할 코어를 선택한다.

| 사례 | 독립 실행 경과 시간(ns) |
|---|---:|
| packed | 59,868,128 |
| spread | 59,869,992 |
| conflict | 89,546,204 |

이 단일 실행 시간은 실행 성공의 근거이며 통계적 성능 주장의 근거는 아니다.

`build/`의 이전 `baseline.exe`, `laysim-final.log`, `runtime-result.json`은
현재 방식으로 대체된 순차 통합 테스트를 기록한다. 과거 증거로 보존하며,
분리된 실행 파일의 결과가 아니다. 당시 관측 시간(packed 59,869,908ns,
spread 59,868,252ns, conflict 89,544,968ns)은 독립된 성능 비교가 아니다.
해당 실행은 참조 예제의 FPU 설정을 맞춘 뒤 통과했다.
실제 GR740 계측이나 캐시 미스 카운터는 수집하지 않았다.

<a id="frozen-baseline"></a>

## 고정된 기준 실험

`artifacts/baseline/rtems-v1/manifest.json`은 원소 CA, 재사용 횟수,
독립 실행 결과, YARDA 커밋, 도구 해시와 보존 파일별 SHA-256을 기록한다.
스냅샷에는 C 소스, Makefile, 캐시 YAML, APE, 원소·라인 RDH,
실행한 ELF 3개, 로그와 검증 코드를 포함한다. 재생성 후 원소·라인 RDH 해시는 일치했다.
같은 입력의 스냅샷 직렬화는 결정적이며 기존 스냅샷은 덮어쓸 수 없다.
재실행 시 실제 시간 측정값까지 바이트 단위로 같아야 하는 것은 아니다.

```sh
python3 tools/freeze_baseline.py --output artifacts/baseline/<new-version>
```

먼저 독립 시뮬레이터 명령 3개를 실행하고 `sh scripts/verify`를 실행한다.
새 스냅샷을 고정하려면 새 실행 로그와 저장된 검증 로그가 필요하다
(`sh scripts/verify > rtems/baseline/build/verify.log 2>&1`).
선택된 사례, PASS 표시와 종료를 모두 검사하며 시뮬레이터 종료 상태만으로 성공을 판정하지 않는다.
일반 검증 테스트는 고정 증거의 격리된 사본을 사용하므로 작업용 시뮬레이터 로그,
verify.log나 laysim 바이너리 설치를 요구하지 않는다. 보존 파일마다 manifest 해시도 검사한다.
빌드·분석 검사에는 여전히 툴체인, YARDA 소스, LLVM 프런트엔드 빌드 의존성이 필요하다.
이 기준 실험은 CHASER C 워크로드 3개를 다룬다. 과거 exp2 스냅샷 재현이나
연결된 ELF의 정확한 물리 주소 모델은 범위에 포함하지 않는다.

<a id="l1-csrd-and-clp-stage-2"></a>

## L1 CSRD와 CLP (2단계)

D1은 확정되었다. `CA_CSRD`는 L1 CSRD 히스토그램만 사용한다.
`chaser/locality/ca.py`는 Global RD와 L1 CSRD에 같은 CAAS 수식을 적용하고
최초 접근을 제외하며 재사용이 없으면 `None`을 반환한다. LLC는 이 스칼라에 합치지 않는다.

```sh
make -C rtems/baseline hierarchy
python3 -m tools.export_locality
```

hierarchy 대상은 생성된 APE v2에서 각 작업과 해당 객체를 선택한 뒤,
실제로 실행한 SPARC ELF와 캐시 YAML로 **yarda_cpp**를 실행한다.
Python은 JSON 레코드를 선택하고 최종 스칼라를 계산하며 RD를 계산하지 않는다.
각 입력은 독립적으로 비어 있는 캐시에서 시작하는 태스크 하나다.
연결된 ELF 주소와 코어 0의 캐시 형상을 사용한다. 측정 실행의 RTEMS 스케줄링,
코어 이동, 인터럽트 접근이나 물리 캐시 상태를 재구성하지 않는다.

출력은 `exports/packed.csrd.json`, `spread.csrd.json`, `conflict.csrd.json`이다.
`exports/locality.json`은 세 CA 표현과 CLP를 요약하고 원본 출력의 해시를 포함한다.
CLP 순서는 L1 적중, LLC 최초 적중, 전체 캐시 미스다.

| 사례 | 원소 CA | 라인 Global CA | L1 CSRD CA | L1 CSRD 히스토그램 |
|---|---:|---:|---:|---|
| packed | 0.22222354 | 1 | 1 | `{0: 1048591}` |
| spread | 0.22222354 | 0.22222354 | 1 | `{0: 1048584}` |
| conflict | 0.22222354 | 0.22222354 | 0.22222354 | `{0: 524296, 7: 524288}` |

conflict는 L1 적중 524,296회, LLC 최초 적중 524,288회, 전체 캐시 미스 8회다.
spread의 최초 접근에 따른 L1 미스는 8회, packed는 1회다. 이는 **모델 카운터**이며
실제 GR740 카운터 측정값이 아니다. 라인 Global RD 대조군은 spread와 conflict 사이의
세트 효과를 분리하며, 원소와 라인 비교에는 그룹화 효과도 포함된다.

`sh scripts/verify`의 테스트 12개가 통과했다. 기대 히스토그램, CA, CLP 보존,
전체 해석 여부와 입력 해시를 검사했다. 분석을 직접 반복했을 때 CSRD 출력은
바이트 단위로 같았고, 분석한 모든 ELF 해시는 고정된 실행 ELF 해시와 일치했다.
1단계 스냅샷은 변경하지 않았다.

<a id="stage-1-acceptance-and-downstream-feature-interface"></a>

## 1단계 수용 검증과 후속 특성 인터페이스

1단계 수용 검증은 검증용 CHASER 워크로드와 닫힌 형태로 계산한 RD/CA 기대값,
결정적 분석, 보존된 독립 실행 증거를 사용한다. 이는 원래 계획의 과거 CAAS 워크로드
재현 요구를 대체하며 exp2 재현을 주장하지 않는다. 고정된 rtems-v1 내용과 manifest는
변경하지 않았다. 이전에 무시하던 빌드 파일 9개는 한정된 무시 규칙 예외를 통해
Git 추적 대상이 되었으므로 커밋 시 해당 변경에 포함한다.

`chaser.locality.features.locality_scalar(kind, record, alpha=...)`는 `caas-ca`,
`ca-line`, `ca-csrd` 또는 미리 계산한 `cls`를 선택한다. 레코드 필드는
`exports/locality.json`의 `ca_caas_element`, `ca_global_line`, `ca_csrd_l1`을 사용한다.
CLS 레코드는 `cls: {"0.5": 0.75}`처럼 문자열 키의 맵도 포함한다.
`chaser.locality.cls`는 무조건부 최초 적중 비율과 바이트 단위 캐시 용량에서
`CLS = p_L1 + (K_L1 / K_LLC)^alpha * p_LLC`를 계산한다.
빈 프로파일은 `None`을 반환하며 선택기는 요청한 alpha 결과가 없으면 거부한다.

일반 지역성 출력에는 alpha 값 `0, 0.3, 0.5, 0.7, 1.0`을 포함한다.
분석을 다시 실행하지 않고 기존 분석기 출력에서 여러 alpha 값을 재계산하려면 다음을 사용한다.

```sh
python3 -m tools.run_cls_sweep --alpha 0,0.3,0.5,0.7,1.0
# 별도 출력 경로를 선택하려면:
python3 -m tools.run_cls_sweep --alpha 0,0.5,1 --output exports/cls-sweep.json
```

기본 출력은 `exports/locality.json`이며 CLS와 함께 CA, CLP, 분석 ID,
소스 해시와 모델링한 접근 횟수를 유지한다. 사례별 출처 정보에는 분석기 버전
(Git 리비전과 수정 여부 표시 포함), 캐시 설정을 포함한 입력 해시, 선택 경로,
용량·라인 크기·연관도를 포함한 캐시 계층을 보존한다. 용량은 분석에 사용한 계층에서
가져오므로 이후 설정 변경이 저장된 CLP의 의미를 바꾸지 않는다.
이 레코드는 `fit_rf(..., 'cls', seed=42, alpha=0.5)`와
`allocate(..., kind='cls', alpha=0.5, threshold=...)`에 직접 전달할 수 있다.
alpha마다 별도의 RF·스케일러 학습이 필요하다. 기본 설정은 alpha 0.5이며,
이 기능은 스칼라 생성만 구현한다. RF 민감도 계측이나 스케줄링 실험은 수행하지 않는다.

`build_features(records, kind, alpha=...)`를 호출하기 전에 태스크 ID로
각 레코드와 해당 태스크의 `utilization`을 결합한다. 결과는 `FEATURE_NAMES` 순서의
목록으로, 지역성 통계 5개(평균·모집단 표준편차·최솟값·최댓값·중앙값) 뒤에
이용률 통계 6개(같은 5개와 합계)가 온다. 기존 `ca_*` 이름은 표현이 바뀌어도 유지한다.
여기서는 스케일링하지 않는다. 빈 워크로드, 정의되지 않거나 유한하지 않은 스칼라·이용률,
음수 이용률, [0, 1] 범위 밖 지역성은 0으로 바꾸지 않고 거부한다.
데이터셋 구성 시 모든 변형에 공통으로 완전한 결과가 있는 워크로드 집합을 선택해야 한다.

2026-09-16 검증: 작업 트리와 제안 파일만 포함하고 작업용 빌드 디렉터리·시뮬레이터
로그는 없는 임시 체크아웃 모두에서 `sh scripts/verify`의 테스트 23개가 통과했다.
Makefile은 출처 검사를 위해 사례별 APE 입력을 보존한다. 새 시뮬레이터 계측은 수행하지 않았다.

<a id="rf-consumption-of-selected-features"></a>

## 선택한 특성을 RF에 연결하기

`chaser.policy.rf.fit_rf(cases, workloads, labels, kind, seed=...)`는 태스크 ID로
지역성 레코드와 이용률을 결합하고 기존 특성 11개를 만든 뒤 새 sklearn
RandomForestClassifier를 학습한다. CAAS 래퍼와 같은 구현·매개변수를 사용하며,
트리 100개, 깊이 제한 없음, 명시적 시드를 적용한다.
외부 프레임워크와 기존 저장 가중치는 불러오지 않는다.

각 워크로드는 `{task_id: utilization}` 맵이고 `cases`는 `locality.json`의 맵이다.
태스크 ID 누락, 이용률 누락·오류, 정의되지 않은 스칼라, 빈 워크로드,
유효하지 않거나 일치하지 않는 라벨은 거부한다.
라벨은 `0=Global`, `1=Clustered`, `2=Partitioned`다.

반환된 모델은 사용한 표현과 지정된 CLS alpha를 보존한다.
MinMaxScaler는 학습 특성으로 학습하고 예측 시 재사용한다. 표현마다 같은 학습
워크로드·라벨·시드로 별도 모델을 학습한다. 호출자가 계열 단위 분할과 공통으로
완전한 결과가 있는 워크로드 집합을 제공한다. 이 API는 연구 데이터셋을 만들거나
정확도를 측정하지 않는다.

아래는 **합성 라벨과 이용률만 사용하는** 실행 가능한 연결 예제다.

```python
import json
from pathlib import Path
from chaser.policy.rf import LABEL_NAMES, fit_rf

cases = json.loads(Path('exports/locality.json').read_text())['cases']
workloads = [{'packed': 0.1}, {'spread': 0.5}, {'conflict': 0.9}]
labels = [0, 1, 2]  # 테스트용 입력이며 실측한 최적 스케줄링 라벨이 아니다.
for kind in ('caas-ca', 'ca-csrd'):
    model = fit_rf(cases, workloads, labels, kind, seed=42)
    predictions = model.predict(cases, workloads)
    print(kind, [LABEL_NAMES[label] for label in predictions])
```

실험에서는 예제 입력을 계측 파이프라인의 학습 데이터·라벨로 교체한 뒤
학습에 쓰지 않은 워크로드를 예측한다. 여기까지는 RF 입력 연결을 완성하며
S2 평가는 별도 작업이다.

<a id="offline-allocator-connection-stage-2"></a>

## 오프라인 할당기 연결 (2단계)

`chaser.policy.allocator.allocate`는 RF 인터페이스와 같은 지역성 사례와
태스크 ID→U 맵을 받아 `Placement(mapping, residual, infeasible)`을 반환한다.
자료형과 어노테이션은 Python 3.10을 대상으로 한다.

```python
from chaser.policy.allocator import CoreGroups, allocate

# 명시적 예제 설정이며 실험으로 보정한 기본값이 아니다.
cores = CoreGroups(isolated=(0,), non_isolated=(1, 2, 3))
placement = allocate(cases, {'spread': 0.6, 'conflict': 0.3}, cores,
                     kind='ca-csrd', threshold=0.5)
```

정책은 프로젝트 계획에 옮긴 알고리즘 1을 따른다. U 내림차순으로 처리하고,
스칼라가 임곗값 이하이면 부하가 가장 낮은 격리 Ω 코어에,
임곗값보다 크면 비격리 NΩ 코어에 worst-fit 방식으로 할당한다.
같은 정책에 `caas-ca`나 `ca-csrd`를 사용하며 선택기는 `ca-line`과 명시적으로
선택한 사전 계산 CLS도 받는다. 코어 그룹 분할과 유한한 임곗값은 필수 입력이다.
실험용 분할·임곗값을 암묵적으로 선택하지 않으며 보정 후보는 [0, 1]에 둔다.

논문의 부분적 정책은 명시적 규칙으로 보완한다. 두 분기 모두 코어당 용량은 1이고,
그룹 사이에 넘겨 할당하지 않으며 실패한 태스크를 기록한 뒤 나머지를 계속 처리한다.
U > 1은 유효하지 않은 계측값이 아니라 할당 불가능한 경우다.
태스크 동률은 태스크 ID 오름차순, 코어 동률은 코어 ID 오름차순으로 처리한다.
빈 그룹은 허용하지만 태스크를 받지 못한다. 그룹은 서로 겹치지 않고 고유한 음이 아닌
코어 ID를 가져야 하며 전체에 코어가 하나 이상 있어야 한다. 빈 워크로드는 사용하지 않은
코어를 반환한다. 누락되거나 정의되지 않은 입력은 거부한다.
잔여 용량은 할당된 U의 합으로 계산한다.

이는 탐욕적 배치 정책이며 전역 최적 할당 가능성 해법이나 스케줄 가능성 증명이 아니다.
2단계 오프라인 RF·할당기 입력 인터페이스를 완성한다. RTEMS 코어 친화도 적용,
토폴로지별 스케줄링, 실측 라벨, 실측 임곗값 보정, S2/S3 성능 평가는 후속 작업이다.

<a id="offline-threshold-calibration-stage-4"></a>

## 오프라인 임곗값 보정 (4단계)

`chaser.periodic.calibration`은 보정 분할에서 P 전용 매핑 계측을 계획하고,
요청한 모든 매핑의 결과가 나온 뒤 임곗값을 선택한다. 후보 집합은 정확히 0, 1과
관측된 스칼라 값이며 할당은 `scalar <= threshold`를 사용한다.
CAAS-CA, CA-CSRD와 CLS alpha 5개에 같은 보정 워크로드를 사용한다.
인프라 오류가 있으면 선택을 중단한다. 후보 중 할당·실행 실패가 가장 적은 것을 고르고,
동률이면 공통 성공 워크로드의 P 중앙값 TAT 평균이 작은 것, 다시 동률이면 작은 임곗값을
선택한다. 공통 성공 집합이 비어 있으면 미해결로 남긴다.
`classify_p_batch()`는 변경되지 않은 원시 배치를 검증한 뒤 결과를 반환한다.

현재 계측 계약으로 실험용 임곗값을 선택한 결과는 없다.
전체 P 수집·고정 CLI는 아직 구현해야 하며,
[재구축 계획](system-prompt-extraction/plan/DATASET-REBUILD-PLAN.md)을 참고한다.

<a id="plan-5-analyzer-and-dataset-bridge"></a>

## PLAN 5: 분석기와 데이터셋 연결

`chaser.locality.analyzer.analyze_task`는 준비된 단일 함수 APE, 대응하는 ELF,
캐시 YAML, 소스 파일, C++ 분석기 실행 파일, 새 출력 디렉터리와 명시적 분석 한도를 받는다.
C++ 경로 **3개**, 즉 원소 Global RD, 캐시 라인 Global RD 대조군, 계층 CSRD를 실행한다.
Global CA는 블록 간 재사용을 유지하도록 프로그램 히스토그램을 사용한다.
Python은 스칼라·특성 산술만 수행한다. 성공한 각 `analysis.json`은 `task_id`, `case`,
`provenance`를 포함하며 원시 출력과 로그도 함께 남긴다. 출처 정보에는 입력·출력·분석기
바이너리 해시, 보고된 리비전(`-dirty` 접미사 포함), 명령, UTC 시각과 경과 초를 포함한다.
소스 해시는 제공한 소스를 식별하며 컴파일과 소스·ELF 대응은 호출자가 책임진다.

```python
from pathlib import Path
from chaser.locality.analyzer import analyze_task

record = analyze_task(
    'chaser_packed', ape=Path('rtems/baseline/build/packed.ape.json'),
    elf=Path('rtems/baseline/build/packed.exe'), cache=Path('rtems/baseline/cache.yaml'),
    source=Path('rtems/baseline/workload.c'),
    executable=Path('rtems/baseline/build/yarda/backend/yarda_cpp'),
    output_dir=Path('/tmp/chaser-packed-analysis'),
    max_cumulative_loop_iterations=2000000, max_source_accesses=1100000,
)
```

데이터셋 생성기는 다음 필드가 있는 JSON 입력 하나를 받는다.

- `cases`: 태스크 ID → `record['case']`로 반환된 지역성 레코드.
- `provenance`: 태스크 ID → `record['provenance']`. 필수 필드는
  `source_hash`, `elf_hash`, `analyzer_commit`, `cache_model_id`,
  `cache_config_hash`, `model_hash`(RF 학습 전에는 null)다.
- `workloads`: `workload_id`, `family_id`, `utilization`(태스크 ID → U),
  `utilization_source`(`measured-mean` 또는 `wcet`)를 담은 레코드. U의 기본값을 0으로 두지 않는다.
- `measurements`: `workload_id`, 숫자 `architecture`(0=Global, 1=Clustered,
  2=Partitioned), `topology_id`, `allocator_id`, `mapping_hash`, 문자열 `run_id`,
  `tet`, `tat`, `execution_status`, 명시적 `measurement_source`(`measured` 또는
  `synthetic`)를 담은 `Measurement` 레코드. `time_unit` 기본값은 `ns`다.
  소문자 `tet`/`tat` 필드는 계획의 TET/TAT 지표를 저장한다. 실패한 실행의 시간은
  null일 수 있으며 `execution_status='ok'`인 경우만 라벨 생성 대상이다.

```sh
python3 -m tools.build_dataset input.json --split split.json --seed 42 \
  --expected-runs 10 --output dataset-v1
```

`freeze_split`은 **계열 단위로** 약 70/20/10 비율을 배정한다.
각 분할에 계열 하나 이상, 전체에 계열 3개 이상이 필요하다. 계열 ID는 실험 설계자가
제공한다. 반복 실행, 배치·매개변수 변형, 주기 변경은 같은 계열을 유지해야 한다.
기존 분할 구성과 시드를 재사용하고 워크로드·계열 구성 변경은 거부한다.
이는 선언된 구성원을 검사하며 두 소스 프로그램의 의미적 관련성을 판단하지 않는다.
제외가 발생해도 다시 분할하지 않는다. 소규모 예비 실험으로 일반화 성능을 입증할 수 없다.

`label_measurements`는 세 구성 모두의 계획된 전체 실행을 요구한다.
중앙값 TAT, 중앙값 TET, 가장 작은 라벨 순서로 선택하고 정확한 동률을 기록한다.
실패·누락·중복 실행이 있으면 라벨을 만들지 않는다. 한 데이터셋은 할당기 하나,
일관된 단위·출처, 구성별 고정 토폴로지를 사용한다. 매핑은 워크로드별로 달라도 되지만
반복 실행 사이에는 고정해야 한다. 할당기 설정이 다르면 별도 계측·라벨 데이터셋이 필요하다.

새 출력 디렉터리는 `raw_measurements.jsonl`, `task_characterization.jsonl`,
`rf_samples.jsonl`, `provenance.jsonl`, `metadata.json`을 포함하며 기존 산출물을
덮어쓸 수 없다. U가 주기에 따라 달라질 수 있으므로 특성화 키는 `(workload_id, task_id)`다.
RF 행은 기존 특성 11개, 계열·분할, 표현·alpha, 라벨과 라벨 근거를 포함한다.
TET/TAT와 라벨은 특성 벡터에 넣지 않는다. 메타데이터는 고정 분할·해시, 특성 버전·순서,
필수 반복 횟수와 제외된 워크로드·사유를 기록한다. 스키마·출처·U 누락은 오류다.
지역성·CLP를 구할 수 없거나 계측이 불완전하면 해당 워크로드를 **8개 변형 모두**
(CA 표현 3개와 CLS alpha 5개)에서 제외하며 원시 증거는 남긴다.

S2에는 `caas-ca`, `ca-csrd`, `alpha=0.5`인 `cls`를 선택한다.
라인 대조군과 다른 alpha는 별도 비교에 사용한다. 원본 사례와 U 맵을 이용해 학습
워크로드 ID와 라벨만 기존 `fit_rf` API에 전달하고 표현마다 새 모델·스케일러를 학습한다.
검증 워크로드 레코드는 고정된 계열 분할과 `utilization`을 포함해
`CalibrationWorkload`에 전달할 수 있다. 보정 TAT는 단순한 구성별 RF 라벨 계측이 아니라
요청한 정확한 매핑에 대응해야 한다. 내보내기 도구는 스케일러나 모델을 학습하지 않는다.

이는 PLAN 5의 데이터 구성 경로를 구현한다. 테스트는 명시적으로 합성한 계측 입력과
실제 기준 C++ 분석을 사용한다. 새 스케줄링 C 워크로드, RTEMS 매핑·반복 계측,
실측 라벨·임곗값, 외부 PolyBench 평가는 이 연결 기능만으로 완료되지 않는다.
PolyBench는 모델·임곗값 선택 이후의 외부 테스트 집합으로 제안되어 있으며,
이 변경에서 학습이나 보정에 추가하지 않는다.

<a id="plan-67-rtems-placement-and-measurement-wiring-check"></a>

## PLAN 6/7: RTEMS 배치·계측 연결 확인

`tools.rtems_smoke`는 기존 packed/spread/conflict 작업 3개에 대해
오프라인 할당기와 실제 RTEMS 단일 코어 친화도를 연결한다. 제공 설정은 통합 검증용
**합성 U와 보정하지 않은 임곗값**을 사용한다. 주기적 스케줄링 태스크 집합이나
학습 데이터셋은 아니다.

```sh
python3 -m tools.rtems_smoke prepare configs/rtems-smoke.json --output rtems/smoke/build/check-v1
python3 -m tools.rtems_smoke editor rtems/smoke/build/check-v1
python3 -m tools.rtems_smoke run rtems/smoke/build/check-v1 --runs 10 --timeout 60
```

준비 단계는 불완전한 배치를 거부하고 소스·설정·지역성 입력을 스냅샷에 보존하며,
`waf configure build`와 `rtems/smoke/wscript`로 SPARC ELF를 빌드한다.
설치된 `/opt/src/rtems/waf` 실행기를 스냅샷에 복사하고, 셸의 `CC`나 `RTEMS_ROOT`가
다르더라도 `/opt/rtems/6` 컴파일러를 명시적으로 선택한다.
입력, waf 실행기, wscript, 컴파일 데이터베이스, 컴파일러와 ELF 해시를 `manifest.json`에
기록한다. 준비 디렉터리와 그 안의 `runs` 디렉터리는 모두 새 경로여야 한다.
후속 배치도 새 디렉터리를 사용한다. `rtems/smoke/build/`의 생성 산출물은 Git에서 무시한다.

`editor` 명령은 실제 waf 컴파일 명령과 해당 스냅샷에서 생성한 `config.h`를 사용해
워크스페이스 `init.c`용 `rtems/smoke/compile_commands.json`을 만든다.
새로 준비한 빌드를 선택하려면 다시 실행한다. 로컬 `.clangd`는 RTEMS 대상·newlib 설정을
제공하고 clangd가 받지 않는 GCC의 `-mfpu`를 제거한다. 대체용 가짜 헤더는 사용하지 않는다.
VS Code에 이전 진단이 남아 있으면 **clangd: Restart language server**를 실행한다.
생성된 편집기 데이터베이스는 Git에서 무시한다. 편집하는 동안 참조된 빌드 디렉터리를
유지해야 하며, 편집기 없이 다음 명령으로 검사할 수도 있다.

```sh
clangd-14 --check="$PWD/rtems/smoke/init.c" --log=error
```

대상 프로그램은 4코어 설정과 요청한 친화도를 검사하고 모든 실행 태스크가 준비되기를
기다린 뒤 공통 가동 시간 기준점에서 태스크별 작업 하나를 활성화한다.
관측한 시작·종료 코어를 기록하고 각 작업 결과를 검사한다. 모든 계측 작업이 끝난 뒤
로그를 출력한다. 공통 기준점에는 순차 이벤트 전달의 시차가 포함되므로 하드웨어의
동시 활성화가 아니다. 반복마다 `script`로 새 시뮬레이터 프로세스를 시작하고
`timeout`으로 각 프로세스 그룹의 시간을 제한한다. RTEMS 툴체인, laysim,
GNU coreutils와 util-linux가 필요하다. 관리되는 워크스페이스에서 laysim은
샌드박스 밖에서 실행한다.

`runs/measurements.jsonl`은 성공·실패 시도와 함께 원시 로그, 반환 코드,
UTC 시작 시각, 호스트 경과 시간과 로그 해시를 기록한다.
`runs/protocol.json`은 시뮬레이터 해시, 정확한 명령과 반복 횟수를 기록한다.
실행 전후에 준비된 입력을 검사한다. 성공하려면 대상 프로그램의 완료 표시,
완전한 태스크 레코드, 유효한 시간, 올바른 친화도와 워크로드 검사 통과가 필요하다.
시뮬레이터 종료 코드만으로는 충분하지 않다.

측정 필드는 의미를 명확히 드러내는 이름을 사용한다.

- `cpu_ns`: 작업별 RTEMS rate-monotonic CPU 사용 시간 표본의 차이.
  표본 수집 오버헤드는 포함하고 실행 태스크가 선점된 시간은 제외한다.
  10초 활성 주기는 사용 시간 집계를 위한 것이며 만료되면 실행 실패다.
- `start_ns` / `completion_ns`: 작업과 사용 시간 집계 전후의 가동 시간 시각.
- `response_ns`: 완료 시각에서 공통 활성화 기준점을 뺀 값으로 대기 시간을 포함한다.
- `sum_job_cpu_ns`, `sum_response_ns`, `makespan_ns`: 각각 CPU 시간 합,
  응답 시간 합, 마지막 완료 시각과 공통 활성화 기준점의 차이.

이 값은 PLAN 5 `Measurement`의 TET/TAT나 RF 라벨로 **자동 내보내지 않는다**.
해당 집계는 연구 지표 계약으로 확정되지 않았다. 기준 지역성 입력은 이 통합 실행 파일과
다른 ELF를 다루므로 연결 검증으로 캐시 모델 정확성이나 지역성 기반 성능 향상을 입증할 수 없다.
실제 실험 수집에는 워크로드 계열, 실측 U, 실행한 ELF 분석, 주기적 활성화,
고정 G/C/P 토폴로지와 합의된 TET/TAT 정의가 여전히 필요하다.
Clustered EDF SMP에는 별도 스케줄러 인스턴스가 필요하며 일부 코어만 포함한
다중 코어 친화도 마스크로는 충분하지 않다.

<a id="plan-78-s1-estimator-and-independent-cache-reference"></a>

## PLAN 7/8: S1 추정기와 독립 캐시 참조 모델

`tools.compare_s1`은 호출자가 준비한 단일 태스크 APE·연결된 ELF 하나를
실제 캐시 형상과 독립적인 Python LRU 캐시 재생 모델로 비교한다.
아래의 소스 기반 워크로드 실험은 이 비교를 기반으로 한다.
대상 장치의 캐시 카운터·실행 추적 검증은 후속 작업이다.

```sh
python3 -m tools.compare_s1 TASK_ID \
  --ape /path/to/task.ape.json --elf /path/to/task.exe \
  --source /path/to/source.c --cache rtems/baseline/cache.yaml \
  --executable rtems/baseline/build/yarda/backend/yarda_cpp \
  --max-source-accesses 100000 --max-line-references 100000 \
  --max-cumulative-loop-iterations 2000000 --timeout 60 \
  --output /tmp/chaser-s1-task-v1
```

출력 디렉터리는 새 경로여야 한다. 한도는 제공된 태스크에 적용한다.
원래 기준 워크로드의 접근은 1,048,592회이므로 예시의 100,000회 한도를 초과한다.
전체 이벤트 출력은 참조 횟수에 비례하는 메모리·디스크 공간이 필요하다.
이는 범위를 제한한 정확성 검증 경로이며 분석기 확장성 벤치마크가 아니다.
소스·APE·ELF 대응은 호출자의 책임이며 소스 해시만으로 그 대응을 입증하지 않는다.

Global RD 대조군은 `full-linked-stream-capacity-bins-v1`이다.
라인 크기가 같고 L1 용량이 LLC 이하일 때 전체 접근열의 캐시 라인 RD가 L1 라인 용량보다
작으면 L1 최초 적중, L1과 LLC 라인 용량 사이면 LLC 최초 적중으로 센다.
더 큰 RD와 최초 접근은 메모리 접근으로 센다. 최초 접근도 분모에 포함한다.
이는 실험적 확장이며 기존 CAAS 출력이나 요구 접근 계층의 LLC 요청열 시뮬레이션이 아니다.

모든 RD/CSRD 계산은 `yarda_cpp`에서 수행한다. 실행기는 같은 APE·ELF를 실제 형상과
완전 연관 L1 세트 하나로 바꾼 설정으로 두 번 분석한다. 두 번째 L1의 full-exact CSRD
히스토그램은 L1 용량을 초과하는 유한 거리까지 포함한 전체 접근열 Global RD다.
그 LLC 횟수는 대조군에 사용하지 않는다. 이 방식은 객체 간 공유 라인을 포함해 연결된
라인의 식별을 유지한다. 데이터셋 경로의 기존 객체 상대 Global RD 출력은 변경하지 않는다.

참조 모델은 전체 YARDA 이벤트의 순서 있는 연결 주소만 받아 정수 나눗셈으로 라인 ID를
만들고, 세트별 LRU 상주 상태를 독립적으로 관리한다. YARDA의 세트·태그·RD·결과 필드는
사용하지 않는다. 참조 모델과 실제 CSRD 모두 빈 캐시에서 시작하며, 모든 요구 미스에
할당하고 L1 미스만 LLC에 전달한다. 역방향 무효화, 희생 라인 삽입, 프리페치,
다시 쓰기 트래픽은 포함하지 않는다. 이벤트에는 라인을 가로지르는 접근이 이미 전개되어
있으므로 다시 전개하지 않는다. Global RD 임곗값 대조군은 두 용량 경계에서 전체 접근열의
최근성을 사용하므로 세트 충돌 효과가 없어도 요구 접근만 받는 LLC의 최근성과 다를 수 있다.

`comparison.json`은 L1/LLC/메모리 횟수·비율, 성분별 절대 오차, 태스크별
MAE/RMSE/최대 오차, 입력·접근열·출력·구현 해시, 캐시 모델, 정확한 명령, 도구 버전과
호스트 경과 시간을 기록한다. MAE/RMSE는 비율 성분 3개에 같은 가중치를 준다.
빈 입력은 비율·오차가 null이며 상태는 `empty`다. CSRD·참조 모델 불일치는
`mismatch`로 보존한다. CLI 종료 코드는 `ok`/`empty`이면 0, 모델 불일치면 1,
실행 실패나 잘못된 입력이면 2다. 입력 스냅샷, 두 원시 결과·이벤트 쌍, 파생 설정,
로그와 실패 시 `failure.json`에 증거를 남긴다. 잘린 이벤트, 불완전한 접근 포괄성,
잘못된 횟수, 해시·접근열 불일치, 미지원 모델, 시간 초과는 성공한 비교로 처리할 수 없다.

이는 **YARDA가 생성한 공통 주소열**에서 캐시 판정을 검증한다.
APE 전개와 ELF 주소 해석을 독립적으로 검증하거나 대상 장치의 캐시 카운터·실행 추적을
수집하지는 않는다. 보고서에는 `execution_validation=not-performed`를 명시한다.
S1-D에 따라 별도 실행 증거가 확보되기 전까지 결론은 추상 모델 수준에 한정한다.
현재 기본 동작 확인의 시간이나 호스트 캐시 결과를 GR740 카운터 대신 사용할 수 없다.

<a id="s1-load-only-workload-sweep"></a>

## S1 읽기 전용 워크로드 실험

`sh scripts/verify`로 분석기·플러그인을 빌드하고 툴체인을 검증한 뒤,
캐시가 비어 있는 상태의 모델 검증 25개 사례를 새 디렉터리에 실행한다.

```sh
python3 -m tools.run_s1_suite --output rtems/s1/build/evaluation-v1 \
  --sweeps 3 --max-references 250000 --timeout 60
python3 -m tools.plot_s1 rtems/s1/build/evaluation-v1/suite.json \
  --output rtems/s1/build/evaluation-v1/plots
```

시각화 명령은 환경에 설치된 Matplotlib을 사용한다. 소규모 확인에는
`--cases packed_8 spread_8 conflict_4 conflict_5 mean_uniform mean_mixed`를 선택한다.
기본 순회 3회는 최초 접근과 반복 2회를 드러내며 독립된 대상 실행 3회를 뜻하지 않는다.
검증 도구는 기존 출력 디렉터리를 거부하고 부분 선택을 명시하며, 각 실패를 보존하면서
후속 사례를 계속 시도한다. 종료 코드는 선택 사례 전체 통과 시 0, 사례 실패나
CSRD·참조 모델 불일치 시 1, 잘못된 입력·환경 설정 시 2다.
Global RD 예측 오차는 실험 결과이며 전체 검증 실패로 처리하지 않는다.

`chaser.s1.workloads`는 사례마다 자체적으로 완결된 C 소스를 생성한다.
스냅샷의 `rtems/s1/Makefile`은 바로 그 소스를 LLVM/APE와 SPARC RTEMS ELF로 빌드한다.
추출 후 APE 경계를 수정하지 않는다. 분석 함수는 누적값을 반환하고 정렬된 volatile
바이트 배열 하나에 읽기만 수행한다. 준비와 체크섬 검사는 함수 밖에 있다.
검증 도구는 생성 주소열을 사례별 논리적 오프셋, 읽기 연산, 정렬, 전체 접근 횟수와
완전한 분석 포괄성에 대조한다. 모든 RD/CSRD 계산은 C++에 남기며,
라인 Global RD는 앞서 설명한 연결 주소 기반 완전 연관 대조군을 사용한다.

목록은 원래 읽기·수정·쓰기 기준 실험을 보존하고 다음 사례를 추가한다.

- 원소 8개의 packed, 고유 라인 3·4·5·8개의 spread/conflict 쌍.
- 32바이트 간격의 연속 순환 접근: 라인 수 256, 448, 511, 512, 513, 576, 1024,
  32768, 61440, 65535, 65536, 65537, 69632, 73728.
- 유한 평균 RD가 511이고 최초 접근 라인 1024개, 전체 참조 수·메모리 사용 범위가 같은
  두 분포. `mean_uniform`은 512라인 순환을 재방문한 뒤 새 라인 512개를 한 번씩 읽는다.
  `mean_mixed`는 단일 라인과 겹치지 않는 1023라인 순환을 같은 횟수로 재방문한다.
  3회 순회 시 유한 히스토그램은 각각 `{511:4092}`, `{0:2046,1022:2046}`이다.
  여기서 `sweeps`는 혼합 패턴 전체를 반복하는 대신 재사용 표본 수를 제어한다.

각 사례는 소스, LLVM, 추출된 APE, 실행 파일, 빌드 명령·로그, 원소 RD,
두 연결 주소 기반 계층 분석·이벤트와 비교 보고서를 보존한다.
`inputs.json`은 컴파일러 버전, 지원 코드·도구 해시와 한도를 기록하고,
`suite.json`은 CA, 최초 접근 비율, 히스토그램, 횟수·비율, 소스 포괄성과 계층별
오차 집계를 추가한다. `results.csv`는 워크로드 오차 표다.
집계 MAE/RMSE는 모델 불일치를 포함한 평가 워크로드에 같은 가중치를 주며,
실패 사례는 목록에 남기되 수치 오차에서 제외한다.
`resources.json`은 실행 경과 시간, 디스크 사용량, Linux 프로세스 RSS를 기록한다.
전체 이벤트 출력과 참조 재생이 포함되므로 이 비용을 분석기만의 확장성 측정으로
사용할 수 없다. `rtems/s1/build/`의 생성된 원시 실행 결과는 Git에서 무시한다.

검증 도구는 모델링된 배열 접근을 검사한다. C·APE·ELF 일치와 논리적 오프셋 검사로
실제 CPU 접근 추적의 동일성을 입증하지는 않는다. 대상의 스택·명령어 접근, 준비 후
캐시 상태, 컴파일러 효과는 이 빈 캐시 모델의 범위 밖이다.
체크섬 검사가 가능한 ELF도 캐시 카운터, TET/TAT, 스케줄링 라벨을 제공하지 않는다.
S1 결론은 추상 모델 검증 범위에 한정한다.

최초로 완료한 25개 사례의 모델 실험, 오차 표, 산점도와 증거 해시는
[S1 모델 평가](artifacts/s1/model-v1/README.md)에 요약했다.

## S1 실행 주소열 검증

YARDA가 생성한 주소열과 독립적인 실행 증거는 다음 명령으로 수집한다.
Clang/opt 14, GNU nm, Valgrind Lackey와 위 verifier가 빌드한 YARDA가 필요하다.

```sh
python3 -m tools.run_s1_execution --output rtems/s1/build/host-trace-new \
  --sweeps 3 --max-references 250000 --timeout 120 --max-trace-bytes 536870912
python3 -m tools.plot_s1 rtems/s1/build/host-trace-new/suite.json \
  --output rtems/s1/build/host-trace-new/plots
```

작은 검증에는 `--cases packed_8 conflict_5 capacity_513`을 추가한다.
동일 생성 C를 host x86-64 non-PIE ELF와 APE로 빌드하고, **실행한 바로 그 ELF**를
YARDA에 전달한다. Lackey의 instruction PC와 ELF symbol 범위로 `chaser_s1` 함수의
`data` 배열 접근만 선택한다. 함수는 한 번 실행하는 leaf 함수여야 하며,
진입·종료 기록이 없거나 배열 경계에 일부만 겹친 접근이 있으면 실패한다.

검증은 두 단계다. 먼저 `(load/store, 절대주소, byte 크기)`의 전체 순서를 비교한다.
그다음 **필터링된 실행 trace**를 cold LRU로 재생하여 CSRD의 계층별 count와 비교한다.
최종 cache count만 같고 주소 순서가 다른 경우도 실패로 처리한다.
초기화·instruction·stack·다른 객체 접근은 replay 전에 제거하므로,
이 결과는 전체 프로그램 Cachegrind 통계나 GR740 hardware counter 측정값이 아니다.

원본 `trace.log.gz`, 필터 결과 `accesses.jsonl.gz`, native/Valgrind checksum,
source/LLVM/APE/ELF, 명령·도구 버전·해시와 실패 기록을 보존한다.
원본 stdout/stderr의 합산 비압축 byte 수와 실행 시간을 제한하며,
제한 초과·비정상 종료·checksum 오류·불완전 trace를 성공으로 취급하지 않는다.
기존 output 디렉터리는 덮어쓰지 않는다. CLI 종료 코드는 전체 성공 0,
case 실패/주소열·CSRD 불일치 1, 잘못된 입력·초기 설정 실패 2다.

전체 결과와 기존 모델 그래프와의 관계는
[실행 trace 검증 결과](artifacts/s1/host-trace-v1/README.md)에 정리했다.

## S1 Cachegrind 비교

기존 host 실행 suite의 동일 ELF를 stock Cachegrind로 실행해 정적 예측과 비교한다.

```sh
python3 -m tools.run_s1_cachegrind --input rtems/s1/build/host-trace-v2 \
  --output rtems/s1/build/cachegrind-new
python3 -m tools.plot_s1 rtems/s1/build/cachegrind-new/suite.json \
  --output rtems/s1/build/cachegrind-new/plots
```

x축은 배열 load 소스 줄에 귀속된 Cachegrind data count다. 초기화·stack·instruction의
cache 영향은 유지되며, y축의 cold 배열 전용 모델과 조건이 다르다.
[25-case 결과와 해석](artifacts/s1/cachegrind-v1/README.md)에 차이와 원본 출력을 보존했다.

함수 진입 시 cache를 비우는 재비교에는 [별도 cold-entry 빌드](tools/cachegrind/README.md)를 사용한다.

```sh
python3 -m tools.run_s1_cachegrind --input rtems/s1/build/host-trace-v2 \
  --output rtems/s1/build/cachegrind-cold-new --cold-prefix /tmp/chaser-cg-cold-install
```

[Cold Cachegrind 결과](artifacts/s1/cachegrind-cold-v1/README.md)는 CSRD와 25/25 count가 일치했다.
함수 첫 명령 직전에 I1·D1·LL residency만 reset하며, 이후 전체 traffic과 stock cache 판정은 유지한다.

PolyBench 계열 고정 크기 kernel 4개의 별도 host 비교와 correlation 제외 근거는
[S1 외부 Cachegrind 확인](artifacts/s1/polybench-cold-v1/README.md)에 보존했다.

<a id="original-polybench-medium-suite"></a>

## 원본 PolyBench MEDIUM 벤치마크 모음

[PolyBench/C 4.2.1 전체 30종 예제](rtems/periodic/polybench/README.md)는 원본의
MEDIUM 크기, 초기화 방식, `double`/`float`/정수 자료형을 유지한다.
[스키마 v3 설정](configs/periodic-polybench)을 기존
`tools.rtems_periodic prepare/analyze/run` 명령으로 실행한다. 별도 명령
`python3 -m tools.polybench_suite --periodic --output .cache/polybench-medium --timeout 600`은
네이티브 출력을 검증하고 G/C/P RTEMS ELF를 빌드한 뒤 모든 사례에 YARDA 분석을 시도한다.
프런트엔드·백엔드 실패와 시간 초과도 보고서에 남긴다. 실행 성공과 독립적인
메모리 접근 추적 검증은 구분한다.

2026-09-29 삼각형 루프 시작값·종료 경계 지원을 반영한 YARDA `a058a45`·APE `c976301`로
전체를 다시 검사했다. 네이티브 출력 비교와 G/C/P 빌드는 **30/30 통과**했고,
YARDA도 **30종 모두 통과**했다. 네이티브·G·C·P 합계 **120/120개 분석이 통과**했으며,
이전에 종료 경계 때문에 차단됐던 9종도 해결됐다. 전체 결과와 별도 접근 횟수 검사는
[MEDIUM 재검증 기록](artifacts/periodic/polybench-medium-v3/README.md)에 있다.
2mm·atax·correlation·gemm·jacobi-2d의 CAAS-CA, CA-CSRD, CLS, CLP는
[MEDIUM locality 분석](artifacts/periodic/polybench-locality-medium-v1/README.md)에 정리했다.

<a id="periodic-multi-array-workloads"></a>

## 주기적 다중 배열 워크로드

주기적 계측 환경은 `schema_version: 2`의 명시적 배열을 지원한다.
자료형을 지정하는 `cyclic`·`paired-read` 커널(`uint8_t`/`uint32_t`)과
uint32 곱셈·누적·출력 저장을 수행하는 행 우선 `gemm-u32`를 제공한다.
[PolyBench 기반 ATAX 예제](configs/periodic-multi-array/polybench-atax-u32-medium.json)는
행렬, 입력 벡터, 임시 벡터, 출력 벡터로 `y = Aᵀ(Ax)`를 계산한다.
uint32 연산과 주기적 계측 환경을 사용하며, 원본과의 차이와 실행 명령은
[ATAX 안내](rtems/periodic/experiment-guide/INPUTS.md#polybench-atax)를 따른다.
배열에는 다차원 `shape`와 양의 행 우선 간격 `strides_elements`를 선언할 수 있다.
GEMM은 2차원 형상에서 행렬 크기를 유도한다. 기존의 평탄한 `length` 입력도 지원한다.
태스크는 읽기 전용 입력을 공유할 수 있으며, 각 출력 배열은 한 태스크가 독점한다.
입력 스키마와 계측 계약은 별개이며, 계측 계약은
`chaser-periodic-measurement-v3`를 유지한다.

[GEMM 기본 동작 확인용 설정](configs/periodic-multi-array/gemm-u32-smoke.json),
[입력을 공유하는 GEMM](configs/periodic-multi-array/gemm-u32-shared-smoke.json),
[입력을 공유하는 cyclic/paired-read](configs/periodic-multi-array/shared-reads-smoke.json)으로 시작한다.
[다중 배열 실험 안내](rtems/periodic/experiment-guide/INPUTS.md#multi-array)는
필드 단위·범위, 준비·분석, G/C/P 실행과 독립 P 실행 절차를 설명한다.
체크섬·접근 횟수 계약도 명시하며,
[검증 기록](rtems/periodic/experiment-guide/INPUTS.md#multi-array-verification)에서
완료된 검사와 로컬 증거 경로를 확인할 수 있다.
새 연산은 [사용자 커널 인터페이스](rtems/periodic/experiment-guide/CUSTOMIZATION.md#kernel-interface)에
따라 직접 작성한 C 템플릿과 Python 검증·참조 계약을 함께 등록한다.
GEMM도 같은 인터페이스를 사용한다. 준비된 스냅샷은 두 소스와 해시를 함께 보존한다.

2026-09-28 검증에서 `scripts/verify`는 **511개 테스트를 통과**했고,
선택적 환경 테스트 3개는 건너뛰었다. 앞서 수행한 다중 배열 SIM 기본 동작 확인은
**20/20 성공**했으며, 해당 기록의 마지막 변경 이후 SIM은 재실행하지 않았다.
분석은 연결된 ELF 객체를 기준으로 자료형별 읽기·쓰기 순서를 검사한다.
계측되는 작업 내부의 GEMM 출력 해시용 읽기도 포함한다.
분석 모델은 캐시가 비어 있는 상태에서 태스크 하나의 작업만 다루며,
쓰기 트래픽·캐시 일관성·태스크 간 주기적 간섭은 모델링하지 않는다.
스키마 v2 결과는 진단용이며 RF 데이터셋의 자동 라벨 생성 대상에서 제외한다.
대규모 성능 실험, float32, 공유 쓰기, 실제 하드웨어 검증은 후속 범위다.

<a id="periodic-rf-dataset-measurement"></a>

## 주기적 RF 데이터셋 계측

[주기적 데이터셋 안내](datasets/periodic-v2/README.md)에서 보존된 입력·측정 결과,
제외 대상, RF 내보내기 상태를 확인할 수 있다(2026-09-24 기준).
[RTEMS 계측 환경](rtems/periodic/README.md)은 주기적 G/C/P 시간 계측과 독립 U 측정을 구현한다.
실험 환경 생성·수정·재현은 [실험 가이드](rtems/periodic/EXPERIMENT-GUIDE.md)를,
보드 설정·실행·로그 수집·계측 검증은
[하드웨어 검증 가이드](rtems/periodic/HARDWARE-VALIDATION.md)를 따른다.

- `datasets/periodic-v2/`: 고정 태스크 집합 207개, 독립 U, 지역성 분석과 검증용 보정 결과.
- `datasets/periodic-final-v1/`: CAAS-CA·CA-CSRD·CLS 각각에서 동일한 적격 태스크 집합
  198개의 최종 라벨과 기존 스칼라 RF 표본. 학습/검증/테스트 분할은 120/41/37이다.
- `.cache/final-replacement-v1/run/`: 교체 대상 9개 중 5개를 채택했고 4개는 미해결이다.
  상태는 `partial`, 내보내기는 `not_exported`이며 교체 표본은 위 198개에 포함되지 않는다.

`arm_phase`/`release_mismatch` 실패가 있는 태스크 집합 9개는 세 정책 모두에서 제외한다.
합의된 RF 연구 조합은 할당 CAAS-CA/CA-CSRD/CLS × 입력 CAAS-CA+U/CA-CSRD+U/CLP+U다.
CLP 21개 특성 내보내기와 RF 학습은 미완료이며, 현재 표본은 이전 스칼라 스키마를 사용한다.
예비 산출물과 정리 보고서는 삭제했다. 최종 수집·내보내기 CLI 모듈도 작업 트리에서
제거했으므로, 결과가 보존되어 있다는 사실이 해당 명령을 현재 실행할 수 있다는 뜻은 아니다.
남아 있는 경로와 재개 지점은 데이터셋 안내를 참고한다.
