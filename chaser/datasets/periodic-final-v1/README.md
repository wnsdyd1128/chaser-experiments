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

## 원본 근거와 보존 범위

기초 입력·독립 U·캐시 분석은 [periodic-v2](../periodic-v2/README.md)에 있다.
정책별 실행 소스·ELF·raw log는 [.cache/final-mapping-v1/execution](../../.cache/final-mapping-v1/execution/)에 남아 있다.
이번 이전은 최종 export만 대상으로 했으며 측정 원본 전체를 옮기지는 않았다.
Metadata의 `source_execution`, provenance의 snapshot 경로 및 hash는 원래 측정 근거를 가리키므로 그대로 유지했다.
따라서 학습 sample은 이곳에서 읽을 수 있지만 전체 측정 재검증에는 해당 원본 경로도 필요하다.

대용량 payload는 기존 `.cache`에서와 마찬가지로 Git 제외이며 README만 Git 관리 대상이다.
Git commit만으로 dataset payload가 백업되지는 않는다.
