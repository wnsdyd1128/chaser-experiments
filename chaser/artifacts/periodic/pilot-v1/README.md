# Periodic harness pilot

2026-09-20. **최종 batch의 790/790 독립 실행이 통과했고, 10개 taskset의 임시
G/C/P label과 4종 표현의 11-feature 행 40개를 생성했다.** RF 학습·θ 보정·최종
train/validation/test split은 수행하지 않았다. Backend는 laysim-GR740이며 silicon 측정이 아니다.

## 범위와 결과

4–6개 periodic task, task별 10/20 ms period, 공통 40 ms horizon을 사용했다.
각 job은 9600개 byte load를 수행하는 고정 반복 wrapper다. 데이터 배열은 task별로
독립이고 G/C/P·반복 실행 사이에 동일한 source·sweep·주소 배치를 유지한다.
Policy는 `pilot-explicit-core-order-v1`의 명시적 core 배치이며 보정된 θ를 사용하지 않는다.
모든 변형은 **하나의 pilot family**다. 40개 행은 독립적인 RF 표본 40개가 아니다.

| 항목 | 결과 |
|---|---:|
| G/C/P 실행 | 10 tasksets × 3 × 10 = 300회 |
| 독립 U 실행 | 49 task instances × 10 = 490회 |
| 최종 batch 실패·제외 | 0회 / 0 tasksets |
| 측정 job | 5,840개, 그중 독립 U job 1,460개 |
| 독립 job CPU 시간 범위 | 0.910324–1.627460 ms |
| 임시 label 분포 | G=3, C=2, P=5 |
| Feature 행 | CAAS-CA / CA-line / CA-CSRD / CLS(0.5), 각 10개 |
| 8 process 병렬 수집 경과 시간 | 718.79 s (약 12분) |
| 개별 simulator 실행 wall time 합 / 평균 | 5,513.36 s / 6.98 s |
| 독립 U 수집 wall time 합 | 1,740.32 s |
| 비압축 build·analysis·measurement 자료 | 약 765 MB |

탐색 목표는 job당 1–3 ms였으며 일부 kernel은 1 ms보다 약간 짧았다. Architecture별로
sweep을 바꿔 시간을 맞추지 않았고 sleep을 CPU 작업량으로 세지 않았다. 위 wall time은
8개 process가 병렬 실행되는 환경에서 관측한 비용이며 target TET/TAT와 다르다.

아래 값은 전체 job 응답시간 합인 **TAT의 10회 median, 단위 ms**다. Makespan이나
평균 job 실행시간이 아니다. 이 표는 label 생성 경로를 검증하며 architecture 우열이나
CAAS 대비 성능 개선을 주장하지 않는다.

| Taskset | Tasks | G TAT | C TAT | P TAT | 임시 label |
|---|---:|---:|---:|---:|---|
| pilot-00 | 4 | 18.106 | 17.964 | 17.884 | P |
| pilot-01 | 5 | 24.848 | 24.876 | 24.803 | P |
| pilot-02 | 6 | 33.938 | 38.569 | 37.934 | G |
| pilot-03 | 4 | 16.412 | 16.376 | 16.203 | P |
| pilot-04 | 5 | 24.077 | 27.579 | 27.653 | G |
| pilot-05 | 6 | 28.766 | 29.504 | 31.501 | G |
| pilot-06 | 4 | 14.587 | 14.559 | 14.406 | P |
| pilot-07 | 5 | 20.207 | 20.114 | 24.441 | C |
| pilot-08 | 6 | 34.821 | 33.010 | 33.266 | C |
| pilot-09 | 4 | 16.541 | 16.511 | 16.348 | P |

원시 단위는 ns 정수다. [summary.json](summary.json)에 median TAT/TET와 task별 U,
[provisional_samples.jsonl](provisional_samples.jsonl)에 feature·label 근거를 보존한다.
모든 행은 `eligible_for_training=false`, `split_group=pilot`이다.

## 검증과 수정 기록

- 실제 G/C/P EDF SMP scheduler 소유 core와 affinity, nominal release·watchdog·EDF
  deadline, job 완결성·checksum·CPU accounting epoch를 검사했다.
