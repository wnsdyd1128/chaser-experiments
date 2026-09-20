# S1 cold-entry Cachegrind

Stock Valgrind 3.18.1에 [s1-cold-entry.patch](s1-cold-entry.patch)를 적용한다.
기존 설치는 변경하지 않고 별도 prefix에 빌드한다. 옵션은
`--s1-cold-entry=0x<ELF의 chaser_s1 주소>`다. non-PIE x86-64 ELF에 사용한다.

해당 guest PC가 **실행될 때마다**, 앞선 buffered event를 먼저 처리한 뒤
현재 명령의 instruction/data cache 접근 전에 I1·D1·LL의 tag 배열을 0으로 초기화한다.
이는 원본 `cachesim_initcache`의 초기 상태와 같다. Cachegrind의 cache lookup,
LRU replacement, miss count 계산 함수는 변경하지 않는다. 통계 counter도 지우지 않는다.
배열 초기화는 실행되고 메모리 값은 유지되며, cache residency만 초기화한다.
초기화 이후 stack·instruction 등 모든 traffic은 계속 cache 상태에 영향을 준다.

실행 로그의 `S1 cold reset` 주소·횟수와 `S1 cold reset total`을 검사한다.
S1 runner는 정확히 한 번의 reset만 허용하고, 누락·잘못된 주소·반복 reset을 실패 처리한다.
`--cache-sim=no`와 함께 사용하면 도구가 옵션 오류로 거부한다.

## 빌드 재현

공식 소스: https://sourceware.org/pub/valgrind/valgrind-3.18.1.tar.bz2
SHA-256: `00859aa13a772eddf7822225f4b46ee0d39afbe071d32778da4d99984081f7f5`.
Valgrind 원본은 GPL-2.0-or-later이며 저작권·라이선스는 소스의 COPYING을 따른다.

다음은 이번 실험에서 사용한 경로다. 재실행 시 새 build/prefix 경로를 사용한다.

```sh
curl -fL https://sourceware.org/pub/valgrind/valgrind-3.18.1.tar.bz2 -o /tmp/chaser-valgrind-3.18.1.tar.bz2
sha256sum /tmp/chaser-valgrind-3.18.1.tar.bz2
mkdir /tmp/chaser-cg-cold-build
tar -xjf /tmp/chaser-valgrind-3.18.1.tar.bz2 -C /tmp/chaser-cg-cold-build
cd /tmp/chaser-cg-cold-build/valgrind-3.18.1
patch -p1 < /workspace/experiments/chaser/tools/cachegrind/s1-cold-entry.patch
./configure --prefix=/tmp/chaser-cg-cold-install --enable-only64bit
make -j4
make install
```

설치 prefix에 `s1-build.json`으로 빌드 출처를 기록한다. 예를 들어 workspace에서:

```sh
python3 - <<'PY'
import json, subprocess
from pathlib import Path
from chaser.s1_execution import file_hash
source = Path('/tmp/chaser-cg-cold-build/valgrind-3.18.1')
prefix = Path('/tmp/chaser-cg-cold-install')
metadata = {
    'version': '3.18.1+s1-cold-entry',
    'source_url': 'https://sourceware.org/pub/valgrind/valgrind-3.18.1.tar.bz2',
    'archive_sha256': file_hash(Path('/tmp/chaser-valgrind-3.18.1.tar.bz2')),
    'patch_sha256': file_hash(Path('tools/cachegrind/s1-cold-entry.patch')),
    'patched_cg_main_sha256': file_hash(source / 'cachegrind/cg_main.c'),
    'unchanged_cg_sim_sha256': file_hash(source / 'cachegrind/cg_sim.c'),
    'compiler': subprocess.check_output(['gcc', '--version'], text=True),
    'configure': ['./configure', '--prefix=' + str(prefix), '--enable-only64bit'],
    'build': ['make', '-j4'], 'install': ['make', 'install'],
}
(prefix / 's1-build.json').write_text(json.dumps(metadata, indent=2) + '\n')
PY
```

Runner가 launcher뿐 아니라 실제 `libexec/valgrind/cachegrind-amd64-linux`와 preload,
빌드 기록도 hash하며, `VALGRIND_LIB`를 해당 설치로 고정한다.
빌드 기록은 출처 설명이고, runtime reset 로그 검사와 실제 counter 검증을 대체하지 않는다.

```sh
python3 -m tools.run_s1_cachegrind --input rtems/s1/build/host-trace-v2 \
  --output rtems/s1/build/cachegrind-cold-new --cold-prefix /tmp/chaser-cg-cold-install
CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install sh scripts/verify
```

`CHASER_COLD_PREFIX`는 live reset integration test에 사용한다. 지정하지 않으면 그 테스트는
명시적으로 skip되며, 저장된 25-case 원본 재집계 및 reset 로그 검사는 항상 실행된다.
