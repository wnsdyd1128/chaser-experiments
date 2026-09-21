# TACLeBench 단계·삼각 범위 읽기 원형

V2의 window/multi-array/block-phase에 두 보수적 워크로드군을 추가한다. 출처 revision은
`c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`이며 파일 hash는
[staged-recipe-sources.json](staged-recipe-sources.json)에 있다. 보존 조사본을 읽었다.
PolyBench는 사용하지 않는다. Benchmark 프로그램·입력·trace는 학습 표본이 아니다.

공통 `READ(i)`는 private volatile byte buffer의 `i*stride`를 읽는다. 각 block은
아래 M개 위치를 모두 방문하며 block 사이 영역은 겹치지 않는다. 전체 block을 순서대로
방문하는 sweep을 `sweeps`회 반복한다. `distinct`는 M의 양의 배수다. Stage/삼각 row는
Python 생성 시 펼치고 C에는 literal-bound affine loop만 남긴다. 원본의 값·산술·store·
자료형 폭·compiler load 수·C 표현식 평가 순서와 동일하다고 주장하지 않는다.

## F: Staged butterfly와 twiddle 재사용

근거: [fft.c 140–192행](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/fft/fft.c#L140-L192).
Source는 stage의 butterfly 거리를 배증하고 lane마다 twiddle 쌍을 한 번 읽어 여러
group에 사용한다. Complex p/q의 반복 source 표현식은 합성 stream에서 각각 한 번으로
줄인다. 이는 원본 compiled trace의 복제가 아니라 명시적으로 축약한 read-side 계약이다.

Width n은 2/4/8/16/32. M=4n−2, data D=[0,2n), 계수 T=[2n,4n−2).

```text
for h in 1,2,...,n/2:                 # 생성 시 stage를 펼침
    for lane in 0..h-1:
        READ(2n+2(h-1+lane)); READ(2n+2(h-1+lane)+1)
        for group in 0..n/(2h)-1:
            q = 2(2h*group+lane); p = q+2h
            READ(p); READ(p+1); READ(q); READ(q+1)
    if butterfly-scale:
        for i in 0..2n-1: READ(i)
```

- `butterfly-twiddle`: stage별 결합만 유지, loads=2(n−1)+2n·log₂n.
- `butterfly-scale`: 각 stage 끝의 전체 data scan 추가, loads=2(n−1)+4n·log₂n.
  Scan은 source scaling RMW의 **read 부분**이며 store를 load로 치환한 것이 아니다.
- Twiddle은 group마다 다시 읽지 않는다. Bit reversal, complex 산술, in-place update,
  scaling 산술은 생략한다. A는 scaling read phase도 생략한다.
- 두 역할은 `staged-butterfly` 하나의 워크로드군이다. n=2의 A는 각 위치를 한 번만 읽어
  reuse-normalized cyclic으로 퇴화하므로 정확성 fixture에만 쓴다. 후보 n=8을 사용한다.

## T: 전진/후진 삼각 행렬·벡터 결합

근거: [ludcmp.c 135–159행](https://github.com/tacle/tacle-bench/blob/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/ludcmp/ludcmp.c#L135-L159).
원본의 forward/back substitution에 있는 증가 prefix와 감소 row의 suffix 결합을
보존한다. 그 앞의 LU factorization·eps 조기 반환·계산·값 갱신은 포함하지 않는다.

Width n은 정수 2~32. M=n²+3n−1. 비중첩 영역 A[n²], B[n], Y[n], Xslice[n−1]를
순서대로 놓는다. Source에서 X[0]은 쓰지만 읽지 않으므로 Xslice[j−1]은 원본 X[j]의
읽기 위치 역할만 보존한다. 원본 A의 pitch50은 합성 pitch n으로 일반화한다.

```text
for r = 0..n-1:
    READ(B[r])
    for j = 0..r-1: READ(A[r,j]); READ(Y[j])
for r = n-1..0:
    READ(Y[r])
    for j = r+1..n-1: READ(A[r,j]); READ(Xslice[j-1])
    READ(A[r,r])
```

- `triangular-solve`: A[r,j] 주소는 r*n+j.
- `triangular-solve-transposed`: 합성 저장 배치 대비로 j*n+r 사용.
- 두 역할은 동일한 첫 등장 정규화 재사용 순서를 가지며 **공간 배치 대비**다.
  다른 temporal reuse나 독립 family로 세지 않는다. 둘 모두 `triangular-solve` 워크로드군,
  block당 loads=2n²+n이다. 모든 matrix/vector 위치를 실제 방문한다.
- B/Y/X의 논리적 의존성은 읽기 주소 관계로만 표현한다. Feedback이나 쓰기 traffic,
  원본 선형방정식 풀이의 기능·성능을 대표하지 않는다.

## 워크로드군·후보와 검증

F는 기존 coarse-fine/lane-scan/block-phase와 일부 stage/scan primitive를 공유하지만
거리 배증 쌍과 stage별 twiddle을 결합하는 전체 task는 다르다. F의 scan phase만으로
개발 cyclic task를 복제한 것으로 분류하지 않는다. 별도 cyclic task를 혼합하면 해당
워크로드군의 개발 노출/전이 병합 규칙을 적용한다.

T는 기존 overlap/hot-per-tile/matrix-reuse와 일부 재사용 특성을 공유하지만 삼각 범위·
행렬/벡터 결합·forward→backward 전체 주소 계약이 다르다. V2의 matrix-reuse task를
그대로 쓰지 않는다. 역할·width·stride·period·혼합비·저장 배치는 같은 워크로드군 안 변형이다.
이 판단은 통계적 독립성 증명이 아니며 완전한 base-task 재사용이 발견되면 병합한다.

`tools.rtems_periodic_pool --version 3`은 기존 세 워크로드군과 F/T의 같은 5개 coverage cell을
열거한다. 총 300개 요청 중 정확히 같은 실행 입력을 첫 등장 하나만 남기고 나머지는
`duplicate_candidates`에 원본 config·target U·`duplicate_of`·이유를 보존한다.
V1/V2 archive와 기본 version1 동작은 유지한다. V2 후보도 기존 archive와 동치 검사한다.
후보 width는 8이며 source-informed catalog는 5개 워크로드군, split은 여전히 초안이다.
LLC의 높은 부하 부재와 역할/core/period 상관은 이번 워크로드군 확장으로 해결되지 않는다.

작은 literal reference·완전 footprint·load/loop 예산과 G/C/P ELF stream을 검사한다.
큰 입력의 build/analysis/runtime 비용, 실측 U, 적격성, 충분성·최종 split 동결은 별도 gate다.
