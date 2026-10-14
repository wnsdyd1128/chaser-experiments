# 6장 본문·통계 통합 검토

이 디렉터리는 본문과 통계 검토 결과다. 그림은 다른 세션이 담당한다. 공용 `THESIS-CH6-DRAFT.md`와 `thesis-ch6/figure-*`는 이 검토본을 반영하면서 덮어쓰지 않는다.

- [CHAPTER6.md](CHAPTER6.md): 6.1–6.7 통합 원고. 완성된 그림 6.1–6.12에 삽입 위치·본문 인용·캡션을 맞췄으며, 작업용 경로는 아래 대응표에 모았다.
- [APPENDIX-NOTES.md](APPENDIX-NOTES.md): 부록 A·D에 옮길 재현 점검과 v2 선택 경위.
- [posthoc-sensitivity.json](posthoc-sensitivity.json): 기본 태스크 집합 단위 사후 분석. 기존 사전 등록 결과를 교체하지 않는다.
- [supplement.py](../../figures/thesis_ch6/supplement.py): 저장된 결과만 읽는 재현 코드. 학습·추론·시뮬레이션을 수행하지 않는다.

## 검토 의견의 반영과 정정

| 항목 | 반영 위치·판정 |
|---|---|
| 실험 45 뒤 v2 개발, 실험 46 결과 확인 뒤 v1 유지 | 6.1.2, 6.5.3–6.5.4, 6.7, 부록 D. 사전 결정 저장과 사전 등록 확증을 구분했다. |
| v2의 47개 거절 | 유효 144사례 중 47개다. 네 후보가 모두 성공했고, v1은 모두 P로 허용했다. 두 정책의 실패 구분 능력은 이 전부 성공 자료로 검정할 수 없다. |
| 경합 인과 주장 | 함께 실행할 때 관측한 CPU 시간 증가로 고쳤다. 직접 측정하지 않은 원인의 효과라고 서술하지 않는다. |
| V1 누락 | 6.2.4에 88/88·84/84·66/143을 추가했다. 네 결정적 P 배치의 공동 결과이며 개별 run 성공률이 아니다. 768 KiB는 원 설계상 보고용 적용 범위 점검이다. |
| CAAS 84 대 RA-CGB 77 | 6.3.2에 불일치 9 대 2, 정확 양측 McNemar raw p=0.0654296875, 보조 Holm p=0.5234375 중 본문에는 보정값 0.523을 명시했다. |
| 실험 46의 0.58/0.79초 | **v2 시간**이다. v1의 별도 시간 기록이 없어 표 6.6에는 기록 없음으로 표시했다. 본문에서 귀속을 설명하고 부록 D에 참고값을 보존했다. |
| 합성 계획 이용률 | 단독 보정 모델의 구현별 예측 CPU/주기이다. 각 조건·부하의 set 0에서 단독 실행 오차 3% 이내를 점검한다. 커널의 직접 단독 실행 측정과 구분했다. |
| 작업 CPU 증가 1.3–1.8배 | GEMM을 제외한 여섯 커널의 중앙값이다. GEMM은 1.04배, 추가 네 커널은 1.02배이다. 준비 구간을 포함한 기록된 작업의 최대값이며, 측정 구간만의 최대값이 아니다. 6.5.5와 그림 6.12에 관측 범위를 적었다. |
| 무작위 배치 대비 −9.8/−11.7%p | 6.2.2에 보조 분석으로 추가했다. 각 사례의 세 무작위 배치 평균과 비교하며, 하나라도 위반 지표가 양수인 231/121사례를 사용한다. |
| 재현 표본 점검 | 6.7과 부록 A. 8사례·20실행의 시각·응답·판정 재현이며 파일 바이트의 완전 일치는 아니다. |
| 약어·작업 경로 | RA-CGB를 본문에서 정의했다. 본문에 `/workspace` 경로나 기존 결과 파일 링크를 넣지 않았다. |

## 부트스트랩 신뢰구간의 차이

아래 세 분석은 같은 난수 시드 20264400과 2,000회 재표집을 사용한다. 소수 셋째 자리 차이는 시드가 달라서 생긴 것이 아니라 **재표집 단위와 층화 방식의 차이**다.

| 실험 44의 RF−D | 재표집 방식 | 95% percentile CI |
|---|---|---|
| 기존 사전 등록 분석 | 유효 357사례를 개별 재표집 | [0.1869904, 0.2877973] |
| 사후 비층화 분석 | 기본 집합 72개를 함께 재표집, 집합의 모든 유효 부하 포함 | [0.1948703, 0.2750450] |
| **사후 층화 분석: 본문 채택** | 유형별 기본 집합 24개씩 재표집, 집합의 모든 유효 부하 포함 | **[0.2006062, 0.2743508]** |

