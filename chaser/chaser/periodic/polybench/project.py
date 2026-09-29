"""Prepare source-suite inputs and verify linked global storage."""

from pathlib import Path
import re

from chaser.periodic.polybench.native import write_sources, verify_native
from chaser.periodic.polybench.sources import benchmark_named


def prepare_sources(output: Path, plans: list[dict]) -> None:
    """Compute the native reference before freezing the three RTEMS plans."""
    from chaser.periodic.measurement import digest
    benchmark = benchmark_named(plans[0]['polybench']['benchmark'])
    write_sources(benchmark, output / 'source')
    result = verify_native(output, benchmark)
    checksum = result['expected_checksum']
    source = output / 'source/workload.c'
    source.write_text(f'#define CHASER_EXPECTED {checksum}u\n' + source.read_text())
    for plan in plans:
        plan['tasks'][0]['expected_checksum'] = checksum
        del plan['plan_hash']
        plan['plan_hash'] = digest(plan)


def storage_layout(elf: Path, source: Path) -> list[dict]:
    """Check every hoisted object's alignment, extent and reserved RAM range."""
    from chaser.periodic.build import read_symbols
    symbols = read_symbols(elf)
    names = re.findall(r'PB_STORAGE\((\w+)\)', source.read_text())
    names = ['pb_y1' if name == 'y1' else name for name in names]
    result = []
    end = 0x01000000
    for name in sorted(names, key=lambda n: symbols[n][0]):
        address, size = symbols[name]
        if address < end or address % 64 or size <= 0 or address + size > 0x02000000:
            raise ValueError(f'PolyBench storage layout mismatch: {name}')
        result.append(dict(symbol=name, address=address, size=size, alignment=64))
        end = address + size
    return result
