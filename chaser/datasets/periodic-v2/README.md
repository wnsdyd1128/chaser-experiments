# Periodic dataset v2 — 기초 자료와 최종 학습 데이터 위치

갱신: 2026-09-24. 현재 파일과 최종 export 기록을 기준으로 한다.

## 현재 완료 범위

| 단계 | 현재 상태 |
|---|---|
| 입력·split·독립 U·정적 분석 | 207 tasksets, train/validation/test=126/41/40, 2,168 tasks |
| Validation 보정 | 41개로 CAAS-CA·CA-CSRD·CLS(α=0.5)의 θ/policy 동결 완료 |
| 최종 정책별 측정 | 621개 배치, G/C/P 1,863 batches × 10회 = 18,630회 완료; 성공 18,400회, 실패 230회 |
| 학습 sample export | 공통 적격 198개, train/validation/test=120/41/37; 세 정책별 label 생성 완료 |
| 실패 제외 | arm_phase/release_mismatch가 발생한 9개(taskset 단위, train6/test3)를 세 정책 모두에서 제외 |
| 추가 대체 | 9개 중 5개 확보, 4개 미확보; partial / not_exported. 보충분은 현재 sample에 미반영 |
| CLP feature·RF | CLP 21차원 export 미구현, RF 학습·S2/S5 본평가 미실행 |

## 무엇을 어디서 읽는가

| 경로 | 내용 |
|---|---|
| 이 디렉터리의 [dataset.json](dataset.json)·[membership.json](membership.json) | 기초 입력207개와 characterization·보정 자료의 위치·소속 |
| [datasets/periodic-final-v1](../../datasets/periodic-final-v1/) | 현재 RF 학습용 export; 최종 [summary](../../datasets/periodic-final-v1/summary.json) |
| [.cache/final-mapping-v1/execution](../../.cache/final-mapping-v1/execution/) | 세 정책별 실행 소스·ELF·분석·측정 raw |
| [.cache/final-mapping-v1/plan.json](../../.cache/final-mapping-v1/plan.json) | 동결 정책별 배치와 원본 입력·U identity |
| [.cache/final-replacement-v1/run](../../.cache/final-replacement-v1/run/) | 대체 후보의 측정·성공/실패 시도와 [선택 결과](../../.cache/final-replacement-v1/run/summary.json) |
| [frozen-policies.json](../../artifacts/periodic/calibration-v2/frozen-policies.json) | 현재 적용한 세 배치 정책의 θ·α·정책 ID |

`datasets/periodic-v2/`는 기초 자료 저장소다. 최종 RF export는 별도 `datasets/periodic-final-v1/`로 이전했다.
기존 `.cache/final-mapping-v1/dataset/`에는 호환 링크만 남았다. 실행 raw는 `.cache/final-mapping-v1/execution/`에 유지한다.
`dataset.json`의 `final_labels_ready: false`는 기초 자료 index 생성 당시 범위다.
별도 최종 export의 `dataset_stage: final_labels_ready`와 혼동하지 않는다. 기존 index 바이트는 유지한다.

최종 export의 `caas-ca/`, `ca-csrd/`, `cls/`는 **배치 정책**이다. 각 디렉터리의
`rf_samples.jsonl`은 198개 × 기존 표현3종(CAAS-CA/CA-CSRD/CLS) = 594행이며 독립 taskset은 198개다.
`task_characterization.jsonl`에는 제외 전 207개·2,168 tasks의 분석값도 남아 있으므로,
학습 집합은 `rf_samples.jsonl`과 [eligibility.json](../../datasets/periodic-final-v1/eligibility.json)으로 읽는다.
`split.json`은 원래207개 소속을 보존한다. 실패 원본·분석 기록 보존을 학습 포함으로 해석하지 않는다.

제외 ID는 candidate-v3-0066/0067/0113/0117/0137/0195/0196/0197/0223이다.
한 정책에서라도 실패하면 다른 정책의 성공분도 공통 비교에서 제외한다.
대체 성공은 0066→0066-03, 0067→0067-03, 0113→0113-01, 0117→0117-02, 0223→0223-01
(`final-replacement-v1-` 접두사)이며 0137/0195/0196/0197은 미확보다.
[export 상태](../../.cache/final-replacement-v1/export-progress.json)는 `not_exported`이고
대체 dataset 디렉터리는 없다. 현재198개에 성공5개가 자동 합쳐진 상태도 아니다.

## RF 설계와 동일 소스 검증

