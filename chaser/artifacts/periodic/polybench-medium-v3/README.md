# 종속 종료 경계 지원 후 PolyBench MEDIUM 재검증

2026-09-29 실행. 원본 PolyBench/C 4.2.1의 MEDIUM 30종을 그대로 사용했다.
시작값 지원 단계의 결과는 [v2 기록](../polybench-medium-v2/README.md)에 보존한다.
[기계 판독 요약](summary.json) · [소스·명령·로그·분석 증거](evidence.tar.gz)

- YARDA: `a058a454d0979ed1987eac30a858d706d17317c3`.
- APE 서브모듈: `c9763015e15ba2d1d4fed3c5c74d80763afad7cc`.
- 원본·어댑터 네이티브 최종 출력 비교와 재초기화 후 반복 실행: **30/30 통과**.
- G/C/P RTEMS ELF 빌드·배열 배치 검사: **30/30 통과**.
- YARDA: **30/30종 통과**, 네이티브·G·C·P 합계
  **120/120개 분석 통과**.
- 공용 `sh scripts/verify`: **589개 통과, 3개 건너뜀**. 기존 sklearn 경고 1건.

## 이전 결과와의 차이

v2에서는 21종이 통과하고 9종이 APE의 종료 경계 해석에서 차단됐다.
이번에 새로 통과한 사례는 cholesky, durbin, lu, ludcmp, nussinov, symm, syr2k, syrk, trisolv다.
기존 성공 사례의 회귀는 0건이다.

이전에는 루프 종료 경계를 상수로 요구했다. 이번 변경은 바깥 루프 변수에 의존하는
아핀 종료 경계를 MAP에 보존하고, 실행 시 해당 바깥 루프 값으로 평가한다.
SYRK의 `j <= i`, TRISOLV의 `j < i`, Nussinov의 `k < j`가 이 범위에 해당한다.
이전의 Correlation·Covariance 시작값 지원도 계속 통과했다.

## 삼각형 반복 횟수의 별도 확인

네 사례는 분석기와 별개로 원본 C의 읽기·쓰기 횟수에서 유도한 수식과 대조했다.
`N*(N+1)/2`는 `j <= i`, `N*(N-1)/2`는 `j < i`의 전체 반복 횟수다.
후자는 `i=0`일 때 내부 루프를 실행하지 않는 경우도 포함한다.
호출부에서 읽는 전역 크기·스칼라 매개변수도 접근 수에 포함한다.
아래 수식과 네이티브·G·C·P의 결과가 모두 일치했다.

| 커널 | 예상 접근 수 수식 | 일치한 접근 수 |
|---|---|---:|
| durbin | `4 + 2*(N-1) + 7*N*(N-1)/2` | 559,402 |
| syr2k | `4 + N*(N+1)/2 * (2 + 6*M)` | 34,761,844 |
| syrk | `4 + N*(N+1)/2 * (2 + 4*M)` | 23,193,844 |
| trisolv | `1 + 5*N + 4*N*(N-1)/2` | 321,201 |

## 전체 결과

| 벤치마크 | 이전 YARDA | 이번 네이티브·G·C·P YARDA |
|---|---|---|
| 2mm | 통과 | 통과 |
| 3mm | 통과 | 통과 |
| adi | 통과 | 통과 |
| atax | 통과 | 통과 |
| bicg | 통과 | 통과 |
| cholesky | APE 차단 | 통과 |
| correlation | 통과 | 통과 |
| covariance | 통과 | 통과 |
| deriche | 통과 | 통과 |
| doitgen | 통과 | 통과 |
| durbin | APE 차단 | 통과 |
| fdtd-2d | 통과 | 통과 |
| floyd-warshall | 통과 | 통과 |
| gemm | 통과 | 통과 |
| gemver | 통과 | 통과 |
| gesummv | 통과 | 통과 |
| gramschmidt | 통과 | 통과 |
| heat-3d | 통과 | 통과 |
| jacobi-1d | 통과 | 통과 |
| jacobi-2d | 통과 | 통과 |
| lu | APE 차단 | 통과 |
| ludcmp | APE 차단 | 통과 |
| mvt | 통과 | 통과 |
| nussinov | APE 차단 | 통과 |
| seidel-2d | 통과 | 통과 |
| symm | APE 차단 | 통과 |
| syr2k | APE 차단 | 통과 |
| syrk | APE 차단 | 통과 |
| trisolv | APE 차단 | 통과 |
| trmm | 통과 | 통과 |

## 실행 방법과 증거 범위

공통 `prepare()`와 `analyze_source()`를 사용해 독립적인 ELF 분석을 최대 8개씩 실행했다.
원본 MEDIUM 크기·자료형·연산과 APE가 생성한 루프·접근식을 그대로 사용했다.
각 분석 프로세스의 제한 시간은 600초다. 실행 스크립트는 압축 파일의 `rerun.py`,
진행 로그는 `run.log`, 접근 수 대조는 `check_counts.py`와 `access-count-validation.json`에 있다.
로컬 실행 디렉터리는 `.cache/periodic-polybench/affine-bounds-20260929/`다.

기존 CLI로 같은 전체 범위를 순차 재검증할 수도 있다.

```sh
python3 -m tools.polybench_suite --periodic \
  --output .cache/polybench-medium-affine-bounds --timeout 600
```

각 벤치마크의 생성 소스, 빌드·네이티브 검증 기록, APE 입력,
YARDA 결과·명령·종료 상태·도구 해시를 압축 파일에 보존한다.
전체 ELF와 구현 스냅샷은 요약의 `full_snapshot` 경로에 있으며 압축 파일에는 넣지 않았다.
내부 `evidence-manifest.json`과 외부 `manifest.json`으로 파일 해시를 확인할 수 있다.

이번 실행에서는 RTEMS 시뮬레이터 시간 계측을 새로 수행하지 않았다.
YARDA 통과는 정상 종료와 모델의 접근 포괄성·횟수 보존 검사 통과를 뜻한다.
네 사례의 별도 접근 수 대조도 전체 동적 접근 순서 검증을 대신하지 않는다.
특히 Nussinov·Floyd–Warshall의 데이터 의존 분기가 실제로 선택하는 접근 순서는
독립적인 실행 추적과 비교해야 한다. 따라서 보고서의
`trace_validation: not-validated`, `dataset_eligible: false`는 유지한다.
