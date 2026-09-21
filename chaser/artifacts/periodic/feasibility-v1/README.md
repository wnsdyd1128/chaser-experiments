# Periodic 개발 probe와 자원 경계 검증

2026-09-21. 공개 측정 계약 v2와 같은 G/C/P workload object를 유지해 개발용
11개 probe의 분석·반복 실행을 검증했다. **Timing/U 550/550회가 성공했다.**
Backend는 laysim-GR740이며, 최종 RF 학습 데이터·독립 family 충분성·hardware cache
정확도의 증거가 아니다. Label/RF는 생성하지 않았다.

## 고정 입력과 검증 범위

입력 생성은 [개발 도구](../../../tools/rtems_periodic_probes.py)의 `configurations()`와
`boundary_configurations()`를 따른다. `suite.json`, 개별 configuration, 생성 C,
G/C/P ELF, APE, 전체 분석 event와 manifest를 archive에 보존했다.
모든 구성은 같은 개발 family이며 `eligible_for_training=false`, `test_eligible=false`다.

| Probe | Target 입력 | q | Period / horizon |
|---|---|---:|---|
| 정규화·충돌 3개 | D=64, stride=1/32/4096 B | 160 | 20 / 40 ms |
| L1 경계 3개 | D=511/512/513, stride=32 B | 21/20/20 | 20 / 40 ms |
| LLC 경계 3개 | D=65535/65536/65537, stride=32 B | 2 | 100 / 200 ms |
| Hot/cold | H=64, C=1024, H 4회→C 1회 | 8 | 20 / 40 ms |
| Phase | H=64, C=1024, H 4회→C 4회 | 3 | 20 / 40 ms |

Companion은 D=64, stride=32, q=160이며 target과 period가 같다. 두 task 모두 두 job을
실행하고 explicit core 0/1 배치를 사용한다. q는 `max(2, ceil(10240 / sweep 접근 수))`로
정했다. 이 값들은 개발 feasibility 입력이며 목표 U가 아니다. Smoke 이후 G/C/P 결과에
맞춰 q·period·horizon을 변경하지 않았다. Phase의 cold 반복 수는 이전 patterns-v1 예제와
다르므로 두 artifact를 동일 구성으로 비교하지 않는다.

분석 모델은 32-byte line, L1 16 KiB/4-way, LLC 2 MiB/4-way다. 11개 probe 모두 최종
G/C/P ELF의 접근 count/order/address/size/kind와 locality 일치 검사를 통과했다.
Cyclic 9개 × q=1/2 × G/C/P의 54개 plan/source 검사와 기존 작은 수작업 접근열·실제
ELF 통합 테스트도 확인했다. RD/CSRD 계산은 yarda_cpp가 담당한다.

## 실행 결과

| 구분 | 시도 / 성공 | 성공한 job |
|---|---:|---:|
| 11개 probe smoke | 55 / 55 | 176 |
| G/C/P timing + 독립 U | 550 / 550 | 1760 |
| 별도 G/C/P 진단 | 33 / 33 | 132 |
| 독립 empty | 110 / 110 | 220 |

경계 구성은 full-stream 분석과 별도의 build/runtime 검증이다.

| 경계 | 결과 |
|---|---|
| 4/8/12/16 tasks, D=64, q=2, period=20 ms, 두 jobs/task | G/C/P 12/12 성공 |
| LLC 초과 task 하나(D=65537) + 작은 task 15개, q=2, period=100 ms | G/C/P 3/3 성공 |
| 16 tasks × 1 MiB, q=2, period=100 ms, 두 jobs/task | 정확히 16 MiB 배치/빌드 성공; G/C/P 모두 deadline miss·postponed job |
| 균등 4096 jobs: 16 tasks × 256 jobs, period=1 ms | G/C/P 모두 600초 timeout, 출력 미완결 |
| 비균등 4096 jobs: periods=[1]+[4081]×15 ms, horizon=4081 ms | G/C/P 모두 600초 timeout, 출력 미완결 |
| 추가 64/256 jobs: 16 tasks, period=1 ms, q=1 | 별도 구성으로 G/C/P 6/6 성공 |

