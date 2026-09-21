# TACLeBench 관찰에서 일반화한 읽기 원형 v2

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

두 역할은 같은 `window-coefficient` 계보다. 2개 bank와 n:2n 크기 관계는 합성 설계 선택이다.
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

생략: DCT 연산, 같은 쌍의 source 재참조, in-place store. 두 역할은 `block-phase` 계보다.
n=2에서는 두 역할의 접근열이 같으므로 정확성 검증 외 후보에는 사용하지 않는다.
