"""Compile the original and adapted C drivers and compare their live-out dumps."""

from pathlib import Path
import shutil
import subprocess

from chaser.periodic.polybench.sources import SUPPORT, UPSTREAM, Benchmark, render
from tools.rtems_smoke import file_hash, write_json


def write_sources(benchmark: Benchmark, directory: Path) -> None:
    """Capture every C input required by native, LLVM and RTEMS compilation."""
    directory.mkdir(parents=True)
    (directory / 'workload.c').write_text(render(benchmark))
    for path in (benchmark.source, benchmark.source.with_suffix('.h'),
                 UPSTREAM / 'utilities/polybench.h', UPSTREAM / 'utilities/polybench.c',
                 SUPPORT / 'adapter.h'):
        shutil.copyfile(path, directory / path.name)


def verify_native(directory: Path, benchmark: Benchmark, *, timeout: float = 120) -> dict:
    """Require identical original/adapted output and repeatable reset behavior.

    Comparison uses the upstream print precision, with no uint32 conversion.
    Both binaries use clang-14 O0 and disable FP contraction. This check does not
    claim exact floating-point equivalence across host and SPARC architectures.
    """
    source = directory / 'source'
    commands = [
        ['clang-14', '-O0', '-ffp-contract=off', '-DMEDIUM_DATASET',
         '-DPOLYBENCH_USE_SCALAR_LB', '-DPOLYBENCH_DUMP_ARRAYS', '-I', str(source),
         str(source / (benchmark.name + '.c')), str(source / 'polybench.c'),
         '-lm', '-o', str(directory / 'original.exe')],
        ['clang-14', '-O0', '-ffp-contract=off', '-DCHASER_NATIVE', '-I', str(source),
         str(source / 'workload.c'), '-lm', '-no-pie', '-o', str(directory / 'native.exe')]]
    with (directory / 'native-build.log').open('w') as log:
        for command in commands:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)
    for name in ('original', 'native'):
        with (directory / f'{name}.dump').open('wb') as dump, (directory / f'{name}.stdout').open('wb') as out:
            subprocess.run([str(directory / (name + '.exe'))], stdout=out, stderr=dump,
                           check=True, timeout=timeout)
    if file_hash(directory / 'original.dump') != file_hash(directory / 'native.dump'):
        raise ValueError(f'{benchmark.name}: adapted live-out dump differs from upstream')
    checksum = int((directory / 'native.stdout').read_text())
    report = dict(status='passed', expected_checksum=checksum, comparison='upstream-formatted-live-outs',
                  dump_sha256=file_hash(directory / 'original.dump'), commands=commands)
    write_json(directory / 'native-validation.json', report)
    return report
