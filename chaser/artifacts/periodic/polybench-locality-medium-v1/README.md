# PolyBench MEDIUM 5종 locality 분석

2026-09-29에 원본 PolyBench/C 4.2.1 리비전
`3e872547cef7e5c9909422ef1e6af03cf4e56072`의 2mm, atax, correlation,
gemm, jacobi-2d를 분석했다. 원본 커널 연산과 MEDIUM 크기를 유지하는 기존
어댑터를 사용했다. 각 원본·어댑터의 최종 출력이 같은지 네이티브 실행으로 검증한 뒤,
Clang 14 O0 APE와 같은 소스의 네이티브 ELF로 `yarda_cpp`를 실행했다.

[기계 판독 요약](summary.json) · [입력·ELF·원시 출력·로그](evidence.tar.gz) ·
[파일 해시](manifest.json)

| 커널 | 모델 접근 수 | CAAS-CA (원소) | CA (라인 Global RD) | CA (L1 CSRD) | L1 최초 적중 | LLC 최초 적중 | 전체 미스 | CLS (α=0.5) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2mm | 58,937,406 | 9.58518e-5 | 0.00140131 | 0.158345 | 93.6978% | 6.2202% | 0.0820% | 0.942476 |
| atax | 1,280,002 | 0.00189070 | 0.0308594 | 0.859210 | 96.8486% | 0.0045% | 3.1469% | 0.968490 |
| correlation | 30,852,123 | 9.48233e-5 | 0.00112140 | 0.0995449 | 51.3917% | 48.5107% | 0.0976% | 0.556795 |
| gemm | 42,328,005 | 7.44450e-5 | 0.00119112 | 0.133990 | 93.7087% | 6.2058% | 0.0855% | 0.942572 |
| jacobi-2d | 73,804,802 | 1.87702e-6 | 0.000379204 | 0.0467845 | 91.5653% | 8.3923% | 0.0423% | 0.923071 |

Correlation은 다섯 커널 중 LLC 최초 적중 비중이 가장 높다(48.51%).
2mm와 GEMM의 CLP는 가깝지만 L1 CSRD CA는 각각 0.1583과 0.1340이다.
CA와 CLP는 서로 다른 정의의 값이므로 CA를 적중률로 읽으면 안 된다.

## 지표와 입력

캐시 설정은 [`rtems/baseline/cache.yaml`](../../../rtems/baseline/cache.yaml)의
코어 0 경로다: 16 KiB·4-way·32 B L1, 2 MiB·4-way·32 B LLC, LRU.
각 태스크의 빈 캐시에서 시작하는 요구 접근 모델이다. CAAS-CA는 원소 Global RD,
라인 CA는 캐시 라인 Global RD, CA-CSRD는 L1 CSRD 히스토그램에 동일한
`sum(count) / (sum(count) + sum(distance × count))`를 적용한다. 세 CA는 최초
접근을 제외한다. CLP의 세 성분은 공통 모델 접근 수를 분모로 쓰며 순서는
L1 최초 적중·LLC 최초 적중·전체 미스다. CLS는
`p_L1 + (16 KiB / 2 MiB)^α × p_LLC`다. `summary.json`에는 α=0, 0.3, 0.5,
0.7, 1.0의 CLS를 모두 보존했다.

사용한 YARDA는 `a058a454d0979ed1987eac30a858d706d17317c3-dirty`, 모델은
`exact-two-level-lru-demand-v1`이다. 분석기 바이너리·APE 플러그인·캐시 YAML,
각 소스·APE·ELF·분석 출력의 SHA-256은 `summary.json`과 각 `case.json`에 있다.
`evidence.tar.gz`는 워크로드별 소스, 네이티브 검증 기록, ELF, APE,
YARDA 원소·라인·계층 JSON, 명령과 로그를 담는다.

## 재실행과 검증

워크스페이스 루트에서 현재 YARDA 소스를 빌드하고 **새 출력 경로**를 지정한다.

```sh
cmake --build rtems/baseline/build/yarda --target MemoryAccessPatterns yarda_cpp -j 4
for benchmark in 2mm atax correlation gemm jacobi-2d; do
  python3 -m chaser.periodic.polybench.locality_experiment "$benchmark" \
    --output ".cache/periodic-polybench/locality-medium-rerun/$benchmark" --timeout 600
done
```

각 커널에서 원본·어댑터 출력 일치, YARDA 접근 포괄성·보존 불변식,
두 계층 실행의 L1/LLC/미스 횟수 일치를 확인했다. 다섯 `case.json`의 CA와 CLS를
원시 히스토그램·비율에서 다시 계산했고, 모든 CLP 성분 합은 1이다.
`sh scripts/verify` 결과는 **591 passed, 1 skipped, 1 warning**이었다.

이 값은 네이티브 ELF에 대한 모델의 단일 태스크 지역성이다. 실제 GR740 캐시
카운터, RTEMS G/C/P 간섭 또는 TET/TAT 측정값은 아니다. YARDA 접근 순서를
독립적인 동적 추적으로 검증하지 않았고, 각 `case.json`의
`trace_validation`은 `not-validated`, `dataset_eligible`은 `false`다.
