# PolyBench 계열 kernel과 cold Cachegrind 비교 (S1 외부 확인)

첨부 그림과 같은 miss-count 막대 비교를 수행한 **host 실험**이다. 입력은 공식
PolyBench/C 4.2.1 원본 실행 파일이 아니라, 기존 로컬 CAAS 프로젝트의 고정 크기
PolyBench **계열 C 예제** 5개다. 실험 입력 소스는 [`sources/`](sources/)에 두고,
SHA-256은 [`tools/run_s1_polybench.py`](../../../tools/run_s1_polybench.py)의 `SOURCE_HASHES`에 고정했다.
공식 suite의 크기·할당·최적화 결과 또는 CASA 논문 수치를 재현했다는 주장은 하지 않는다.
공식 배포의 출처는 [PolyBench/C SourceForge](https://sourceforge.net/projects/polybench/files/)다.
본 실험의 코드는 위 로컬 예제에서 파생됐고 관련 재배포 고지는
[`sources/POLYBENCH-LICENSE.txt`](sources/POLYBENCH-LICENSE.txt)에 둔다.

| Kernel | 배열 접근 수 | Cachegrind L1 miss | YARDA CSRD L1 miss | Cachegrind LLC miss | YARDA CSRD LLC miss |
|---|---:|---:|---:|---:|---:|
| 2mm | 49,024 | 429 | 429 | 429 | 429 |
| atax | 8,465 | 288 | 288 | 288 | 288 |
| gemm | 32,800 | 300 | 300 | 300 | 300 |
| jacobi | 86,640 | 7,800 | 7,800 | 800 | 800 |

선정된 **4개 kernel × 2개 cache level의 miss count 8쌍이 모두 일치**했다.
최대 절대오차는 0 miss이며, 네 kernel의 전역 배열 접근 176,929건도 Lackey와 YARDA의
`(load/store, 주소, 크기)` 순서까지 일치했다. 0% MAPE 대신 이 범위와 원시 count를 표시한다.
표본이 작고 전역 배열 접근열과 cache 구성을 통제한 비교이므로, 이 일치는 일반적인 PolyBench 전체나
실제 하드웨어에서의 예측 정확도를 뜻하지 않는다. [그래프](polybench-cachegrind.svg)와
위 표는 저장소에 포함된다. 세부 집계와 원시 근거는 로컬 `suite.json` 및 case별
출력에 있다. 원래 실행의 `results.csv`와 `manifest.json`도 로컬 전용이다.
Global RD도 이 네 사례에서는 CSRD와 같은 count다. 따라서 이 그림은 분석·실행·Cachegrind
비교 경로가 일치하는지 보여 주지만, Global RD 대비 CSRD의 개선을 입증하지는 않는다.

## 비교 범위와 통제

1. 복사한 각 C 예제의 전역 배열을 `volatile`로 지정하고 kernel에 `noinline`과
   `ape.analyze`를 붙였다. Kernel 계산·반복 순서·고정 크기는 유지했다.
   Kernel 뒤의 checksum은 분석 범위 밖이며, 같은 소스를 `volatile` 없이 빌드한
   기준 실행과 수치 결과가 일치함을 확인했다. 생성 C와 기준 C는 case별로 저장소에,
   host ELF와 APE는 로컬 실행 결과에 보존했다.
2. **바로 그 host ELF**를 YARDA에 넘겼다. Clang 14 `-O1` host 실행과 Clang 14 `-O0`
   + `mem2reg` APE 생성의 접근 차이는 Valgrind Lackey 주소열로 검증했다.
   Kernel 함수 PC와 네임드 전역 배열의 ELF symbol 범위로 필터링한
   `(load/store, 절대주소, byte 크기)` 전 순서가 네 case 모두 일치했다.
   Valgrind 3.18.1의 `### unhandled dwarf2 abbrev form code` 진단 줄만 trace 파싱에서 제외했다.
3. 별도 패치된 Cachegrind 3.18.1은 kernel 첫 명령 직전에 I1·D1·LL tags를 한 번 비운다.
   16 KiB 4-way 32 B D1과 2 MiB 4-way 32 B LL을 사용했다. 이후에는 stack·instruction·
   라이브러리를 포함한 **전체 traffic**을 simulation한다. Reset 로그와 도구 hash를 보존했다.
4. Cachegrind 함수 통계의 `Dr+Dw`에서 디버그 정보가 kernel 선언/닫는 중괄호에 귀속시킨
   **비배열 stack 접근**만 사후 제외했다: 2mm 줄50 1건, atax 줄43 1건, gemm 줄41 1건,
   jacobi 줄21·50 각1건. 소스 줄 `0`의 data 접근은 2mm·gemm에서 실제 배열 접근이므로
   보존했다. 선택된 `Dr+Dw`가 Lackey와 YARDA의 전체 배열 접근 수와 일치하지 않으면 실패한다.
   L1 miss=`D1mr+D1mw`, LLC miss=`DLmr+DLmw`로 계산했다.

이 조정은 Cachegrind simulation 전의 주소 필터가 아니다. 제외한 stack 접근도 cache 상태에
영향을 줄 수 있다. 실측은 Cachegrind가 재현한 **host cache model**이며 GR740의 write policy,
RTEMS scheduler/interference 또는 hardware counter는 검증하지 않는다.
`volatile`과 고정 크기 배열은 일반적인 PolyBench 최적화 실행과 다른 접근 집합을 만든다.
이번 네 작은 입력에서는 Global RD와 CSRD가 같아 set conflict 차이를 시험하지 못했다.
앞으로 더 큰 입력을 평가할 때는 결과를 본 뒤 크기를 골라 튜닝하지 않고 먼저 suite를 고정해야 한다.
PolyBench는 주 데이터셋의 패턴 생성·θ/RF 학습·validation 튜닝에는 사용하지 않는다.

## Correlation 제외

다섯 번째 `correlation`은 정직하게 실패 사례로 남겼다. 원래 삼각 반복
`for (j=i; j<N; j++)`는 현재 YARDA APE frontend에서 `unsupported affine index:
unresolved loop IV`로 거부된다. `j=0..N`에 `if(j<i) continue`를 넣은 등가 C 제어 흐름은
APE를 만들 수 있었지만, YARDA 88,400 접근과 Lackey 51,499 접근의 순서가 처음
2,511번째에서 달랐다. 따라서 Cachegrind 막대를 그리거나 위 일치 건수에 넣지 않았다.
원래 소스와 guard 변형은 저장소에, APE events·Lackey 원본과 최초 불일치는
원래 실험의 로컬 `excluded-correlation/exclusion.json`에 보존했다.
이는 분석기 적용 범위/APE 제어 흐름 지원의 한계다.

## 재현

YARDA plugin·`yarda_cpp`는 `sh scripts/verify`로 준비한다.
패치된 Cachegrind 빌드는 [`tools/cachegrind/README.md`](../../../tools/cachegrind/README.md)를 따른다.
새 출력 디렉터리를 지정한다.

```sh
python3 -m tools.run_s1_polybench \
  --source-dir artifacts/s1/polybench-cold-v1/sources \
  --cold-prefix /tmp/chaser-cg-cold-install \
  --output rtems/s1/build/polybench-cold-new
python3 -m tools.plot_s1_polybench rtems/s1/build/polybench-cold-new/suite.json \
  --output rtems/s1/build/polybench-cold-new/plot
```

원시 Lackey와 Cachegrind 출력, YARDA events/results, symbol, ELF, checksum과
실행 명령은 case별 gzip/JSON으로 **로컬에만** 보존한다. JSON·CSV·gzip·ELF는
Git에 포함되지 않는다. 원래 실행의 `manifest.json` 역시 로컬 근거이며 저장소의
그림을 그린 과거 실행을 독립적으로 재집계하려면 이 파일들이 필요하다. 위 재현 명령은 저장소의
고정 C 소스에서 새 suite와 근거를 생성한다. 원본 `sources/`의 5개 소스는 고정 참조이며
이번 평가의 수치 표본은 4개뿐이다.