- 49개 job wrapper를 각각 G/C/P의 최종 ELF로 분석했다. 접근 수·순서·주소·크기·종류와
  coverage, CA/CSRD/CLP/CLS가 일치했다. 주소를 옮긴 실제 ELF는 검사에서 거부된다.
- 별도 trace에서 G와 C 공유 domain 안의 migration, P singleton 실행을 확인했다.
  Trace는 timing dataset에 포함하지 않는다.
- Empty-job 10회, 20개 job의 CPU 계측 비용은 3,719–6,248 ns, 평균 4,983.5 ns였다.
  이 값을 workload 측정에서 빼지 않았다.
- 단 하나의 마지막 job이 period를 초과하는 실행을 의도적으로 만들었다.
  Deadline miss·expired period·postponed job이 실패로 보존됐다.
- `--mode 16`이 같은 P ELF에서 16번째 task만 core 0에 실행하는 경계도 확인했다.
- 전체 verifier: **283 passed in 47.79s**. Cold Cachegrind 설치본을 지정했다.
  [verification.log](verification.log)에 실제 출력을 보존한다.
- 최종 parser로 790개 raw log를 다시 읽고 모든 집계·임시 feature 행의 재생성 일치를
  확인했다. [revalidation.json](revalidation.json)에 구현 hash와 결과를 기록했다.

초기 batch는 ns epoch 검증이 작은 음의 sub-tick 차이까지 오류로 처리해 중단했다.
실제 watchdog/EDF deadline tick은 예정 표와 일치했다. 이후 tick 일치 검사는 유지하고
epoch의 절대 차이가 1 tick 미만인지 검사하도록 수정했다. Completion deadline에는
slack을 추가하지 않았다. 초기 batch의 완결 기록 295개(당시 성공 110, 실패 185)와
시작된 raw log 303개는 [aborted-batch.json](aborted-batch.json) 및 별도 archive에 남겼다.
초기 성공 기록도 최종 batch에 섞거나 실패 run을 개별 교체하지 않았다.

측정 완료 후 malformed JSON record 처리와 boot mode의 명시적 hexadecimal 표기를
보강했다. 실제 성공 데이터의 집계는 바뀌지 않았고, 최종 parser 재검사·mode 16 실행·
회귀 테스트로 확인했다. 각 batch의 `implementation/`과 protocol에 당시 runner/parser
코드와 hash가 남아 있다.

## 보존 자료와 재현

- `pilot-00.tar.gz` ~ `pilot-09.tar.gz`: 각 snapshot의 source, waf/wscript/config,
  linker 설정, 실제 compile database, workload object, G/C/P ELF, LLVM/APE,
  YARDA 결과·접근 event·명령·manifest 전체.
- [measurements.tar.gz](measurements.tar.gz): 최종 790회 raw log·job record·protocol,
  boot batch, 구현 snapshot, U 및 임시 feature 결과.
- [diagnostics.tar.gz](diagnostics.tar.gz), [diagnostics.json](diagnostics.json): trace,
  empty-job, 의도적 overrun과 사용한 실행 snapshot. `mode16.tar.gz`는 별도 경계 실행이다.
- [aborted-batch.tar.gz](aborted-batch.tar.gz): 초기 중단 batch를 원형 보존.
- `implementation.tar.gz`: 최종 harness·parser·adapter·feature/label 계산 코드.
- [manifest.json](manifest.json): 이 디렉터리 산출물의 SHA-256. Snapshot 내부 manifest는
  개별 파일 hash를 추가로 검증한다.

원본 작업 경로는 `.cache/periodic-pilot-v1`와 `.cache/periodic-pilot-runs-v2`다.
새 측정은 [harness README](../../../rtems/periodic/README.md)의 `prepare` → `analyze`
→ `run` 명령을 사용하며, 기존 output은 덮어쓰지 않는다. Archive를 이동하면
compile database와 당시 명령의 절대 경로는 원래 provenance로 보존된다. 재빌드는 새
snapshot에서 수행한다. 설치된 RTEMS SDK·laysim·Clang/opt·YARDA가 필요하다.

다음 단계는 본실험의 workload/family 다양성과 규모·예산 결정, family split 고정,
validation mapping별 θ·policy 동결, 최종 label 수집과 RF 학습이다. 이 pilot family는
최종 held-out test에 넣지 않는다. GR740 hardware cache trace/counter 검증도 남아 있다.
