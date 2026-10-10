# 논문 4장 그림 4.1–4.5와 TET 표

[`figures/thesis_ch4.py`](../figures/thesis_ch4.py)가 저장된 결과 묶음과 `core-load-runs.csv`에서 만든다. `scheduler-comparison-v1`에서 실행한다.

```sh
python3 figures/thesis_ch4.py thesis-ch4
```

그림은 본문 폭 16 cm로 그린다. 글자 크기는 인쇄 크기 그대로다(본문 8 pt, 눈금·범례 7.5 pt, 값 표시 7 pt).
각 그림은 `png`(300 dpi), `pdf`, `svg`와 그린 값을 담은 `csv`로 저장한다.
색은 색각 이상에도 구분되는 Okabe-Ito palette(Wong, Nature Methods 8:441, 2011)이고, 흑백 인쇄를 위해 빗금을 함께 쓴다.
그림 안에는 그림 제목과 아래 설명 문장을 넣지 않았다. 설명은 논문 캡션에 둔다.

| 파일 | 내용 | 입력(실험) |
|---|---|---|
| `figure-4-1.*` | 공유 L2 탐침: 동시 task 수에 따른 접근당 CPU 시간. (a) 32 KiB·3 MiB 배열, (b) 512·640·768 KiB 배열. 점선은 48 ns × task 수와 220 ns × task 수 기준선 | [`results/l2-probe/probe.json`](../results/l2-probe/probe.json) (8절) |
| `figure-4-2.*` | 32 KiB 저-CLS task가 U의 50%인 set: Partitioned 배치 4종의 부하별 모든 마감을 지킨 set 수, 주기 CV 0과 0.2 | [`results/small-memory-load/results.jsonl`](../results/small-memory-load/results.jsonl) (24절) |
| `figure-4-3.*` | 같은 task, 부하 0.5에서 모든 마감을 지킨 run: 묶은 저-CLS task가 있는 코어와 다른 코어의 계획 U와 실제 U(run 중앙값) | [`core-load-runs.csv`](core-load-runs.csv) (24절 원자료) |
| `figure-4-4.*` | CLS(차이 ≤ 0.005)와 목표 U를 맞추고 메모리 비용만 다른 짝: 부하별 모든 마감을 지킨 set 수(L2 적중 대 메모리 접근), U 균형(WFD)과 CLS 균형 묶음 | [`results/memory-cost-analysis/memory-cost.json`](../results/memory-cost-analysis/memory-cost.json) (41절) |
| `figure-4-5.*` | 같은 run: task 종류별 늦은 job이 있었던 task 관측의 비율 | 위와 같음 (41절) |
| `table-4-tet.{md,csv}` | release-aware 대비 "release-aware 안의 CLS 묶음"의 짝지은 TET 차이(4.3절 본문 근거) | `results/small-memory-load/stats-small-memory-load.json` (24절), `results/task-count/stats-task-count.json` (20절) |
| `core-load-runs.csv` | 그림 4.3의 run별 값: 24절의 `cv00-low50`·`cv20-low50`, 부하 0.5·0.55, CLS 묶음 배치 2종 | `.cache/small-memory-load-v1`(원자료, 삭제 목록에 있음) |

`core-load-runs.csv`는 [`figures/thesis_ch4_core_load.py`](../figures/thesis_ch4_core_load.py)가 원자료에서 한 번 뽑았다. 원자료를 지운 뒤에도 그림 4.3을 다시 그릴 수 있도록 값을 남긴다.

```sh
python3 figures/thesis_ch4_core_load.py $W/.cache/small-memory-load-v1 thesis-ch4/core-load-runs.csv
```

## 캡션과 본문에 밝힐 집계 기준

- **그림 4.1:** 48 ns와 220 ns는 관측에 맞춘 기준선의 계수다. 단일 접근 지연을 직접 잰 값이 아니다. 512 KiB × 4는 정확히 2 MiB이므로 (b)는 "용량에 이르거나 넘는" 배열이다.
- **그림 4.2:** Partitioned 배치는 모두 시작에 성공했다(스크립트가 확인한다). G·C 배치는 넣지 않았다.
- **그림 4.3:**
  - task는 처음 마감을 넘기면 이후 job을 실행하지 않는다(`rtems/periodic/init.c`). 그래서 모든 마감을 지킨 run만 썼다. run 수는 막대 아래에 적었다.
  - 실제 U는 측정 구간(준비 구간 뒤)의 job CPU 시간 합을 구간 길이로 나눈 값이다. run마다 코어 무리별 평균을 구하고 run 중앙값을 그렸다.
  - 마감을 놓친 시점의 부하를 보인 것은 아니다.
  - 부하 0.55에서는 막대마다 18개 중 2–7개 run만 모든 마감을 지켜 넣지 않았다(`core-load-runs.csv`에는 있다).
- **그림 4.4:**
  - 95쌍은 기본 set 24개를 네 부하에서 반복한 짝이라 서로 독립이 아니다. 그래서 그림에는 p값을 넣지 않았다.
  - 41절에서 사전 등록한 검정은 95쌍을 합친 exact McNemar다(Holm p < 0.0001).
  - 독립 단위로 다시 본 값(2026-10-09 계산, 결과 묶음에는 없음):
    - set 단위: 배치마다 24개 set 중 23개에서 L2 적중 쪽만 지킨 부하가 있었고, 반대는 0개였다. 부호 검정 p = 2.4 × 10⁻⁷이다.
    - 부하별 exact McNemar에 8개 비교의 Holm 보정: 부하 0.55에서 WFD 0.0195, CLS 묶음 0.00293. 부하 0.6에서 둘 다 1.9 × 10⁻⁶. 부하 0.45·0.5는 유의하지 않다.
- **그림 4.5:**
  - 분모는 고유 task 수가 아니다. 각 run에서 task를 한 번씩 세고, 4개 부하와 24개 set을 합한 관측 수다.
  - 분자는 준비 구간을 포함해 늦은 job이 한 번 이상 있었던 관측 수다.
  - 시작에 실패한 run은 조건마다 빼서 두 조건의 분모가 다르다.
  - 비교는 비율로 한다. 예를 들어 저-CLS task가 없는 코어는 WFD 55/513(10.72%), CLS 묶음 106/1000(10.60%)이다.
- **TET 표:** TET 차이는 (release-aware 안의 CLS 묶음 − release-aware) ÷ release-aware이고, 두 배치가 모두 마감을 지킨 set끼리 짝지었다. Holm 보정은 각 실험 통계 파일에서 같은 짝·지표의 칸 전체에 적용했다.

기존 결과 묶음과 실험별 그림 스크립트(`figures/small_memory_load_bars.py`, `cv_miss_bars.py`, `memcost_bars.py`)는 바꾸지 않았다.