반복하여 추출된 기본 집합의 행은 반복 포함한다. 시작 실패로 제외한 행을 복원하거나 각 집합을 임의로 5행으로 맞추지 않는다. 유형의 순서는 small, big, mem이다. 두 군집 방식은 각각 같은 시드로 새 NumPy RNG를 시작한다. 신뢰구간은 기본 선형 보간을 적용한 2.5·97.5백분위수다. 재표집 차이가 비양수인 횟수 0/2,000을 p=0으로 보고하지 않는다.

실험 45의 커널 자료는 기본 집합 24개를 재표집한다. RF−D CI는 [0.0334032, 0.1348399], RF−(D+M) CI는 [−0.0079960, 0.0232074]로, 후자는 0을 포함한다.

### 재현 명령

워크스페이스 `/workspace/experiments/chaser`에서 실행한다.

```sh
python3 artifacts/periodic/scheduler-comparison-v1/figures/thesis_ch6/supplement.py artifacts/periodic/scheduler-comparison-v1/thesis-ch6/review/posthoc-sensitivity.json
```

다른 작업 디렉터리에서는 스크립트·출력에 절대경로를 지정할 수 있다. 입력 경로는 스크립트 위치를 기준으로 결정한다. 결과 JSON에 입력 SHA-256, 구현 SHA-256, 라이브러리 버전, 표본 수, 방식과 시드를 함께 기록한다. 원자료·결정·모델 파일에는 쓰지 않는다.

### 검증 범위

- 재현 스크립트를 실행하여 독립 검토에서 계산한 AUC 차이 신뢰구간, TET 감소 집합 수, TAT 동등성 및 부호검정 결과와 대조하였다. 위 수치가 모두 재현되었다.
- 입력 16개와 구현 파일의 SHA-256, 본문의 절·그림 자리 및 내부 문서 링크를 확인하였다.
- 판정 결과 해석과 관련된 기존 `tests/policy/pfirst/test_pfirst_decision.py`는 `python3 -m pytest -q -p no:cacheprovider`로 실행하여 **7 passed**였다. 보조 통계 코드는 이 테스트로 검증된 것이 아니라 위 수치 재현으로 검증하였다.
- 그림 완성 후 12개 CSV를 결과 묶음과 대조하였다. 공통 성공 표본·중앙값·사분위수, 마감 준수 수, 배치 가능·시작 성공 수, AUC, 결정 결과, 확률 구간별 수, 요청률 및 CPU 증가 비율의 백분위수가 모두 일치하였다.
- 그림 6.1–6.12의 본문 인용·삽입 위치·캡션 순서와 PDF·SVG·PNG·CSV 48개 파일의 존재를 확인하였다. 검토 전후 그림 묶음 파일의 SHA-256도 일치하였다. 이 단계에서는 문서 두 개만 수정했으며 정책 테스트를 다시 실행하지 않았다.
- 시뮬레이션 재실행과 모델 재학습은 이 검토의 범위에 포함하지 않는다. 완성된 그림과 본문의 대응은 아래에 별도로 정리하였다.

## 본문과 결과 묶음의 대응

아래 경로는 `artifacts/periodic/scheduler-comparison-v1/` 기준이다. 논문 본문에는 작업용 경로를 삽입하지 않고 부록의 재현 자료 목록에 옮긴다.

| 본문 | 근거 |
|---|---|
| 6.1 측정·분모 | `system-prompt-extraction/plan/MEASUREMENT-CONTRACT-V3.md`는 workspace 기준. 분석 구현은 `policy-mix/rt_metrics.py`. |
| 6.1 합성 계획 이용률 | `policy-mix/deadline_set.py`, `policy-mix/confirm_set.py`, `high-load/hl_run.py`; `results/deadline-{small,big}{,-caas}/isolated-u.json`, `results/confirm-{small,big,mem}/isolated-u.json`. |
| 표 6.2, V1, 무작위 비교, TAT | `results/deadline-confirm/deadline-confirm.{json,md}`, `policy-mix/deadline_analysis.py`. |
| 표 6.3·CAAS 검정 | `results/deadline-ladder/ladder.{json,md}`, `policy-mix/algorithm1.py`. |
| 표 6.4·G/C 전환 | `results/confirm-analysis/confirm.{json,md}`, `results/confirm-{small,big,mem}/{results.jsonl,decisions.json}`. |
| 표 6.5·확률 구간 | `results/real-kernels-analysis/{confirm,report}.{json,md}`, 같은 디렉터리의 `figures/kernel-calibration.csv`. |
| 추가 커널 v1·v2 | `results/heldout-kernels/{results.jsonl,decisions.json}`. 주 `status`는 v2, `compare`는 v1이다. `policy-mix/kernel_report.py`의 v1 변환은 시간 필드를 교체하지 않는다. |
| 그림 6.11 | `results/heldout-kernels-analysis/report.json`, `results/real-kernels-analysis/report.json`의 `task_values`. 커널 입력 분포는 시작 실패를 제외하기 전의 전체 설계 사례를 사용한다. |
| 그림 6.12 | `thesis-ch6/kernel-inflation-tasks.csv`, `figures/thesis_ch6_inflation.py`. 기존 `results/heldout-kernels-analysis/figures/heldout-inflation.csv`와 같은 관측 범위이며, 준비 구간을 포함한다. |
| 표 6.6 | `results/confirm-analysis/confirm.json`, `results/real-kernels-analysis/confirm.json`의 결정 시간; 시간 구간은 `policy-mix/kernel_run.py`, `policy-mix/confirm_run.py`. |
| 재현 점검 | `results/reproduction-check/spotcheck.{py,json}`, `EXPERIMENTS.md` 47절. |
| 사후 기본 집합 통계 | 이 디렉터리의 `posthoc-sensitivity.json`. 기존 검정 결과와 분리한다. |

