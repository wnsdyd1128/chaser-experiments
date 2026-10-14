# 논문 6장 그림 6.1–6.12와 사후 분석

[`figures/thesis_ch6.py`](../figures/thesis_ch6.py)가 저장된 결과 묶음과 `kernel-inflation-tasks.csv`에서 그림을 만든다.
[`figures/thesis_ch6_posthoc.py`](../figures/thesis_ch6_posthoc.py)는 본문에 쓰는 기본 집합 단위 사후 분석을 계산한다(`posthoc.md`, `posthoc.json`).
둘 다 `scheduler-comparison-v1`에서 실행한다.

```sh
python3 figures/thesis_ch6.py thesis-ch6
python3 figures/thesis_ch6_posthoc.py thesis-ch6
```

형식은 4장 그림과 같다. 그림 번호는 통합 초안(`system-prompt-extraction/plan/THESIS-CH6-DRAFT.md`)에서 처음 인용되는 순서를 따른다.
그림은 본문 폭 16 cm로 그리고, 글자 크기는 인쇄 크기 그대로다(본문 8 pt, 눈금·범례 7.5 pt, 값 표시 6–7 pt).
각 그림은 `png`(300 dpi), `pdf`, `svg`와 그린 값을 담은 `csv`로 저장한다. 색은 Okabe-Ito palette이고 흑백 인쇄를 위해 빗금을 함께 쓴다.
그림 안에는 그림 제목과 아래 설명 문장을 넣지 않았다. 설명은 논문 캡션에 둔다.
배치 이름은 약어로 쓴다. 캡션이나 본문에서 처음 나올 때 풀어 쓴다.
- WFD: U 균형 배치(Worst-Fit Decreasing)
- RA: release 고려 배치(Release-Aware)
- CGB: CLS Grouping with Balancing
- RA-CGB: Release-Aware CGB, CHASER 배치

| 파일 | 내용 | 입력(실험) |
|---|---|---|
| `figure-6-1.*` | 친화도가 낮은 task의 관측 최대 job CPU 시간 ÷ 계획 예산. 유형(32 KiB, 768 KiB)·주기 CV별로 Partitioned 배치 4종의 중앙값과 사분위 범위 | [`results/deadline-small`](../results/deadline-small/), [`results/deadline-big`](../results/deadline-big/)의 `rt-metrics.json`, `results.jsonl` (27절) |
| `figure-6-2.*` | 같은 사례의 TET(ms) | 같은 결과 묶음의 `results.jsonl` (27절) |
| `figure-6-3.*` | 32 KiB 유형: 부하별 모든 마감을 지킨 set 수(배치 4종, 주기 CV 0과 0.2) | `results/deadline-small/results.jsonl` (27절) |
| `figure-6-4.*` | 768 KiB 유형: 같은 그림 | `results/deadline-big/results.jsonl` (27절) |
| `figure-6-5.*` | 그림 6.1과 같은 사례의 TAT(ms) | 같은 결과 묶음의 `results.jsonl` (27절) |
| `figure-6-6.*` | Algorithm 1 변형 3종(CAAS, CLS-A1, 보정 임곗값의 CLS-A1)의 부하별 배치 가능 set 수(주기 CV 두 칸 합, 부하당 36개) | [`results/deadline-ladder/ladder.json`](../results/deadline-ladder/ladder.json)의 `summary` (28절) |
| `figure-6-7.*` | 합성 워크로드 RF 평가: CHASER 배치의 마감 준수를 가르는 AUC(RF 확률, D + M, D), 전체와 유형별 | `results/confirm-{small,big,mem}`의 `results.jsonl`, `decisions.json` (44절) |
| `figure-6-8.*` | 같은 평가: 실행 허용·거절 결과 네 가지의 set 수(RF, D + M < 0.975 규칙, 항상 CHASER 실행) | [`results/confirm-analysis/confirm.json`](../results/confirm-analysis/confirm.json) (44절) |
| `figure-6-9.*` | 미학습 커널 7종: 부하별 같은 결과 | [`results/real-kernels-analysis/confirm.json`](../results/real-kernels-analysis/confirm.json) (45절) |
| `figure-6-10.*` | RF 확률 구간별 CHASER 배치의 실제 마감 준수 비율, 합성 평가와 커널 7종 (사후 진단) | [`results/real-kernels-analysis/report.json`](../results/real-kernels-analysis/report.json)의 `calibration` (44·45절) |
| `figure-6-11.*` | 실행 전 점검이 본 task별 L1 miss 요청률(단독 실행 µs당), 합성 유형 3종·커널 7종·추가 커널 4종의 5·25·50·75·95번째 백분위수 | [`results/heldout-kernels-analysis/report.json`](../results/heldout-kernels-analysis/report.json), `results/real-kernels-analysis/report.json`의 `task_values` (44–46절) |
| `figure-6-12.*` | 부하 0.625·0.70의 CHASER run에서 task별 가장 긴 job CPU 시간 ÷ 계획 예산, 커널별 백분위수 (사후 진단) | [`kernel-inflation-tasks.csv`](kernel-inflation-tasks.csv) (45·46절 원자료) |
| `posthoc.md`, `posthoc.json` | 기본 집합 단위 사후 분석: 27절 TET·TAT, 44절 RF 대 규칙 부호검정, 44·45절 AUC 차이의 기본 집합 재표집 구간 | 결과 묶음 (27·44·45절) |
| `kernel-inflation-tasks.csv` | 그림 6.12의 task별 값 1,593개 | `.cache/real-kernels-v1`, `.cache/heldout-kernels-v1`(원자료, 삭제 목록에 있음) |