배치 정책 CAAS-CA/CA-CSRD/CLS × RF 입력 CAAS-CA+U/CA-CSRD+U/CLP+U의 **3×3**을 평가한다.
현재 scalar 11-feature sample은 보존하고, 제안 RF의 CLP 세 성분별 통계15개+U 통계6개(21차원)는
별도 feature version으로 구현해야 한다. CLS는 배치에만 사용하고 RF-CLP 입력에는 α가 없다.
같은 배치 정책의 세 RF는 같은 label을 사용한다. 다른 정책은 자기 측정의 label을 사용한다.
[실험 설계](../../system-prompt-extraction/CHASER%20실험%20상세%20계획.md)를 따른다.

2026-09-24 read-only 대조 결과: 207개×3정책의 실제 소스 해시가 원본과 일치했다.
입력은 policy ID·core 배치를 제외하면 같고 독립 U·캐시 분석값·split도 동일하다.
학습198개의 동일 표현 feature vector는 정책 간 동일하며 소스/feature 불일치0건이다.
`task_characterization.jsonl` 세 파일의 SHA-256은 모두
`61028c1fc7be3706ba74f4599eaa7da307bffe07850dd132e85f6238eb512ce5`다.
Label은 CAAS-CA↔CA-CSRD 38개, CAAS-CA↔CLS 37개, CA-CSRD↔CLS 1개에서 다르다.
실행 배치가 달라지는 ELF의 동일성을 주장하는 것은 아니다.

## 정리 이후 남은 자료와 재실행 한계

현재 `artifacts/periodic/`에는 calibration-v2, candidates-v3, input-freeze-v1,
validation-supplement-v1/v2만 남아 있다. Pilot·feasibility·patterns·public-api·readiness·
load-balance·candidates-v1/v2·characterization-v1·calibration-v1 보고서와 periodic-history,
final-mapping/final-collection/final-replacement 보고서·대체 생성 archive는 삭제됐다.
삭제된 과거 raw의 재검증을 현재 가능하다고 가정하지 않는다.

`input-freeze-v1`과 `candidates-v3`의 README는 각 manifest가 해시로 고정한 생성 당시 보고서다.
그 안의 runtime·label 미수집 표기는 당시 상태이며 현재 진행 상태는 이 문서를 따른다.
해시로 고정한 원본 보고서는 수정하지 않았고 두 manifest의 파일 해시는 모두 일치함을 확인했다.

후보 생성기는 feasibility 파일을 읽는 대신 고정 비용 추정 상수와 과거 요약 hash를 사용한다.
V2 입력 회귀 테스트는 삭제된 archive 대신 동결 fingerprint를 확인한다.

최종 수집·export 관련 `chaser/periodic_final_*`, `tools/rtems_periodic_final_*` 모듈도 현재 작업 트리에 없다.
측정·export 결과와 [수집 당시 코드 snapshot](../../.cache/final-mapping-v1/collection-implementation/)은 남아 있으나,
현재 CLI에서 최종 수집·대체 export를 그대로 재실행할 수는 없다. 재개하려면 필요한 실행 경로와
삭제된 대체 생성 입력·manifest의 복구 가능성을 확인해야 한다. 이번 문서 갱신에서 복구·재측정은 하지 않았다.

## 구조와 읽는 순서

```text
periodic-v2/
├── README.md
├── dataset.json                         # 새 위치 기준 workload/mapping 목록
├── membership.json                      # 원래 소속 파일의 바이트 동일 사본
├── inputs/<workload_id>.json             # 사용207개 설정
├── characterization/<workload_id>/
│   ├── prepared/                        # configuration, ELF, 분석, manifest
│   ├── records/
│   │   ├── features.json
│   │   ├── utilization.json
│   │   └── u0/, u1/, ...                # task별 독립 U10회
│   └── basic-gcp/{g,c,p}/                # 보충 입력4개의 기존 기본 배치 측정
├── calibration/
│   ├── plan.json
│   ├── prepared/<mapping_id>/
│   ├── runs/<mapping_id>/{g,c,p}/
│   ├── frozen-policies.json
│   ├── completion-summary.json
│   └── ...                              # 재사용 감사·예산·실행 기록
└── provenance/
    ├── original-frozen/                 # 원본 population/split/생성 계보 전체
    ├── calibration-v1/                  # 원래 보정 계획·구현 snapshot
    ├── validation-supplement-v1/        # 보충 입력 생성·검증 기록
    ├── validation-supplement-v2/
    ├── collection-records/              # 수집 protocol·summary 등
    ├── files.jsonl                      # 원래 경로→새 경로·파일 hash
    ├── migration-plan.json
    └── migration-verification.json
```

`dataset.json`의 workload 경로는 이 디렉터리 기준이다. `inputs/`에는207개만 있으며,
각 workload의 `snapshot`과 `records`를 읽으면 ELF·feature·U 증거를 찾을 수 있다.
Calibration의 key는 workload ID와 정확한 core 배치로 결정한 mapping ID다.
기존175개 mapping에는 G/C/P가 있고 신규14개에는 P만 있다. Calibration P는
총189개·1,890회이며, 보충 입력의 기본 G/C/P는 다른 배치이므로 섞어 집계하지 않는다.

