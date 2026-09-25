# TACLeBench 관찰에서 일반화한 읽기 원형 v2

현재 본실험은 5개 워크로드군 **각각의 고유 taskset**을 train/test/validation
60%/20%/20%로 나누는 [분할 정책](README.md#main-experiment-split-policy)을 따른다.
아래 워크로드군 단위 split 수치는 보존된 후보 생성 당시의 초안이다.
현재 [입력·split 동결본](../../artifacts/periodic/input-freeze-v1/README.md)은 V3 고유 입력
207개를 train 126 / validation 41 / test 40개로 배정했다. 다음은 독립 U·정적 feature
수집이며, validation θ/policy 동결 후 최종 G/C/P label과 RF를 준비한다.

이 문서는 합성 입력의 계약이다. Benchmark 코드·입력·trace를 실행하거나 학습 표본으로
사용하지 않는다. **PolyBench는 외부 평가용이며 원형 도출·입력 선정·튜닝에서 제외한다.**

조사 revision은 TACLeBench `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`이다.
출처의 source 수준 접근 관계 중 아래에 명시한 부분만 일반화한다. Benchmark의 산술,
store, floating-point 폭, 실제 working set 분포나 실행 시간을 대표하지 않는다.

## 공통 계약

- `width = n`: 2~32의 짝수. `distinct = B*M`: 완전한 block B개, 각 block의 위치 수 M.
  Width/크기/stride/sweep/period 변화는 독립 family가 아니다.
- `READ(i)`는 해당 task의 private volatile byte array에서 `data[i*stride]`를 읽는다.
  아래 식은 block 내부 상대 index다. Block b의 모든 index에 `b*M`을 더한다.
  한 sweep에서 block을 0부터 순서대로 방문하며, job은 이를 `sweeps`회 반복한다.
- 여러 원본 배열은 하나의 private buffer 안에 **서로 겹치지 않는 영역**으로 놓는다.
  Block 사이의 영역도 공유하지 않는다. 모든 `distinct` 위치를 실제로 방문한다.
- 아래 순서는 합성 stream에 명시적으로 부여한 순서다. C 원본의 피연산자 평가 순서나
  register 재사용을 복제했다고 주장하지 않는다. 각 READ는 별도 C statement로 생성한다.
- 계수 재사용은 block 내부에 한정된다. 큰 배열을 여러 block으로 확장할 때 하나의 전역
  계수 영역을 공유하는 형태와 다르다. Stride는 byte 위치 간격이며 다중 byte load가 아니다.
- 원본의 output store를 load로 치환하지 않는다. 최종 checksum은 접근 보존용이며 원본
  계산 정답/성능 label이 아니다. U/label은 이후 실제 CHASER 측정으로만 얻는다.

## W: 입력 window와 계수 영역

근거: [fir2dim 계산 loop](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/fir2dim/fir2dim.c#L155-L181),
[filterbank FIR](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/filterbank/filterbank.c#L113-L150),
[fmref LPF와 equalizer](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/sequential/fmref/fmref.c#L193-L272).

보존: 이웃 출력 사이 입력 중첩, 입력/계수의 원소별 결합, 같은 입력에 대한 계수 bank 교체.
생략: FIR의 2D pitch, 경계 길이 변화, decimation, 중간/output 쓰기, buffer compaction.
이 버전은 고정 길이의 **1D 읽기 window**이며 fir2dim 전체를 대표하지 않는다.

`window-coeff`: M=3n. 입력 [0,2n), 계수 [2n,3n). 한 block에 2n(n+1) loads.

```c
for (w = 0; w < n+1; ++w)
    for (i = 0; i < n; ++i) {
        READ(w+i);
        READ(2*n+i);
    }
```

`window-bank`: M=4n. 같은 입력과 두 계수 bank. 한 block에 4n(n+1) loads.

```c
for (w = 0; w < n+1; ++w)
    for (bank = 0; bank < 2; ++bank)
        for (i = 0; i < n; ++i) {
            READ(w+i);
            READ(2*n+bank*n+i);
        }
```

두 역할은 같은 `window-coefficient` 워크로드군이다. 2개 bank와 n:2n 크기 관계는 합성 설계 선택이다.
기존 `overlap`은 input 중첩만 있는 부분 대조군이며 계수 결합을 포함하지 않는다.

## M: 다중 배열의 재사용

근거: [st의 통계 pass·같은 index 결합](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/st/st.c#L160-L217),
[matrix1의 물리 layout·계산](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/matrix1/matrix1.c#L136-L160).

`paired-pass`: M=2n. A=[0,n), B=[n,2n). 한 block에 6n loads.
보존: A 반복 pass, B 반복 pass, A[i]/B[i] 결합 순서.
생략: scalar 통계 상태, 마지막 pass의 source 표현식 재참조, 산술.

```c
for (r = 0; r < 2; ++r)
    for (i = 0; i < n; ++i) READ(i);
for (r = 0; r < 2; ++r)
    for (i = 0; i < n; ++i) READ(n+i);
for (i = 0; i < n; ++i) {
    READ(i);
    READ(n+i);
}
```

`matrix-reuse`: M=2n². A는 row-major, B는 column-major. 한 block에 2n³ loads.
보존: column별 A 반복 순회, row별 B의 같은 연속 열 구간 재사용.
생략: C 전체 영역과 누산 load/store. 두 배열만 남긴 읽기 투영이다.

```c
for (c = 0; c < n; ++c)
    for (r = 0; r < n; ++r)
        for (i = 0; i < n; ++i) {
            READ(r*n+i);
            READ(n*n+c*n+i);
        }
```

두 역할은 서로 다른 재사용 관계지만 같은 혼합 recipe에서 사용하므로
`multi-array-reuse`로 보수적으로 함께 묶는다. 동일 알고리즘이라는 뜻이 아니다.
기존 F1 all-pairs와 F6의 C-load 포함 contraction을 그대로 등록하지 않는다.

## B: block 내부의 행→열 단계 변경

근거: [jfdctint의 두 pass](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/jfdctint/jfdctint.c#L176-L297).
두 역할 모두 M=n², 한 block에 2n² loads. Phase 사이에 동일 위치를 재참조한다.

`row-column`은 대칭 쌍까지 추출하지 않은 단순 순회 대조 역할이다.

```c
for (r = 0; r < n; ++r)
    for (c = 0; c < n; ++c) READ(r*n+c);
for (c = 0; c < n; ++c)
    for (r = 0; r < n; ++r) READ(r*n+c);
```

`row-column-mirrored`는 각 행/열 안에서 대칭 위치를 묶는다.

```c
for (r = 0; r < n; ++r)
    for (i = 0; i < n/2; ++i) {
        READ(r*n+i);
        READ(r*n+n-1-i);
    }
for (c = 0; c < n; ++c)
    for (i = 0; i < n/2; ++i) {
        READ(i*n+c);
        READ((n-1-i)*n+c);
    }
```

생략: DCT 연산, 같은 쌍의 source 재참조, in-place store. 두 역할은 `block-phase` 워크로드군이다.
n=2에서는 두 역할의 접근열이 같으므로 정확성 검증 외 후보에는 사용하지 않는다.
V2 후보의 n=8에서는 다르다. 기존 F5의 매번 전치 쌍 교대와 구분한다.

## 워크로드군·구성·검증

기존 10종은 부분 특성을 통제하는 대조군으로 남긴다. 새 6종은 기존 kernel을 호출하거나
base-task를 복사하지 않는다. 부분 loop 특성의 공통성만으로 모든 scan을 같은 family로
합치지는 않지만, 완전한 base-task/recipe를 공유하면 registry의 전이 병합 규칙을 적용한다.
이 설계의 3개 워크로드군은 통계적 독립성 증명이 아니다. 이후 원형 재사용 관계가 발견되면 병합한다.

V2는 W/M/B 각각 60개, 총 180개 입력 후보다. 각 set은 같은 그룹의 두 역할을 섞는다.
4/8/12/16 tasks × 아래 5개 cell × 목표 U 0.5/1.0/1.5다. 모든 후보는 n=8.

| Cell | 역할 A:B | 크기·stride | Period 비율 반복 |
|---|---|---|---|
| layout-half | 1:1 | 각 2 blocks, stride 1/32/4096 반복 | 1:2 |
| l1-half | 1:1 | 480 이하/544 이상 위치를 완전 block으로 내림/올림, stride32 | 1:2 |
| l1-skew | 3:1 | 같은 L1 전후 크기 규칙, stride32 | 1:2:4:2 |
| llc-one | 1:1 | 첫 task만 65536 초과 위치, 나머지 2 blocks, stride32 | 1:2 |
| llc-two | 1:1 | 첫 두 task 각각 65536 초과 위치, 나머지 2 blocks, stride32 | 1:2:4:2 |

이는 전체 factorial 설계가 아니라 선택한 대비 cell이다. Role·core·period의 상관도 남아
있으므로 개별 요인의 인과 효과를 분리한 설계라고 주장하지 않는다. Core는 i%4의 임시 배치다.
추정 CPU/U와 sweep·period 계산은 v1의 개발 비용 규칙을 재사용한다. 새 구조 적용 타당성은
미검증이며 최종 독립 U를 대신하지 않는다. 세 그룹만으로 split은 1/1/1 family 초안이다.
최종 규모·워크로드군 다양성·RF 충분성·실측 적격성은 미확정이다. V1과 결과를 자동 합치지 않는다.

작은 수작업 literal trace, block 이동·반복, 전체 footprint 방문, 허용/거부 shape,
G/C/P 최종 ELF의 linked stream을 검사한다. 정확성 fixture는 후보 membership에서 제외하고
timing/label 선택에 사용하지 않는다. 참고 구현: `chaser/periodic/recipes.py`.
