# RTEMS 실험 생성·수정·재현 안내

갱신: 2026-09-28. 모든 명령과 상대경로는 현재 workspace root 기준이다.
다중 배열 구현 worktree는 `/workspace/experiments-array-support/chaser`다.
여기서는 소스·ELF 생성과 laysim 실행을 다룬다. 보드 실행은
[HW 절차](HARDWARE-VALIDATION.md)를 따른다.
공용 periodic harness의 legacy paired-pass와 schema v2 다중 배열을 설명한다.
새 worktree에서는 버전 관리되는 [다중 배열 예제](experiment-guide/INPUTS.md#multi-array)로 시작할 수 있다.
기존 paired-pass·false-sharing의 `.cache` 입력·전용 실행기·raw는 이전 실험의
로컬 산출물로, 이 worktree에 포함되어 있지 않다. 해당 예시를 재현하려면 원본을
별도로 확보하고 출처와 hash를 기록한다. 다른 worktree의 build/output은 공유하지 않는다.

현재 연구는 **SIM 실험을 먼저 진행해 구성·결과를 확정한 뒤 HW에서 검증**한다
(2026-09-27 사용자 지시). HW 가이드는 후속 검증용이며 다음 작업은 SIM 실험의
재집계·변수 통제·재현성 확인이다.

## 문서 목차

절 번호는 분리 전 가이드의 번호를 유지한다.

- §1–2 [입력·다중 배열 예제](experiment-guide/INPUTS.md)
- <a id="multi-array"></a>§2.2 [다중 배열 입력 계약](experiment-guide/INPUTS.md#multi-array)
- <a id="multi-array-verification"></a>§2.4 [다중 배열 검증 기록](experiment-guide/INPUTS.md#multi-array-verification)
- <a id="3-공용-생성기로-빌드실행"></a>§3 [공용 빌드·SIM 실행](experiment-guide/EXECUTION.md#build-and-run)
- §4 [환경 수정](experiment-guide/CUSTOMIZATION.md)
- §5 [false-sharing 재현](experiment-guide/EXECUTION.md#false-sharing)
- §6 [동일 ELF 재실행과 재빌드](experiment-guide/EXECUTION.md#reproducibility)
- <a id="7-raw-로그-위치와-읽는-법"></a>§7 [Raw 로그 조회·해석](experiment-guide/RAW-LOGS.md#raw-logs)