16 MiB 구성은 각 task D=32768, stride=32이며 padding 포함 정확한 한도다.
실패한 period를 늘려 같은 구성의 성공으로 교체하지 않았다. 각 실패 run은 21개의
job 레코드를 보존했고, 전체 32개 job 완료로 인정하지 않는다. Deadline 실패는
simulator exit 0이어도 측정 실패다.

4096-job timeout은 로그 출력 도중 발생했다. 잘린 마지막 JSON 때문에 runner에
`jobs`가 없는 실패 row도 있으며, 보고서는 이를 실패로 보존한다. 수신하지 못한 job의
완료·checksum·deadline을 추정하지 않는다. 64/256-job 추가 입력은 출력 비용이 드러난
뒤 별도 version/output으로 만든 개발 실험이며 기존 4096-job 시도는 모두 남긴다.

Primary 수집은 **772회 중 763회 성공, 성공한 job 2624개**다. 실패 9회는
4096-job timeout 6회와 16 MiB 구성의 deadline 실패 3회다. 별도 환경 실패/확인과
추가 job-budget 실험까지 합치면 **860회 중 770회 성공, 성공한 job 3586개**다.
실패 run에서 남은 부분 레코드는 성공 job 합계에 포함하지 않는다.

## 비용과 본실험에 주는 제약

- 19개 기본 구성 build wall 합계 13.63초, 11개 probe 분석 wall 합계 48.66초.
  작은 probe 분석은 약 1.95–2.28초, peak RSS 약 83–84 MiB;
  LLC 경계는 약 10.50–11.21초, 약 383 MiB였다.
- Smoke 62.25초, 반복 timing/U 325.34초, 진단 77.64초, empty 104.83초였다.
  각 collector의 wall time이며 경계 수집 등과 겹쳤다. Worker 수는 각각 4/8/4/4;
  별도 경계 collector와 job-budget collector도 실행했으므로 독립적인 1/4/8-worker
  scaling benchmark나 전체 기간의 합계로 해석하지 않는다.
- 16-task 32-job 구성은 약 27.4–28.0초, 64-job은 48.8–50.7초,
  256-job은 179.2–183.3초였다. 실용적인 job 수와 출력 예산을 별도로 정해야 한다.
  이 관측을 모든 workload의 runtime 상한으로 일반화하지 않는다.
- 논리 4096-job 한도와 정적 record 할당은 다르다. 균등 구성은 4096 slots/
  655360 B, 비균등 구성은 65296 slots/10447360 B다. 모든 ELF에 dispatch buffer
  524288 B도 있다. Workload data 16 MiB는 전체 RTEMS 메모리 한도가 아니다.
- Empty 평균 CPU는 약 7301.5–7506 ns. 같은 P ELF의 독립 core-0 target 평균 CPU 대비
  0.037–0.745%이며 차감하지 않았다. 모든 task/topology의 총 계측 비용 비율은 아니다.
  Target U는 약 0.0490–0.2018, companion U는 약 0.00983–0.04911이었다.

정확한 task별 U·locality·활성 line 수/할당량·linked set occupancy·비용은
[summary.json](summary.json)에 있다. RSS는 Linux `wait4`가 보고한 프로세스 high-water
mark 중 최대이며 동시 프로세스 RSS 합이 아니다. 파일 크기는 hardlink·압축을 반영하지
않은 논리 크기다. 시도별 wall에는 입력 hash 검사·실행·파싱이 포함된다.

다음은 독립 U 기반의 sweep/period/horizon 선택 규칙, U 목표 오차와 자원 예산을 정하고,
계보 누출 검사·전역 task identity를 갖춘 registry를 만드는 작업이다. 초기/확장 pool,
학습곡선 충분성 기준과 family split은 아직 동결하지 않았다. 현재 11개 probe나 반복
횟수로 학습 데이터 충분성을 주장하지 않는다. 4096-job 수집과 16 MiB/100 ms 구성의
runtime 성공도 주장하지 않는다.