각 측정 batch에는 `protocol.json`, `measurements.jsonl`, `0.log`~`9.log` 및 실행 코드
snapshot이 있다. `prepared/`에는 `configuration.json`, `build/{g,c,p}.exe`,
`{g,c,p}/plan.json`, `analysis/`, `manifest.json` 등이 있다.

## 입력 JSON에서 workload C 코드 재현

`inputs/<workload_id>.json`의 task 설정을 [make_plan](../../chaser/periodic.py)으로
검증·확장한 뒤 [workload_source](../../chaser/periodic_build.py)로 `workload.c`를 만든다.
다음 예시는 workspace root에서 `candidate-v3-0000`의 C 코드를 `/tmp`에 생성하고,
보존된 snapshot과 바이트 단위로 비교한다. 기존 dataset 파일은 수정하지 않는다.

```sh
python3 - <<'PY'
import json
from pathlib import Path

from chaser.periodic import make_plan
from chaser.periodic_build import workload_source

configuration = json.loads(Path(
    'datasets/periodic-v2/inputs/candidate-v3-0000.json'
).read_text())
tasks = make_plan(configuration, 0)['tasks']
Path('/tmp/candidate-v3-0000-recovered-workload.c').write_text(workload_source(tasks))
PY
cmp /tmp/candidate-v3-0000-recovered-workload.c \
  datasets/periodic-v2/characterization/candidate-v3-0000/prepared/source/workload.c
```

`cmp`의 종료 코드가 0이면 동일하다. 이 입력은 현재 생성기로 보존된 C 코드와
바이트가 일치한다. `source/init.c`·`probe.c`는 입력 JSON에서 생성하지 않고
`rtems/periodic/`의 실행 코드에서 복사한다. 위 명령은 C 코드만 재현하며
ELF·분석·측정을 다시 실행하지 않는다.

## 기존 경로와 호환성

실제 파일과 하위 디렉터리는 `.cache/`에서 이곳으로 이동했다. 기존 `.cache`의 루트·
snapshot·U 디렉터리는 실제 디렉터리로 유지하고 그 자식은 이곳을 향하는 상대 symlink로
연결했다. 따라서 기존 loader가 기록하는 `Path.resolve()` identity는 바뀌지 않는다.
Calibration-v2의 기존350개 재사용 링크도 유지되며, 연결을 따라가면 이곳의 파일을 읽는다.

새 데이터셋 내부에는 symlink가 없다. 기존 `.cache` 경로는 같은 파일의 호환 참조이므로
별도 데이터 사본으로 집계하지 않는다. 기존 artifacts의 소속·연결·동결 원본 파일은
그대로 두었고 필요한 metadata를 이곳에 복사했다. 상세 대응은
[migration-plan.json](provenance/migration-plan.json)과 [files.jsonl](provenance/files.jsonl)에 있다.

원래 plan·manifest·protocol·policy의 바이트와 hash는 바꾸지 않았다. 이 파일들의 절대경로와
`membership.json`의 생성 당시 pending 필드는 역사적 기록이다. 현재 위치는 `dataset.json`,
보정 완료는 [completion-summary.json](calibration/completion-summary.json)을 기준으로 읽는다.
기존 보정 CLI 재검증은 [기존 명령](../../artifacts/periodic/calibration-v2/README.md)을 사용한다.

## 보관 범위와 검증

제외된 원본4개와 V1-0001의 실행·측정 증거는 기존 위치에 남겼다. 다만 원본 frozen manifest와
생성 계보를 재검증하려면 전체 원본 입력이 필요하므로 `provenance/original-frozen/`에는
제외 입력의 config도 포함한다. 이 provenance를 사용 population으로 읽으면 안 된다.

대용량 payload와 provenance는 Git에서 제외하며, 이 README와 `dataset.json`을 관리한다.
Git 저장만으로 데이터가 백업되지는 않는다. 디렉터리 전체를 복사하면 파일 payload는 함께
옮길 수 있지만, 다른 workspace에서 기존 CLI를 재실행하려면 역사적 절대경로 연결과
별도의 toolchain/simulator 환경이 필요하다. 이동된 snapshot을 새 측정용으로 수정하지 않는다.

이동 검증 요약은 [relocation-summary.json](../../artifacts/periodic/calibration-v2/relocation-summary.json)에
보존한다. 파일 hash·디렉터리 identity 검사는 workspace에서 다음 명령으로 재실행할 수 있다.

```sh
PYTHONPATH=. python3 artifacts/periodic/calibration-v2/relocate_dataset.py verify
```
