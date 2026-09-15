# CHASER RTEMS / GR740 baseline test

`rtems/baseline/` contains purpose-built C workloads and an RTEMS init task.
The same `workload.c` is compiled into three separate SPARC RTEMS 6 / GR740 executables and
into LLVM IR for LAT extraction. All RD analysis uses **yarda_cpp**.
Python is used only for pytest assertions, not for YARDA analysis.

## Cases

Each job increments eight volatile bytes over 65,537 sweeps. The nonzero final
byte value (1) lets the runtime check reject untouched, zero-initialized arrays.

| Case | Stride | 32 B lines | GR740 L1 mapping |
|---|---:|---:|---|
| packed | 1 B | 1 | One line |
| spread | 32 B | 8 | Eight different sets |
| conflict | 4096 B | 8 | One set, exceeding four ways |

All three have element RDH `{0: 524296, 7: 524288}`, 1,048,584 reuses,
8 cold references, and CA `131073 / 589825` (about 0.222224).
CA excludes cold references. Packed has line CA 1; spread and conflict retain
the same line Global RD. This demonstrates the Global-RD representation's
blindness to set mapping; it does not measure cache misses or prove a timing gap.

Each ELF runs one selected job, reports elapsed nanoseconds, and checks only
that job’s bytes. Unselected jobs and arrays are discarded by the linker. It is a workload integration test, not an SMP
scheduling comparison. `cache.yaml` supplies GR740 geometry with YARDA's supported
LRU/write-allocate policy; it is not an exact model of GR740 write policy.

## Verify

```sh
sh scripts/verify
```

Requires the existing RTEMS toolchain, LLVM 14, CMake, YARDA dependencies, and
pytest. Set `YARDA_DIR` to relocate the source checkout. The script builds a
fresh C++ analyzer inside `rtems/baseline/build/yarda`, builds the three RTEMS ELFs,
extracts LAT from C, analyzes element and cache-line RD, and runs assertions.
The LAT frontend plugin defaults to YARDA's `build-release/libLoopAnnotatedTrace.so`.

Verified with YARDA `6059896` containing `8b12a00` (unroll loop-limit fix):
**10 pytest tests passed**, including SPARC ELF validation and checks that each
ELF contains only its selected job and checker. The workload exceeds
the default cumulative limit, and succeeds with an explicit limit of 2,000,000.
The old YARDA `build-release/backend/yarda_cpp` was stale; rebuilding was necessary.

YARDA exports are saved to `exports/element.rdh.json` and `exports/line.rdh.json`.
Generated ELF, LAT, and build logs live under `rtems/baseline/build/`.
Working outputs can be regenerated.

## Separate builds and runs

```sh
make -C rtems/baseline all
# Or build one case:
make -C rtems/baseline build/packed.exe
```

Outputs: `build/packed.exe`, `build/spread.exe`, `build/conflict.exe`.
Each command below starts a separate simulator process:

```sh
cd rtems/baseline
script -q -e -c 'make run-packed' build/laysim-packed.log
script -q -e -c 'make run-spread' build/laysim-spread.log
script -q -e -c 'make run-conflict' build/laysim-conflict.log
```

Success requires one `RESULT` line for the selected case with a positive elapsed
time, followed by `CHASER PASS`.

## L1 CSRD and CLP (stage 2)

D1 is settled: `CA_CSRD` uses only the L1 CSRD histogram. `chaser/ca.py`
shares the CAAS formula between Global RD and L1 CSRD, excludes cold accesses,
and returns `None` if there is no reuse. LLC is not folded into this scalar.

```sh
make -C rtems/baseline hierarchy
python3 -m tools.export_locality
```

The hierarchy target selects each job and its object from the generated LAT v2,
then runs **yarda_cpp** with the corresponding executed SPARC ELF and cache YAML.
Python selects JSON records and computes the final scalar; it does not compute RD.
Each input is one task with independent cold caches. Linked ELF addresses are
used with core 0 geometry; this is not a reconstruction of RTEMS scheduling,
migration, interrupt accesses, or physical cache state from the measured run.

Outputs: `exports/packed.csrd.json`, `spread.csrd.json`, `conflict.csrd.json`.
`exports/locality.json` summarizes all three CA variants and CLP, and includes
hashes of the source exports. CLP order is L1 hit, LLC first hit, all-cache miss.

| Case | Element CA | Line Global CA | L1 CSRD CA | L1 CSRD histogram |
|---|---:|---:|---:|---|
| packed | 0.22222354 | 1 | 1 | `{0: 1048591}` |
| spread | 0.22222354 | 0.22222354 | 1 | `{0: 1048584}` |
| conflict | 0.22222354 | 0.22222354 | 0.22222354 | `{0: 524296, 7: 524288}` |

Conflict has 524,296 L1 hits, 524,288 LLC first hits and 8 all-cache misses.
Spread has only 8 cold L1 misses; packed has 1. These are **model counters**,
not measured GR740 counters. The line Global RD control isolates the set effect
between spread and conflict; element-to-line comparison also includes grouping.

`sh scripts/verify`: 10 tests pass, including expected histograms, CA,
CLP conservation, complete resolution, and input hashes. A direct repeated
analysis produced byte-identical CSRD exports.