CAAS 원문은 workspace의 `references/CAAS Cache Affinity Aware Scheduling Framework for RTEMS with Edge Computing Support.pdf`이다. PolyBench의 배포 출처는 <https://sourceforge.net/projects/polybench/files/>이다. 최종 참고문헌 번호는 2장의 CAAS·PolyBench 항목과 통일한다.

## 완성된 그림과 통합 원고의 대응

다른 세션에서 완성한 그림 12개의 파일명과 번호를 그대로 사용한다. 기존 8개 자리 중 마감 준수 그림과 커널 사후 진단 그림을 각각 둘로 나누고, TET·TAT 그림을 해당 절에 추가하였다. 각 그림의 PNG를 열어 배치·범례·축·집계 표기를 확인하고, 캡션을 CSV 및 생성 스크립트의 집계 기준과 대조하였다.

| 그림 | 삽입 절 | 내용·PDF |
|---|---|---|
| 6.1 | 6.2.1 | [관측 최대 CPU 시간 증가 비율](../figure-6-1.pdf) |
| 6.2 | 6.2.1 | [TET](../figure-6-2.pdf) |
| 6.3 | 6.2.2 | [32 KiB 유형의 마감 준수](../figure-6-3.pdf) |
| 6.4 | 6.2.2 | [768 KiB 유형의 마감 준수](../figure-6-4.pdf) |
| 6.5 | 6.2.3 | [TAT](../figure-6-5.pdf) |
| 6.6 | 6.3.2 | [Algorithm 1 계열의 배치 가능·시작 성공 사례](../figure-6-6.pdf) |
| 6.7 | 6.4.1 | [합성 워크로드의 예측 AUC](../figure-6-7.pdf) |
| 6.8 | 6.4.2 | [합성 워크로드의 실행 허용·거절](../figure-6-8.pdf) |
| 6.9 | 6.5.2 | [미학습 커널의 부하별 실행 허용·거절](../figure-6-9.pdf) |
| 6.10 | 6.5.3 | [v1 확률 구간별 실제 마감 준수 비율](../figure-6-10.pdf) |
| 6.11 | 6.5.5 | [단독 실행 기준 L1 미스 요청률](../figure-6-11.pdf) |
| 6.12 | 6.5.5 | [고부하의 커널별 작업 CPU 시간 증가](../figure-6-12.pdf) |

캡션에서 바로잡은 내용은 다음과 같다.

- 그림 6.1·6.2·6.5는 네 배치의 공통 성공 사례(59·53·33·33개), 본문의 짝 비교는 두 배치가 모두 성공한 사례를 사용한다. 그림 중앙값의 비와 본문 효과 크기를 같은 통계로 해석하지 않는다.
- 그림 6.4는 시작 실패 한 건을 성공 수에 넣지 않으면서 설계 사례 18개를 분모로 유지한다. 기존 원고의 “시작 실패를 집계에서 제외”를 고쳤다.
- 그림 6.6의 막대는 `ladder_analysis.summary()`가 시작 실패를 제외한 뒤 집계한 `placeable` 값이다. 따라서 순수한 배치 가능 여부만을 센 수가 아니라 **배치 가능·시작 성공 사례 수**로 설명한다. CGB·RA-CGB의 36개 점선은 시작 성공 여부와 별개인 배치 가능 기준선이다.
- 그림 6.8·6.9의 기준선 이름은 `Always`이다. 유형별 패널의 세로축이 다른 그림 6.8에는 그 사실도 명시하였다.
- 그림 6.10은 v1의 사후 진단이며, 표본 없는 구간과 0%인 구간을 구분한다. 구간 경계와 `준수 수 / 전체 수` 표기를 설명하였다.
- 그림 6.11·6.12의 상자는 25–75백분위수, 수염은 5–95백분위수, 굵은 선과 상단 숫자는 중앙값이다. 수염은 신뢰구간이 아니다.
- 그림 6.11의 커널 입력 분포에는 시작 실패 사례의 입력도 들어 있다. 그림 6.12의 실행 기록은 네 후보가 모두 판정 가능한 고부하 사례만 사용하며, 준비 구간의 작업도 포함한다.

그림 파일과 그림 생성 스크립트는 수정하거나 재생성하지 않았다. 인쇄 크기와 글꼴 등 제작 사양은 [그림 묶음 README](../README.md)를 따른다.
