# 논문 3.4절 그림 3.3과 표

[`tools/plot_s1_thesis.py`](../../../tools/plot_s1_thesis.py)가 저장된 S1 결과에서 만든다.

```sh
python3 -m tools.plot_s1_thesis --output artifacts/s1/thesis-ch3
```

| 파일 | 내용 | 입력 |
|---|---|---|
| `figure-3-3.{png,svg,pdf}` | 합성 워크로드 25개의 계층별 접근 비율: 빈 캐시에서 시작한 Cachegrind(가로) 대 HARA(CSRD)와 전역 재사용 거리(세로) | [`cachegrind-cold-v1/results.csv`](../cachegrind-cold-v1/results.csv) |
| `table-3-polybench.{md,csv}` | PolyBench 계열 커널 4개의 배열 접근 수와 L1·L2 미스 수(Cachegrind, HARA, 전역 재사용 거리). 기존 그림(`polybench-cold-v1/polybench-cachegrind.svg`)을 대신한다 | [`polybench-cold-v1/results.csv`](../polybench-cold-v1/results.csv) |

그림 3.3의 모든 워크로드는 정확한 값에 그린다. 같은 값의 워크로드는 겹치므로 모델마다 25개보다 적은 마커가 보인다(캡션에 적는다).
그림 안에는 제목과 설명 문장을 넣지 않았다. 설명은 논문 캡션에 둔다.
그림은 본문 폭 16 cm로 그린다. 글자 크기는 인쇄 크기 그대로다(본문 8 pt, 눈금·범례 7.5 pt).
색은 색각 이상에도 구분되는 Okabe-Ito palette(Wong, Nature Methods 8:441, 2011)이고, 흑백 인쇄를 위해 마커 모양(채운 +, 빈 원)도 다르게 했다.
기존 결과 묶음의 그림(`cachegrind-cold-v1/prediction-reference.*`, `polybench-cold-v1/polybench-cachegrind.*`)과 그 스크립트(`tools/plot_s1.py`, `tools/plot_s1_polybench.py`)는 바꾸지 않았다.
