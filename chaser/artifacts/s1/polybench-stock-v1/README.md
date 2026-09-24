# PolyBench 계열 kernel: 수정하지 않은 Cachegrind와 YARDA CSRD

[그림](polybench-hit-rates.svg)은 같은 네 가지 host ELF의 kernel 함수에서
**시스템 설치 Valgrind Cachegrind 3.18.1**과 YARDA CSRD의 전체 data-cache hit 비율을
나란히 보여 준다. Cachegrind에는 패치나 kernel 진입 시 cache reset을 적용하지 않았다.
YARDA 수치는 S1 cold 실험에서 생성한 로컬 `suite.json`의 정적 분석 결과를
가져왔으며, 이 그림에는 다른 Cachegrind 실험의 측정값을 넣지 않았다.

| Kernel | Cachegrind 함수 접근 | YARDA 배열 접근 | Cachegrind hit | YARDA CSRD hit |
|---|---:|---:|---:|---:|
| 2mm | 49,025 | 49,024 | 99.674% | 99.125% |
| atax | 8,466 | 8,465 | 100.000% | 96.598% |
| gemm | 32,801 | 32,800 | 100.000% | 99.085% |
| jacobi | 86,642 | 86,640 | 100.000% | 99.077% |
| 접근 수 가중 합계 | 176,934 | 176,929 | 99.910% | 98.973% |

각 열의 hit 비율은 `1 − LLC data misses / data accesses`다. Cachegrind는 프로그램
전체의 명령어·데이터 접근을 시뮬레이션하고, 그림에는 그중 **kernel 함수에 귀속된**
`Dr+Dw`와 `DLmr+DLmw`를 집계했다. 함수에 귀속된 비배열 접근도 제외하지 않았다.
YARDA는 kernel의 **전역 배열 load/store** 176,929건만 분석한다. 따라서 두 열의
분모와 대상 접근이 다르며, 막대 간 차이를 YARDA의 예측 오차나 정확도로 해석할 수 없다.

또한 Cachegrind 실행에서는 배열 초기화가 kernel보다 먼저 일어나므로 kernel 진입 시
cache가 이미 채워져 있을 수 있다. YARDA의 수치는 빈 cache에서 전역 배열 접근열을
분석한 결과다. 이 그림은 이런 실험 조건 차이를 포함한 **원본 도구 결과의 비교**다.
Y축은 0%에서 시작하고, 각 막대 위에 실제 비율을 적었다. atax의 두 값 차이는
3.402%p다. 이 실험은 실제 GR740의 hardware counter를 측정하거나 공식
PolyBench/C 배포본을 실행한 결과가 아니다.

로컬 `summary.json`에 Cachegrind 실행 명령, 도구·ELF·원시 출력 hash 및
집계 count를, 로컬 `results.csv`에 그림의 수치를 보존했다. 각 kernel의
`cachegrind.out.gz`, `cachegrind.stderr.txt`, `stdout.txt`는 수정하지 않은
Cachegrind의 실행 기록이다. `cachegrind.out.gz`의 함수 통계는 그래프 생성 시 다시
집계해 summary와 대조한다. 두 도구 모두 16 KiB 4-way 32 B L1과 2 MiB 4-way
32 B LL 구성을 사용했다.

JSON·CSV·gzip·ELF 실행 근거는 Git에 포함되지 않는다. 저장소의 C 소스에서
새 suite를 만들고 수정하지 않은 Cachegrind로 재측정·그림을 생성하려면
workspace root에서 실행한다. 첫 단계에만 P1 실험용 패치된 Cachegrind가 필요하며,
설치 방법은 [P1 재현 설명](../polybench-cold-v1/README.md#재현)을 따른다.

```sh
python3 -m tools.run_s1_polybench \
  --source-dir artifacts/s1/polybench-cold-v1/sources \
  --cold-prefix /tmp/chaser-cg-cold-install \
  --output /tmp/chaser-polybench-cold-replay
python3 -m tools.run_s1_polybench_stock \
  /tmp/chaser-polybench-cold-replay/suite.json \
  --output /tmp/chaser-polybench-stock-replay
python3 -m tools.plot_s1_polybench_hits \
  /tmp/chaser-polybench-cold-replay/suite.json \
  /tmp/chaser-polybench-stock-replay/summary.json \
  --output /tmp/chaser-polybench-stock-replay
```

Runner는 동결된 ELF의 byte hash와 checksum을 확인하고 실행 가능한 임시 사본을
만든다. 첫 단계의 `suite.json`은 YARDA 결과와 ELF의 출처이며,
두 번째 단계의 Cachegrind 실행에는 cache reset을 적용하지 않는다.
