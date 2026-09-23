# Periodic dataset v2

이 디렉터리가 사용207개 입력과 validation 보정 증거의 실제 저장 위치다.
데이터 목록은 [dataset.json](dataset.json), 소속 원문은
[membership.json](membership.json)에 있다. Train/validation/test는 **126/41/40**이며
표본 단위는 taskset 하나다. θ/policy는 동결됐고, 최종 G/C/P label과 RF dataset은 아직이다.

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
