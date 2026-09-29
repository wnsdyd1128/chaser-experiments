<a id="rtems-periodic-measurement-harness"></a>

# RTEMS 주기적 계측 환경

설정 JSON으로 실험을 생성하고 환경을 수정·재현하는 절차는
[실험 가이드](EXPERIMENT-GUIDE.md)를 참고한다. 실제 보드의 준비·실행·계측 검증은
[HW 검증 가이드](HARDWARE-VALIDATION.md)를 따른다.

이 작업 트리는 [현재 계측 계약](../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT-V3.md)과
[데이터셋 재구축 계획](../../system-prompt-extraction/plan/DATASET-REBUILD-PLAN.md)을 따른다.
저장된 계획과 원시 측정 결과의 식별을 유지하기 위해 직렬화된 계약 ID는
`chaser-periodic-measurement-v3`를 그대로 사용한다. Python 모듈은 일반 모듈 이름을 사용한다.

`tools.rtems_periodic`은 빌드·분석·단일 배치 실행을 지원한다.
`chaser.periodic.calibration`에는 현재 P 전용 임곗값 계획기·선택기·배치 분류기가 있으며,
전체 수집 과정을 수행하는 CLI는 아직 없다. S1의 PolyBench 실험은 별도 실행기를 사용한다.

<a id="prepare-and-inspect-a-small-run"></a>

## 소규모 실행 준비와 확인

설치된 GR740 RTEMS SDK, laysim, Clang/opt 14, waf와 YARDA 빌드 대상을 사용한다.
워크스페이스 루트에서 실행하고 출력은 새 디렉터리에 저장한다.

```sh
python3 -m tools.rtems_periodic prepare configs/periodic-example.json --output .cache/periodic-example
python3 -m tools.rtems_periodic analyze .cache/periodic-example
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture p --runs 1 --output .cache/periodic-example-p
```

예제는 기본 동작 확인을 위해 실행 구간을 짧게 설정했다. 논문용 계측에는 현재 계획의
준비·측정 구간 길이, 반복 횟수, 고정된 입력을 사용해야 한다. 설정에는 `warmup_ticks`,
`u_repeats`, `horizon_ticks`, 태스크 주기, 실제 접근 패턴과 코어 배치를 지정한다.
준비 구간의 경계는 모든 태스크 주기와 일치해야 한다. G/C/P는 같은 워크로드 소스를
서로 다른 EDF SMP 스케줄러 도메인에서 실행한다. 분석은 각 구성에서 연결된 ELF의
접근 순서와 배열 배치를 검사한다.

<a id="original-polybench-medium-kernels"></a>

## 원본 PolyBench MEDIUM 커널

[PolyBench/C 4.2.1 전체 30종](polybench/README.md)은 스키마 버전 3과 같은
`prepare/analyze/run` CLI를 사용한다. 각 설정은 공개된 MEDIUM 크기와 원본 연산을
유지하는 커널 하나를 선택한다. 준비 단계에서 원본과 어댑터의 네이티브 최종 출력값을
비교한 뒤 G/C/P RTEMS ELF를 빌드한다. 초기화는 매 작업의 계측 구간 전에 수행하고,
원본 출력 형식에 따른 최종 출력값의 체크섬은 계측 구간 뒤에 계산한다.
이 예제는 진단용 워크로드다. 독립 명령 `tools.polybench_suite`도 모든 벤치마크에
YARDA 분석을 시도하고 지원하지 않는 사례를 보고서에 남긴다.

<a id="explicit-arrays-and-integer-gemm"></a>

## 명시적 배열과 정수 GEMM

`schema_version: 2`를 지정하고 최상위 `arrays`에 저장 공간을 정의한 뒤
`tasks[].arrays`에서 태스크의 배열 역할을 연결한다. 배열 `length`와 연결 정보의
`offset_elements`는 원소 단위다. 선택 필드 `shape`와 `strides_elements`는
다차원 행 우선 저장 배치를 나타낸다. 형상으로 최소 할당 길이를 유도하며,
명시적인 length로 패딩을 확보할 수 있다. 2차원 형상은 GEMM 차원과 간격을 유도하고
이와 충돌하는 태스크 값을 거부한다. 읽기 커널의 `stride_bytes`는 바이트 단위다.
지원 커널은 자료형을 지정하는 `cyclic`, `paired-read`, `gemm-u32`,
`polybench-atax-u32`다. 각 배열은 자체 32/4096바이트 정렬, 자료형, 상수 초기값을 갖는다.
읽기 전용 입력은 공유할 수 있고 출력 배열은 한 태스크가 독점해야 한다.
지원하지 않는 필드, 배열 별칭, 범위를 벗어나는 접근은 거부한다.
계측 계약은 `chaser-periodic-measurement-v3`다.

