# PolyBench MEDIUM 검증 결과

2026-09-28 실행. 원본 PolyBench/C 4.2.1 리비전
`3e872547cef7e5c9909422ef1e6af03cf4e56072`의 전체 30종을 검사했다.
[예제·사용법](../../../rtems/periodic/polybench/README.md) ·
[기계 판독 결과](summary.json) · [로그·분석 증빙](evidence.tar.gz)

- 원본/어댑터 네이티브 출력 비교 및 재초기화 후 반복 실행: **30/30 통과**.
- G/C/P RTEMS ELF 빌드와 전역 배열 배치 검사: **30/30 통과**.
- YARDA 네이티브/G/C/P 실행: **17종 통과, 13종 APE 전처리 차단**.
- ATAX MEDIUM 실제 P 시뮬레이터 실행: **1/1 성공**, 두 작업 모두 체크섬
  `1921650095`; 저장된 원시 결과의 `load_batch` 재검증도 통과했다.
- 프로젝트 검증 `sh scripts/verify`: 586개 통과, 3개 건너뜀. 이후 회귀 테스트
  추가와 빌드 경고 격리 수정 후 전체 `pytest`: **589개 통과, 3개 건너뜀**.
  두 실행 모두 기존 sklearn 경고 1건이 있었다.

YARDA의 `passed`는 프로세스 정상 종료와 생성된 모델의 접근 포괄성·횟수 보존
검사를 의미한다. 전체 동적 메모리 접근 추적의 독립 검증은 수행하지 않았으며
`trace_validation: not-validated`, `dataset_eligible: false`를 유지한다.
특히 데이터 의존 분기가 있는 Floyd–Warshall의 MAP은 실제 분기별 접근을
별도로 검증해야 한다. APE가 차단한 13종은 백엔드 입력을 생성할 수 없어
`yarda_cpp` 실행 성공으로 세지 않았다.

## 재현

```sh
python3 -m tools.polybench_suite --periodic \
  --output .cache/polybench-medium-validation --timeout 600
```

13종의 전처리 오류가 포함되므로 전체 명령의 종료 코드는 1이다. 세 선형 시스템 풀이 커널의
원본 들여쓰기 경고를 워크로드 전용 옵션으로 격리한 후 Cholesky/LU/LUDCMP를
재검증한 결과를 반영했다. 최초 실행 상한은 120초였으며 Floyd–Warshall은
네이티브/G/C/P 모두 시간 초과였다. 같은 MAP·ELF를 600초 상한으로 다시 실행해
네 경우 모두 약 191–193초에 완료했다. 원래 시간 초과와 추가 실행 로그를 모두
보존했다. 설치된 YARDA의 정확한 바이너리 해시와 버전은 각 분석 보고서에 있다.

ATAX 시뮬레이터 검증은 MEDIUM 크기를 유지하고 `period_ticks=2000`,
`horizon_ticks=4000`, `warmup_ticks=2000`으로 실행했다. 프로젝트 문서의
`DISPLAY=165.246.44.80:90.0`을 사용했다. 다른 29종의 시뮬레이터 실행을
완료했다고 주장하지 않는다.

## 결과 목록

YARDA 열은 네이티브 및 G/C/P 네 경우의 최종 실행 상태다.

| 벤치마크 | 네이티브 출력 | G/C/P 빌드 | YARDA | 제한·추가 검증 |
|---|---|---|---|---|
| 2mm | 통과 | 통과 | passed |  |
| 3mm | 통과 | 통과 | passed |  |
| adi | 통과 | 통과 | passed |  |
| atax | 통과 | 통과 | passed |  |
| bicg | 통과 | 통과 | passed |  |
| cholesky | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| correlation | 통과 | 통과 | blocked | 루프 귀납 변수를 해석할 수 없음 |
| covariance | 통과 | 통과 | blocked | 루프 귀납 변수를 해석할 수 없음 |
| deriche | 통과 | 통과 | passed |  |
| doitgen | 통과 | 통과 | passed |  |
| durbin | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| fdtd-2d | 통과 | 통과 | passed |  |
| floyd-warshall | 통과 | 통과 | passed | 600초 상한 재검증; 원래 120초 시간 초과 |
| gemm | 통과 | 통과 | passed |  |
| gemver | 통과 | 통과 | passed |  |
| gesummv | 통과 | 통과 | passed |  |
| gramschmidt | 통과 | 통과 | blocked | 루프 귀납 변수를 해석할 수 없음 |
| heat-3d | 통과 | 통과 | passed |  |
| jacobi-1d | 통과 | 통과 | passed |  |
| jacobi-2d | 통과 | 통과 | passed |  |
| lu | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| ludcmp | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| mvt | 통과 | 통과 | passed |  |
| nussinov | 통과 | 통과 | blocked | 루프 귀납 변수를 해석할 수 없음 |
| seidel-2d | 통과 | 통과 | passed |  |
| symm | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| syr2k | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| syrk | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| trisolv | 통과 | 통과 | blocked | 영역 내 루프 경계를 해석할 수 없거나 지원하지 않음 |
| trmm | 통과 | 통과 | blocked | 루프 귀납 변수를 해석할 수 없음 |

## 증빙 범위

`evidence.tar.gz`에 각 사례의 빌드 manifest·로그, 원본 비교 결과, APE/YARDA
명령·종료 코드·시간·로그·MAP·성공 시 캐시 계층 분석 JSON, ATAX 원시 실행 기록,
프로젝트/pytest 로그를 보존했다. 내부 `evidence-manifest.json`은 압축 해제한
파일들의 SHA-256을 기록한다. 외부 `manifest.json`은 이 요약·설명·압축 파일을
검증한다.

이는 핵심 증거를 모은 자료이며, ELF와 전체 구현 스냅샷을 포함해 독립적으로
재실행할 수 있는 묶음은 아니다. 검증 당시 전체 스냅샷 경로는 `summary.json`의
`full_snapshot`에 기록했다. 새로운 머신에서는 위 명령으로 다시 준비한다.
