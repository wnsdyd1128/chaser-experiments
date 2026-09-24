# Periodic 최종 학습용 dataset v1

2026-09-24: 기존 `.cache/final-mapping-v1/dataset/`의 최종 export를 이곳으로 이전했다.
원본18개 파일·38,743,724 bytes의 SHA-256을 이동 전후 대조했고 모두 동일하다.
기존 경로에는 `../../datasets/periodic-final-v1` 상대 호환 링크만 남아 있으며 데이터 복사본은 없다.
이전으로 입력·split·label·feature·정책을 바꾸지 않았다.

## 학습에 사용할 파일

| 경로 | 내용 |
|---|---|
| [caas-ca/rf_samples.jsonl](caas-ca/rf_samples.jsonl) | CAAS-CA 배치·측정 label과 기존 표현별 feature |
| [ca-csrd/rf_samples.jsonl](ca-csrd/rf_samples.jsonl) | CA-CSRD 배치·측정 label과 기존 표현별 feature |
| [cls/rf_samples.jsonl](cls/rf_samples.jsonl) | CLS(0.5) 배치·측정 label과 기존 표현별 feature |
| [eligibility.json](eligibility.json) | 정책별 성공·실패 판정과 공통 학습 대상 |
| [split.json](split.json) | 원본207개 소속; 학습 시 공통 적격198개로 제한 |
| [summary.json](summary.json) | 완료 상태·건수·정책별 label 분포·파일 hash |

공통 적격198개, train/validation/test=120/41/37이다. 실패9개는 세 정책 공통 제외했다.
정책별 sample594행은198개×기존 RF 표현3종이며 독립 taskset이594개인 것은 아니다.
`task_characterization.jsonl`과 provenance는 원본207개의 분석 기록도 담으므로 이를 그대로
학습 집합으로 사용하지 않는다. `rf_samples.jsonl`의 공통 적격 집합을 따른다.

현재 RF 표현은 CAAS-CA/CA-CSRD/CLS의 scalar 11-feature다. 합의한3×3의 제안 입력인
CLP21 export와 RF 학습은 아직이다. 디렉터리명 `cls/`는 배치 정책이며 CLP feature 생성 완료를 뜻하지 않는다.
별도 대체 수집은5개 확보·4개 미확보이고 export되지 않았으므로 이 dataset에 보충분은 없다.

## S2/S5 주 분석 대상 확정 (2026-09-24)

S2/S5의 주 분석에는 이 export의 **공통 적격 198개**만 사용한다. 기존 label과
`split.json`의 소속을 그대로 유지하며, 세 배치 정책의 각 RF 입력은 동일한 198개에서
학습·평가한다. 정책별 label은 해당 정책의 G/C/P 측정값을 따른다.
실패 9개(train 6, test 3)는 모두 제외한다. 별도 대체 수집의 성공 5개도 현재 export에
없으므로 주 분석 집합에 추가하지 않는다.

현재 공통 적격 집합·split·label 및 task별 CLP/U 원본의 SHA-256은
[공통 적격 집합 고정 파일](analysis-set-lock.json)에 고정했다. 새 feature exporter가 입력 해시를
확인한 뒤 별도 버전을 생성한다.

세 정책 각각에서 sample의 workload·split·label을 `eligibility.json` 및 `split.json`과
대조해 불일치 0건을 확인했다. 현재 scalar sample 파일은 변경하지 않았다.

## 원본 근거와 보존 범위

기초 입력·독립 U·캐시 분석은 [periodic-v2](../periodic-v2/README.md)에 있다.
정책별 실행 소스·ELF·raw log는 [.cache/final-mapping-v1/execution](../../.cache/final-mapping-v1/execution/)에 남아 있다.
이번 이전은 최종 export만 대상으로 했으며 측정 원본 전체를 옮기지는 않았다.
Metadata의 `source_execution`, provenance의 snapshot 경로 및 hash는 원래 측정 근거를 가리키므로 그대로 유지했다.
따라서 학습 sample은 이곳에서 읽을 수 있지만 전체 측정 재검증에는 해당 원본 경로도 필요하다.

대용량 payload는 기존 `.cache`에서와 마찬가지로 Git 제외이며 README만 Git 관리 대상이다.
Git commit만으로 dataset payload가 백업되지는 않는다.