`kernel-inflation-tasks.csv`는 [`figures/thesis_ch6_inflation.py`](../figures/thesis_ch6_inflation.py)가 원자료에서 한 번 뽑았다.
원자료를 지운 뒤에도 그림 6.12를 다시 그릴 수 있도록 값을 남긴다.
뽑은 값의 커널별 중앙값과 95번째 백분위수는 `results/heldout-kernels-analysis/figures/heldout-inflation.csv`와 같다(2026-10-12 확인).

```sh
W=/workspace/experiments/chaser
PYTHONPATH=$W:$PWD/policy-mix:$PWD/period-distribution python3 figures/thesis_ch6_inflation.py $W/.cache thesis-ch6/kernel-inflation-tasks.csv
```

## 캡션과 본문에 밝힐 집계 기준

- **그림 6.1, 6.2, 6.5:**
  - 네 Partitioned 배치가 모두 모든 마감을 지킨 사례만 썼다(공통 사례).
    - 32 KiB 유형: 주기 CV 0 59개, CV 0.2 53개
    - 768 KiB 유형: 각각 33개
  - 막대는 중앙값, 오차막대는 사분위 범위다. 신뢰구간이 아니다.
  - 본문의 백분율(표 6.2, TAT ±2% 동등성)은 사전 등록 분석의 값이다. 두 배치끼리 짝지어, 둘 다 마감을 지킨 사례 전체(117–122개, 70–71개)에서 로그 비의 중앙값으로 구했다. 그래서 이 그림의 중앙값끼리 나눈 값과 다르다.
  - 예: 768 KiB 유형의 TAT는 그림에서 RA 594 ms 대 RA-CGB 628 ms(CV 0)이고, 본문의 짝지은 값은 +2.9%다.
- **그림 6.3–6.4:**
  - set 수는 기본 태스크 집합 18개를 부하와 주기 CV마다 반복한 값이다.
  - 마감 준수는 준비 구간을 포함한 run 전체로 판정했다.
  - 시작에 실패한 Partitioned run은 1개다(768 KiB, CV 0, 부하 0.30, CGB). 마감을 지키지 못한 것으로 셌다.
  - G·C 구성은 넣지 않았다.
- **그림 6.6:** 배치 가능 여부는 각 규칙이 만든 배치로 판정했다. 격리 영역이 가득 차서 대체 배치로 빌드한 run은 배치 불가로 셌다. CGB·RA-CGB는 모든 set을 배치하므로 점선으로만 표시했다.
- **그림 6.7:**
  - RF는 CHASER 배치(Partitioned 후보)의 확률을 썼다. 정적 방법은 −D, −(D + M)을 점수로 썼다.
  - 유형별 막대는 기술 통계다. 사전 등록 판정(H1)은 전체 357개 set의 비교다.
- **그림 6.8–6.9:**
  - "Always"는 점검 없이 모든 set에서 CHASER 배치를 실행하는 경우다.
  - false reject는 평가한 네 후보(CHASER P, G4, C1+3, C1+1+2) 중 하나라도 모든 마감을 지켰는데 거절한 경우다.
  - 6.8은 패널마다 세로축이 다르다.
- **그림 6.10:**
  - 판정을 본 뒤의 사후 진단이다.
  - 막대 위 숫자는 지킨 set 수 / 구간의 set 수다. 커널 7종에는 확률 0.5 미만인 set이 없었다.
- **그림 6.11:**
  - 값은 HARA(YARDA)가 모델링한 job의 L1 miss 수를 계획 단독 실행시간으로 나눈 것이다. 동시 실행 중 실측한 공유 L2 요청률이 아니다.
  - task 관측은 부하별로 반복 집계된다.
  - 세로축은 로그 눈금이다. 상자는 25–75번째, 수염은 5–95번째 백분위수, 굵은 선과 숫자는 중앙값이다.
- **그림 6.12:**
  - 판정을 본 뒤의 사후 진단이다.
  - 계획 예산은 고른 크기를 혼자 실행해 잰 job 시간이다.
  - 마감을 놓친 run의 task는 첫 위반까지 실행한 job만 들어 있다(`rtems/periodic/init.c`).
  - 이름 옆 괄호는 task 관측 수다. 상자와 수염은 그림 6.11과 같다.

기존 결과 묶음과 실험별 그림 스크립트(`deadline_confirm_bars.py`, `ladder_bars.py`, `confirm_bars.py`, `kernel_bars.py`, `heldout_bars.py`)는 바꾸지 않았다.
