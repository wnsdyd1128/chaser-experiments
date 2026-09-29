# 삼각형 루프 지원 반영 후 PolyBench MEDIUM 재검증

2026-09-29 실행. 원본 PolyBench/C 4.2.1의 MEDIUM 30종을 그대로 사용했다.
이전 결과는 [v1 기록](../polybench-medium-v1/README.md)에 보존한다.
[기계 판독 요약](summary.json) · [명령·로그·분석 증거](evidence.tar.gz)

- YARDA: `b33abc15ee48c40c645456715f2310ca583bad3b`.
- APE 서브모듈: `462ed4ed55edfa832c27d59fdb720bb28ee14fe5`.
- 원본·어댑터 네이티브 최종 출력 비교와 재초기화 후 반복 실행: **30/30 통과**.
- G/C/P RTEMS ELF 빌드·배열 배치 검사: **30/30 통과**.
- YARDA: **21종 통과, 9종 APE 차단**.
  네이티브·G·C·P 총 120개 중 84개 통과,
  36개 차단이며 각 벤치마크의 네 실행 상태는 동일하다.
- 공용 `sh scripts/verify`: **589개 통과, 3개 건너뜀**. 기존 sklearn 경고 1건.

## 이전 결과와의 차이

v1의 17종 통과·13종 차단에서 21종 통과·9종 차단으로 바뀌었다.
새로 통과한 사례는 correlation, covariance, gramschmidt, trmm다.
이전 성공 사례가 실패로 바뀌었는지는 아래 표와 요약의 이전 상태로 확인할 수 있다.

이번 변경은 `j = i`나 `j = i + 1`처럼 바깥 루프 변수에 의존하는 시작값을 처리한다.
Covariance의 `for (j = i; j < M; ++j)`와 Correlation의
`for (j = i + 1; j < M; ++j)`가 이 범위에 해당한다.

남은 차단 사례는 cholesky, durbin, lu, ludcmp, nussinov, symm, syr2k, syrk, trisolv다.
오류는 모두 `unresolved or unsupported region loop bound`다.
현재 APE의 `src/region/RegionLoopBounds.cpp::resolveLoopBounds()`는 종료 경계를
LLVM `ConstantInt`로 요구한다. SYRK의 `j <= i`, Nussinov의 `k < j`처럼
종료 경계가 바깥 루프 변수에 의존하는 경우는 아직 이 제약에 걸린다.
Nussinov는 이전의 시작값 해석 오류를 넘어섰지만 종료 경계에서 다시 차단됐다.
이는 해당 경계를 지원하면 전체 커널이 반드시 통과한다는 뜻은 아니다.

## 전체 결과

| 벤치마크 | 이전 YARDA | 이번 네이티브·G·C·P YARDA |
|---|---|---|
| 2mm | 통과 | 통과 |
| 3mm | 통과 | 통과 |
| adi | 통과 | 통과 |
| atax | 통과 | 통과 |
| bicg | 통과 | 통과 |
| cholesky | APE 차단 | APE 차단 |
| correlation | APE 차단 | 통과 |
| covariance | APE 차단 | 통과 |
| deriche | 통과 | 통과 |
| doitgen | 통과 | 통과 |
| durbin | APE 차단 | APE 차단 |
| fdtd-2d | 통과 | 통과 |
| floyd-warshall | 통과 | 통과 |
| gemm | 통과 | 통과 |
| gemver | 통과 | 통과 |
| gesummv | 통과 | 통과 |
| gramschmidt | APE 차단 | 통과 |
| heat-3d | 통과 | 통과 |
| jacobi-1d | 통과 | 통과 |
| jacobi-2d | 통과 | 통과 |
| lu | APE 차단 | APE 차단 |
| ludcmp | APE 차단 | APE 차단 |
| mvt | 통과 | 통과 |
| nussinov | APE 차단 | APE 차단 |
| seidel-2d | 통과 | 통과 |
| symm | APE 차단 | APE 차단 |
| syr2k | APE 차단 | APE 차단 |
| syrk | APE 차단 | APE 차단 |
| trisolv | APE 차단 | APE 차단 |
| trmm | APE 차단 | 통과 |

## 실행 방법과 증거 범위

공통 준비·분석 함수를 사용하되 독립적인 ELF 분석을 최대 8개씩 실행했다.
원본 크기·자료형·연산을 바꾸거나 APE가 생성한 루프·접근식을 수정하지 않았다.
각 분석 프로세스의 제한 시간은 600초다. 실행 스크립트는 압축 파일의
`rerun.py`, 전체 진행 로그는 `run.log`에 있다. 스크립트의 실행 위치는
`.cache/periodic-polybench/triangular-20260929/rerun.py`다.

기존 CLI로 같은 전체 범위를 순차 재검증할 수도 있다.

```sh
python3 -m tools.polybench_suite --periodic \
  --output .cache/polybench-medium-recheck --timeout 600
```

미지원 사례를 포함하므로 전체 실행은 종료 코드 1을 반환한다.
각 벤치마크의 생성 소스, 빌드·네이티브 검증 기록, APE 입력·오류,
YARDA 결과·명령·종료 상태·도구 해시를 압축 파일에 보존한다.
전체 ELF와 소스 스냅샷은 요약의 `full_snapshot` 경로에 있으며 압축 파일에는 넣지 않았다.
내부 `evidence-manifest.json`과 외부 `manifest.json`으로 파일 해시를 확인할 수 있다.

이번 실행은 분석기 재검증이며 RTEMS 시뮬레이터 시간 계측을 새로 수행하지 않았다.
YARDA 통과는 정상 종료와 모델의 접근 포괄성·횟수 보존 검사 통과를 뜻한다.
독립적인 동적 접근 추적 검증은 수행하지 않았으므로
`trace_validation: not-validated`, `dataset_eligible: false`를 유지한다.