| 설정 | 워크로드 |
|---|---|
| [gemm-u32-smoke.json](../../configs/periodic-multi-array/gemm-u32-smoke.json) | 태스크 하나, A × B → C, 작업당 두 번 순회 |
| [gemm-u32-shared-smoke.json](../../configs/periodic-multi-array/gemm-u32-shared-smoke.json) | 태스크 둘이 A/B를 공유하고 각자 C 배열에 저장 |
| [shared-reads-smoke.json](../../configs/periodic-multi-array/shared-reads-smoke.json) | cyclic과 paired-read 태스크가 입력 배열을 공유 |
| [polybench-atax-u32-medium.json](../../configs/periodic-multi-array/polybench-atax-u32-medium.json) | PolyBench 기반 y = Aᵀ(Ax), 임시·출력 배열을 독점하는 uint32 행렬·벡터 커널 |

위 입력 중 하나와 새 출력 디렉터리로 같은 `prepare`, `analyze`, `run` 명령을 사용한다.
[실행 안내](experiment-guide/INPUTS.md#multi-array)에는 G/C/P와 독립 P 명령이 있다.
GEMM은 매 순회마다 C를 덮어쓰고 작업 끝에서 논리적 출력값의 해시를 한 번 계산한다.
해시 계산에 필요한 읽기도 계측·분석에 포함한다.
배열은 작업 사이가 아니라 실행 태스크를 시작하기 전에 한 번 초기화한다.
ATAX는 매 순회마다 논리적 임시·출력 배열을 초기화한다.
[ATAX 안내](experiment-guide/INPUTS.md#polybench-atax)에서 소스, 형상 계약,
원본 PolyBench 벤치마크와의 차이를 설명한다.

새 커널은 [사용자 커널 인터페이스](experiment-guide/CUSTOMIZATION.md#kernel-interface)에
따라 Python 검증·참조 계약을 등록하고 `chaser/periodic/kernels/`에 C 템플릿을 작성한다.
GEMM 루프는 `kernels/gemm.c.in`에 있다. 원본 입력을 수정한 뒤 새 스냅샷을 준비한다.
분석은 변경된 커널 소스를 거부하고 저장된 실행 결과는 해당 소스의 해시를 보존한다.

분석은 모든 객체의 연결된 주소, 접근 너비, 읽기·쓰기 순서를 검증한다.
clang O0 분석과 워크로드 O0/O2 컴파일을 구분해서 기록한다.
쓰기는 요구 접근에 따른 캐시 상주 여부만 다루며 쓰기 트래픽이나 지연은 모델링하지 않는다.
입력을 공유하더라도 캐시가 비어 있는 상태에서 태스크 하나를 분석하는 모델이며,
간섭·캐시 일관성 모델로 바뀌지 않는다. 범위 제약과 완료된 검사는
[입력 계약](experiment-guide/INPUTS.md#multi-array)과
[검증 기록](experiment-guide/INPUTS.md#multi-array-verification)을 참고한다.
Python 호출부에서는 `workload_source(plan['tasks'], arrays=plan['arrays'])`와
`check_layout(symbols, plan['arrays'])`를 사용한다.

<a id="accounting-and-validation"></a>

## 시간 집계와 검증

준비 구간을 포함한 모든 작업은 완전성·체크섬·활성화 시점·상태·마감 시각·도메인 검사를
통과해야 한다. 지표 계산에는 측정 구간의 작업만 사용한다.
TET는 작업별 CPU 사용 시간 차이를 합산한다. TAT는 명목상 활성화 시점이 같은 작업들을
묶어 첫 시작부터 마지막 완료까지의 시간을 구한 뒤 합산한다.
`response_sum_ns`는 작업별 활성화부터 완료까지의 시간을 별도로 합산한다.
독립 U는 실행별 측정 작업의 평균 CPU 사용 시간을 구하고, 그 중앙값을 태스크 주기로
나눈 값이다. 실패하거나 불완전한 실행에는 성공한 구성 라벨을 부여할 수 없다.

실행기는 `protocol.json`, `measurements.jsonl`과 실행별 번호가 붙은 `.log`를 저장한다.
실행 중에는 `tail -f <output>/0.log`로 진행 상황을 확인한다.
`chaser.periodic.dataset.load_batch`는 저장된 해시를 검사하고 원시 로그를 다시 파싱한다.
`feature_record`는 독립 측정한 U와 지역성 특성을 결합한다.
진단용 `--trace`·`--empty` 실행은 시간 측정 라벨에서 제외한다.
스키마 v2 프로토콜은 커널 계약, 워크로드 최적화, 배열·커널 모듈 스냅샷도 보존한다.
다중 배열 결과는 진단용이다. 지역성 보고서는 `dataset_eligible=false`를 기록하고,
`to_measurement`는 별도 적격성 검증 전까지 RF 라벨로의 자동 변환을 거부한다.
