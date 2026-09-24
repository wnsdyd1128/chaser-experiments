# Periodic final-v1 RF 모델

2026-09-24 완료한 `periodic-final-v1-common-198` 학습의 선택 모델을
`.cache/rf-tuning-v1/results/`에서 복사했다. 원본과 복사본의 SHA-256을 대조했다.

`{배치 정책}/{RF 입력}/{baseline|tuned}/seed-{42..46}/model.joblib` 형식이다.
배치 정책은 `caas-ca`, `ca-csrd`, `cls`이며 RF 입력은 `caas-ca`, `ca-csrd`, `clp`다.
각 구성에서 고정 설정(`baseline`)과 validation에서 선택한 설정(`tuned`)을
seed 5개씩 보존해 모델 파일은 총 90개다. 1,620번의 후보 학습 모델 전체를
저장한 것은 아니다.

최상위 `run.json`·`summary.json`, 구성별 `search.json`·`selection.json`은
실행 설정과 튜닝 선택 근거다. Validation/test 예측과 평가지표는 원래
`.cache/rf-tuning-v1/results/`에 남아 있다. 학습 입력·split은
[최종 dataset 설명](../../datasets/periodic-final-v1/README.md)을 따른다.

```python
import joblib

model = joblib.load('models/rf-tuning-v1/ca-csrd/clp/tuned/seed-42/model.joblib')
predictions = model.predict_vectors(feature_rows)  # 각 행은 CLP+U 21차원
```

모델은 `chaser.rf.ArchitectureRF` 객체이며 학습된 MinMaxScaler와 RF를 함께 담는다.
FHC/AMC count 입력의 후속 모델은 아직 학습하지 않았다.
