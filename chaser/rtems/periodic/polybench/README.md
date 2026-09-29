<a id="original-polybenchc-medium-examples"></a>

# 원본 PolyBench/C MEDIUM 예제

[PolyBenchC-4.2.1](https://github.com/MatthiasJReisinger/PolyBenchC-4.2.1)의 전체
30종을 제공한다. `upstream/`에는 리비전
`3e872547cef7e5c9909422ef1e6af03cf4e56072`의 C·헤더·공용 런타임을 수정 없이
보존했다. [원본 라이선스](upstream/LICENSE.txt)와 [작성자](upstream/AUTHORS)를 따른다.

MEDIUM 크기, 원본 초기화 수식, 커널 루프, 기본 자료형을 유지한다. Deriche는
`float`, Floyd–Warshall과 Nussinov의 테이블은 `int`, 나머지는 `double`이다.
Nussinov의 수열은 원본처럼 `char`다. 체크섬 반환형 `uint32_t`는 커널의
배열 자료형이나 산술을 바꾸지 않는다.

## 두 실행 경로

명령은 워크스페이스 루트에서 실행하고 출력은 새 경로에 저장한다.

```sh
# 원본/어댑터 네이티브 출력 비교 + 네이티브 ELF로 YARDA 실행: 전체 30종
python3 -m tools.polybench_suite --output .cache/polybench-native-medium --timeout 600

# 위 검증에 G/C/P RTEMS 빌드·YARDA 분석을 추가: 전체 30종
python3 -m tools.polybench_suite --periodic \
  --output .cache/polybench-periodic-medium --timeout 600

# 기존 periodic CLI로 개별 벤치마크 실행
python3 -m tools.rtems_periodic prepare \
  configs/periodic-polybench/atax-medium.json --output .cache/atax-medium
python3 -m tools.rtems_periodic analyze .cache/atax-medium --timeout 600
python3 -m tools.rtems_periodic run .cache/atax-medium \
  --architecture p --runs 1 --timeout 3600 --output .cache/atax-medium-p
```

`prepare`는 RTEMS SDK/waf와 clang-14, `analyze`는 opt/llvm-extract-14와 설치된
APE/YARDA, `run`은 laysim 환경을 사용한다. 독립 네이티브 검증은 RTEMS SDK와
시뮬레이터가 필요 없다. 전체 검증 명령의 `--periodic`은 실제 시뮬레이터를 실행하지
않으며, 시뮬레이터 실행은 `run`으로 별도 수행한다.

각 설정은 `schema_version: 3`, `polybench: {benchmark, dataset: "MEDIUM"}`와
주기·코어·실행 구간·준비 구간을 지정한다. 한 스냅샷에 벤치마크 태스크 하나를
두어 원본 전역 배열의 독점 소유권을 유지한다. O0를 사용하며 자료형·차원 변경과
임의 C 문자열 주입은 허용하지 않는다. 기본 주기는 100000틱(100초)이며,
총 작업 2개 중 첫 작업이 준비 구간이다. 이 값은 이용률을 보정한 실험 설정이
아니며, 장시간 커널은 측정 결과에 따라 주기·실행 구간·준비 구간을 함께 조정한다.
`--timeout`은 각 호스트 프로세스의 경과시간 상한이다.

## 보존되는 연산과 계측 경계

어댑터는 원본 `main`의 호출을 재사용한다. 배열은 64바이트로 정렬한 전역 저장 공간으로
옮겨 RTEMS 스택 제한과 ELF 주소 해석을 지원한다. 매 작업 전에 임시 저장 공간을
0으로 채우고 원본 `init_array`를 호출한다. 계측 구간에는 원본 커널 호출을 포함하며,
재초기화와 최종 출력값 검증은 계측 구간 밖에서 수행한다. 재초기화도 캐시에
접근하므로 캐시가 비어 있다고 가정한 YARDA 결과를 실제 작업의 캐시 초기 상태로 간주하지 않는다.

`prepare`는 원본 네이티브 바이너리와 어댑터 바이너리의 전체 최종 출력값이 같은지,
재초기화 후 두 번째 실행의 체크섬도 같은지 검사한다. 체크섬은 원본
`print_array`의 출력 정밀도를 그대로 사용한 FNV-1a32다. 부동소수점 결과의
비트 단위 동일성이나 출력에서 생략된 소수 자릿수까지 증명하지 않는다. RTEMS에서도
이 네이티브 기준 체크섬을 검사하며, 호스트/SPARC 수치 차이가 발생하면 성공으로
덮어쓰지 않고 체크섬 실패로 보존한다.

## 분석 결과 해석

원본 소스 → LLVM O0 → 커널 인라이닝 → 작업 함수 추출 → APE →
`yarda_cpp --analysis hierarchy-rd` 순서다. 추출 과정에서 분석 진입 함수의 어노테이션을
보존하고, 분석기의 루프 경계나 접근 인덱스를 결과에 맞춰 수정하지 않는다.
네이티브와 각 G/C/P ELF의 실제 심벌 주소를 사용한다. 전체 MEDIUM 분석은
이벤트 JSON을 모두 내보내지 않고 캐시 계층 분석 결과를 저장한다.

`summary.json`은 30종을 모두 포함한다. 각 `analysis/`와 `native-analysis/`에
명령, 종료 코드, 소요 시간, 로그, MAP과 성공 시 캐시 계층 분석 JSON을 보존한다.

- `passed`: YARDA가 정상 종료했고 모델의 접근 포괄성·횟수 보존 검사를 통과했다.
- `blocked`, `stage: frontend`: APE 입력 생성 실패로 백엔드를 실행할 수 없었다.
- `failed`: 백엔드 실행 또는 결과의 접근 포괄성 검사 실패.
- `timeout`: 설정한 호스트 경과시간 상한 초과.

실패가 하나라도 있으면 전체 CLI의 종료 코드는 1이다. 결과를 누락하거나 작은 데이터셋으로
대체하지 않는다. `trace_validation: not-validated`는 독립적인 동적 접근 순서
검증을 아직 수행하지 않았다는 뜻이다. 실행 성공을 전체 C 접근의 의미적 검증과
동일시하지 않는다. 특히 Floyd–Warshall처럼 데이터에 따른 조건 분기가 있는
경우 생성된 MAP이 실제 선택된 분기의 접근만 표현하는지 추가 검증이 필요하다.
모든 결과는 `dataset_eligible: false`인 진단용이며 RF·시간 측정
학습 데이터에 자동 편입하지 않는다.

2026-09-29 YARDA `a058a45`·APE `c976301`로 다시 검증한 결과는
[MEDIUM 재검증 증빙](../../../artifacts/periodic/polybench-medium-v3/README.md)에 보존한다.
원본·어댑터 네이티브 출력 비교와 G/C/P 빌드는 30종 모두 통과했다.
YARDA 분석도 **30종 모두 통과**했으며 네이티브·G·C·P 합계 **120/120개 분석이 통과**했다.

`j = i`나 `j = i + 1`처럼 바깥 루프 변수에 의존하는 시작값뿐 아니라,
`j <= i`나 `k < j`처럼 종료 경계가 바깥 루프 변수에 의존하는 경우도 처리한다.
이전에 차단됐던 Cholesky·Durbin·LU·LUDCMP·Nussinov·SYMM·SYR2K·SYRK·TRISOLV가
모두 통과했다. SYRK·SYR2K·TRISOLV·Durbin은 원본 C에서 별도로 계산한 접근 횟수와도
일치했다. 이 접근 수 검사는 전체 동적 접근 순서의 독립 검증을 대신하지 않는다.

[시작값 지원 단계의 재검증](../../../artifacts/periodic/polybench-medium-v2/README.md)은
YARDA `b33abc1`·APE `462ed4e`에서 21종 통과·9종 차단을 기록했다.
당시 Correlation·Covariance·GramSchmidt·TRMM 4종이 먼저 통과했다.

[이전 MEDIUM 검증](../../../artifacts/periodic/polybench-medium-v1/README.md)에서는
17종이 통과하고 13종이 차단됐다. 당시 Floyd–Warshall은 120초 제한에 도달했고,
600초로 재실행한 네이티브/G/C/P 네 경우는 약 191–193초에 정상 종료했다.
이번 재검증에서도 600초 상한으로 네 경우 모두 통과했다.

<a id="medium-catalog"></a>

## MEDIUM 벤치마크 목록

각 링크는 공용 periodic CLI가 읽는 설정이다.

| 벤치마크 | 원본 MEDIUM 매개변수 | 기본 자료형 |
|---|---|---|
| [correlation](../../../configs/periodic-polybench/correlation-medium.json) | M=240, N=260 | double |
| [covariance](../../../configs/periodic-polybench/covariance-medium.json) | M=240, N=260 | double |
| [2mm](../../../configs/periodic-polybench/2mm-medium.json) | NI=180, NJ=190, NK=210, NL=220 | double |
| [3mm](../../../configs/periodic-polybench/3mm-medium.json) | NI=180, NJ=190, NK=200, NL=210, NM=220 | double |
| [atax](../../../configs/periodic-polybench/atax-medium.json) | M=390, N=410 | double |
| [bicg](../../../configs/periodic-polybench/bicg-medium.json) | M=390, N=410 | double |
| [doitgen](../../../configs/periodic-polybench/doitgen-medium.json) | NQ=40, NR=50, NP=60 | double |
| [mvt](../../../configs/periodic-polybench/mvt-medium.json) | N=400 | double |
| [gemm](../../../configs/periodic-polybench/gemm-medium.json) | NI=200, NJ=220, NK=240 | double |
| [gemver](../../../configs/periodic-polybench/gemver-medium.json) | N=400 | double |
| [gesummv](../../../configs/periodic-polybench/gesummv-medium.json) | N=250 | double |
| [symm](../../../configs/periodic-polybench/symm-medium.json) | M=200, N=240 | double |
| [syr2k](../../../configs/periodic-polybench/syr2k-medium.json) | M=200, N=240 | double |
| [syrk](../../../configs/periodic-polybench/syrk-medium.json) | M=200, N=240 | double |
| [trmm](../../../configs/periodic-polybench/trmm-medium.json) | M=200, N=240 | double |
| [cholesky](../../../configs/periodic-polybench/cholesky-medium.json) | N=400 | double |
| [durbin](../../../configs/periodic-polybench/durbin-medium.json) | N=400 | double |
| [gramschmidt](../../../configs/periodic-polybench/gramschmidt-medium.json) | M=200, N=240 | double |
| [lu](../../../configs/periodic-polybench/lu-medium.json) | N=400 | double |
| [ludcmp](../../../configs/periodic-polybench/ludcmp-medium.json) | N=400 | double |
| [trisolv](../../../configs/periodic-polybench/trisolv-medium.json) | N=400 | double |
| [deriche](../../../configs/periodic-polybench/deriche-medium.json) | W=720, H=480 | float |
| [floyd-warshall](../../../configs/periodic-polybench/floyd-warshall-medium.json) | N=500 | int |
| [nussinov](../../../configs/periodic-polybench/nussinov-medium.json) | N=500 | int |
| [adi](../../../configs/periodic-polybench/adi-medium.json) | TSTEPS=100, N=200 | double |
| [fdtd-2d](../../../configs/periodic-polybench/fdtd-2d-medium.json) | TMAX=100, NX=200, NY=240 | double |
| [heat-3d](../../../configs/periodic-polybench/heat-3d-medium.json) | TSTEPS=100, N=40 | double |
| [jacobi-1d](../../../configs/periodic-polybench/jacobi-1d-medium.json) | TSTEPS=100, N=400 | double |
| [jacobi-2d](../../../configs/periodic-polybench/jacobi-2d-medium.json) | TSTEPS=100, N=250 | double |
| [seidel-2d](../../../configs/periodic-polybench/seidel-2d-medium.json) | TSTEPS=100, N=400 | double |
