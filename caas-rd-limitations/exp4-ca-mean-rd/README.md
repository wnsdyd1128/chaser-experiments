# Exp4: CA Mean-RD Limitation

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

`CA = T / (T + P) = 1 / (1 + mean RD)` 이므로 CAAS의 CA 지표는 재사용
히스토그램의 **가중평균 하나**로만 결정된다. 평균이 같고 모양이 다른 두
워크로드를 만들면 CA는 같은데 캐시 동작은 갈라진다.

- **A — 모든 재사용이 멀다**: 주소 D개를 한 번씩 순환 접근한다. 모든 재사용이
  `RD = D - 1`에 놓인다.
- **B — 대부분의 재사용이 즉시다**: 주소 D개를 각각 연달아 k번 읽고 순환한다.
  재사용의 `(k-1)/k`가 `RD = 0`에 놓이고 나머지가 `RD = D - 1`에 놓인다.

D와 k를 맞추면 두 평균이 정확히 같아진다. laysim으로 측정한 두 케이스는
`K1D1023`(D=1023, k=1)과 `K4D4095`(D=4095, k=4)이며, 둘 다 **mean δ = 1022,
CA = 9.78e-4**다.

## 측정 경로

세 경로가 서로 다른 것을 재고, 서로를 검증한다.

**1. laysim 시간 축** — GR740에서 job 시간을 직접 잰다.

```sh
make -f Makefile.rtems -C exp4-ca-mean-rd
script -q -c "make -f Makefile.rtems -C exp4-ca-mean-rd run" results/exp4_time_domain.log
tools/parse_results.py results/exp4_time_domain.log -o results/exp4_time_domain.csv
tools/plot_ca_mean_rd.py
```

**2. cachegrind miss 축** — 같은 접근 패턴의 호스트 빌드에 GR740 캐시 형상을
명령줄로 강제해 miss rate를 잰다. 재사용 거리 곡선이 모델의 읽기라면, 이쪽은
캐시가 실제로 한 일이다.

```sh
make -C exp4-ca-mean-rd
tools/run_exp4_cachegrind.sh
tools/plot_exp4_measured_miss.py
```

**3. synthetic RDH와 소스 수준 재현** — 히스토그램을 직접 구성하거나, C
워크로드를 YARDA와 CASA에 태운다.

```sh
tools/plot_ca_mean_rd_limitation.py
tools/run_ca_mean_rd_c_repro.py
```

## 결과

| | A (`K1D1023`) | B (`K4D4095`) |
|---|---:|---:|
| 재사용 히스토그램 | δ=1022가 100% | δ=0이 75%, δ=4094가 25% |
| mean δ | 1022 | 1022 |
| CA | 9.78e-4 | 9.78e-4 |
| working set | 31 KiB | 127 KiB |
| **L1 read miss (cachegrind)** | **99.6%** | **24.9%** |
| LRU 모델 예측 | 100.0% | 25.0% |
| **laysim ns/access** | **128.4** | **89.2** |
| exp3 곡선 환산 stall | 13.1 cycles/reuse | 3.3 cycles/reuse |

CA가 소수점까지 같은 두 워크로드가 L1 miss에서 4배, 실측 시간에서 1.44배
갈라진다. B는 working set이 4배 크면서도 더 빠르다.

두 워크로드의 L1 상주 대조 케이스(`K1D384`, `K4D384`)는 76.4와 76.2
ns/access로 0.225% 안에서 일치한다. 명령어 경로가 같다는 뜻이고, 그래서 위
시간 차이를 메모리 몫으로 읽을 수 있다.

## 그림 캡션

**Fig. (reuse-distance curve).** `results/exp4_mean_rd_mrc`. 재사용 거리
분포의 생존함수 `S(δ) = P(재사용 거리 ≥ δ)`다. 비음수 확률변수의 생존함수
적분이 평균이므로 **곡선 아래 면적이 곧 mean δ**이고, 그것이 CA가 읽는 유일한
값이다. 두 면적은 같고 모양은 전혀 다르다. LRU 모델에서는 c 라인 캐시가
`δ ≥ c`인 재사용을 정확히 미스하므로, 점선(L1 512 라인)에서의 높이가 L1 miss
비율로 읽힌다. 범례의 stall 값은 exp3에서 측정한 "재사용 거리 하나의 비용"
곡선을 각 히스토그램에 가중평균한 것이다.

**Fig. (measured miss).** `results/exp4_measured_miss`. 같은 두 접근 패턴을
호스트 빌드로 옮겨 cachegrind에 GR740 형상(L1 16 KiB, 4-way, 32 B 라인)을
강제해 잰 L1 read miss 비율이다. 막대가 측정값, 검은 가로선이 위 곡선의 LRU
모델 예측이다. 모델과 측정이 0.4%p 안에서 일치하므로, 곡선의 높이를 miss
비율로 읽는 것이 이 워크로드에서 정당함을 확인해 준다.

## 범위

miss 축의 모델과 측정은 서로 다른 가정을 갖는다. 곡선은 완전연관 LRU를
가정하고, cachegrind는 4-way 연관도를 모델링한다. 이 워크로드는 순차 stride
접근이라 두 값이 거의 같지만, 충돌 미스가 있는 패턴에서는 갈라질 수 있다.
또 cachegrind는 SPARC 바이너리가 아니라 같은 접근 패턴의 호스트 빌드를
실행한다. 이전되는 것은 접근 패턴과 명령줄로 강제한 캐시 형상이고, SPARC ISA와
메모리 컨트롤러 타이밍은 이전되지 않는다.

## 산출물

```text
results/exp4_time_domain.log / .csv             laysim 원본과 파싱 결과
results/exp4_mean_rd_mrc.png / .pdf             재사용 거리 생존함수
results/exp4_mean_rd_cost.png / .pdf            측정 시간의 메모리 몫 분해
results/exp4_cachegrind.csv                     cachegrind 실측 miss rate
results/exp4_measured_miss.png / .pdf           실측 miss와 모델 예측 대조
results/ca_mean_rd_limitation.csv / .md         synthetic RDH 표
results/ca_mean_rd_limitation_rdh.png / .pdf    synthetic RDH 그림
results/ca_mean_rd_limitation_metrics.png / .pdf
results/ca_mean_rd_c_repro/                     YARDA + CASA 소스 재현
```
