# Active dataset calibration v2 — loader connected

2026-09-23: 최종 사용 데이터셋을 보정 loader에 연결했다. 소속 정본은
[V2 active-population](../validation-supplement-v2/active-population.json)이며,
보존212개 중 사용207개(train/validation/test=126/41/40)다.
원본 실패4개와 V1-0001은 제외한다. 보정에는 validation 기존37개와
V1-0002/0003/0004, V2-0001만 사용한다.

## 입력 및 증거 연결

[input-sources.json](input-sources.json)은 소속 파일·원본 population/split의 hash와
대체4개의 snapshot, U batch, utilization/features 경로 및 증거 hash를 고정한다.
경로는 workspace root 기준이다. 원본 frozen 입력과 cache를 수정하거나 측정 증거를
다른 ELF identity로 복사하지 않는다. 원본과 V1은 `runs/<workload>/uN`, V2는 `u/uN`의
기존 로그를 직접 읽는다.

Loader는 전체 소속·family별 split 개수와 train/test identity를 먼저 확인한다.
그 후 validation만 로드하여 config hash, snapshot/source 및 analysis manifest,
raw U, utilization, feature, U 상한과 undefined feature 검사를 수행한다.
Toolchain/simulator identity도 보정 계획 작성 시 기존과 동일하게 검사한다.
Mapping 준비 단계의 source/tool/layout/locality/linked-stream 비교도 유지한다.

원본 frozen split hash와 새 active membership/assignments hash는 구분하여 기록하며,
active identity를 후속 보정 계획과 동결 policy에 포함한다. `--input-sources`를 생략하면
역사적 원본 데이터셋 경로이므로 현재 데이터셋 보정에는 반드시 아래 연결 파일을 지정한다.
기존 calibration-v1 출력은 재사용하거나 덮어쓰지 않는다.

## 연결 검증 결과

[loader-validation.json](loader-validation.json)은 실제 기존 cache에 대한 검증 기록이다.
Validation **41개·448 tasks·독립 U raw 4,480회** 재검증 및 tool identity 검사가 PASS다.
기존 U characterization ID와 U ELF hash를 입력별로 보존했다. Train/test의 feature/raw는
보정 입력으로 로드하지 않았다. 이 기록은 새 timing 수집이나 θ 선택 결과가 아니다.

## 다음 실행

다음 명령은 새 θ 후보와 mapping의 계획만 만든다. 이번 연결 작업에서는 실제 데이터의
threshold search, mapping 준비·추가 측정·θ/policy 동결·최종 label 생성을 실행하지 않았다.
기존 측정의 실행 동등성 대응표와 추가 예산은 계획 재계산 이후 별도로 산출해야 한다.

```sh
python3 -m tools.rtems_periodic_calibrate plan \
  .cache/characterization-v1-inputs/frozen \
  --characterized .cache/characterization-v1 \
  --input-sources artifacts/periodic/calibration-v2/input-sources.json \
  --output .cache/calibration-v2
```

후속 prepare/run/freeze에도 같은 `--input-sources`를 전달한다. 입력·구현·연결 파일이
기존 계획과 다르면 resume는 거부한다. Raw와 상세 분석 산출물은 ignored cache이므로
이 연결 파일과 검증 기록만으로 재현에 필요한 전체 증거가 백업되지는 않는다.

## 구현 검증

- `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify`: 빌드 및 전체 **620 passed**, skip 없음.
- 전체 검증 시작 후 추가한 active policy identity 검사까지 포함한
  `python3 -m pytest -q tests/test_periodic_calibration.py`: **30 passed**.
- 실제 loader 검증 기록의 구현 hash, 문서 로컬 링크, `git diff --check`: PASS.
- Finalize는 호출하지 않았다.