## 환경 실패와 재현성

최초 root의 smoke 55회와 boundary 24회는 X display 연결 실패로 RTEMS 시작 전에
종료됐다. 별도 display 확인 3회 중 기존 remote display와 sandbox의 local 연결은
실패했고, local Xvfb를 접근할 수 있는 실행 1회가 성공했다. 이를 primary 수집과 분리했다.
같은 immutable snapshot을 새 root에서 사용했으며 기존 시도를 덮어쓰지 않았다.

Ubuntu Xvfb와 필요한 라이브러리는 `/tmp`에 추출했다. Xvfb 사본의 NUL 종료
`/usr/bin` 문자열 하나를 `/tmp/cxb`로 바꿔 추출한 xkbcomp를 찾게 했다. Simulator와
workload ELF는 변경하지 않았다. 가상 display는 Unix socket만 사용했다. 사용한 deb,
원본/사본 hash와 변경 이유는 supplementary archive의 `virtual-display/provenance.json`에
있다. 시스템 패키지는 설치하지 않았다.

원본은 `/tmp/chaser-periodic-feasibility-v1-r1`(display 실패), `-r2`(본 수집),
`/tmp/chaser-periodic-feasibility-job-budget-v1`(추가 job 수)다. R2는 r1의 immutable
snapshot을 hardlink로 재사용했다. Archive 안의 절대 경로는 당시 provenance다.

## 보존 파일과 검증

- `snapshots-small.tar.gz`, `snapshots-capacity.tar.gz`: 합쳐서 19개 기본 snapshot,
  config/suite 및 q=1/2 검사.
- `measurements.tar.gz`: primary raw 로그·batch protocol·수집/build/analysis 비용,
  독립 U 재계산, collector 구현 및 환경 기록.
- `supplementary.tar.gz`: display 실패 79회, 확인 실행 3회, 추가 64/256-job의 전체
  snapshot과 실행 6회, 가상 display 의존성. [supplementary.json](supplementary.json)에 집계.
- `implementation.tar.gz`: Python 구현, periodic 테스트와 실행 문서/검증 명령.
- [verification.txt](verification.txt): `scripts/verify`, **341 passed in 49.16s**.
  이번 변경의 finalize는 명시 요청이 없어 실행하지 않았다.
- [manifest.json](manifest.json): 문서·요약·스크립트·archive·verifier log의 SHA-256.
  `revalidation.json`은 이 manifest를 검사한 별도 재검증 결과다.

동일 SDK가 있는 환경에서 fresh 경로에 다음과 같이 추출·재검사한다.

```sh
artifact="$PWD/artifacts/periodic/feasibility-v1"
mkdir -p /tmp/chaser-feasibility-review/main
tar -xzf "$artifact/snapshots-small.tar.gz" -C /tmp/chaser-feasibility-review/main
tar -xzf "$artifact/snapshots-capacity.tar.gz" -C /tmp/chaser-feasibility-review/main
tar -xzf "$artifact/measurements.tar.gz" -C /tmp/chaser-feasibility-review/main
tar -xzf "$artifact/supplementary.tar.gz" -C /tmp/chaser-feasibility-review
tar -xzf "$artifact/implementation.tar.gz" -C /tmp/chaser-feasibility-review
PYTHONPATH=/tmp/chaser-feasibility-review/implementation python3 "$artifact/revalidate.py" \
  /tmp/chaser-feasibility-review --output /tmp/chaser-feasibility-review-result.json
```

재검사는 archive hash, 모든 raw batch, 성공/실패 상태, 독립 U 및 두 요약의 일치를
확인한다. Build 당시 collector는 이후 추가한 config/analysis 연결 gate 전 버전이며,
실행 시 사용한 collector 사본은 `collector-implementation`에 보존했다. 동일 gate를
보고서에서 전체 snapshot에 다시 적용한다.
