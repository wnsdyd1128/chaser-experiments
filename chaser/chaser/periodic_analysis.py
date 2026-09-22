"""Analyze fixed job wrappers against every final executable and check streams."""

import json
from pathlib import Path
import re
import subprocess
import time

from chaser.ca import ca_csrd, ca_from_histogram
from chaser.cls import cls, DEFAULT_ALPHAS
from chaser.event_storage import compress_events as archive_events
from chaser.periodic_build import YARDA, check_layout, read_symbols
from chaser.periodic_patterns import access_offsets, job_access_count, loop_iterations
from chaser.s1_artifacts import read_analysis
from tools.rtems_smoke import check_inputs, file_hash, write_json


def check_stream(task: dict, events: list[dict], address: int) -> None:
    """Require the full job's specified byte-load order at its linked address."""
    if len(events) != job_access_count(task):
        raise ValueError('Wrapper access count differs from the emitted workload')
    for event, offset in zip(events, access_offsets(task), strict=True):
        if (event['linked_address'] != address + offset
                or event['access_size'] != 1 or event['operation'] != 'load'
                or event['object_id'] != 'global::data_' + task['task_id']):
            raise ValueError('Wrapper access order/address/kind differs from workload')


def analyze(prepared: Path, *, timeout: float = 120, compress_events: bool = False) -> dict:
    """Preserve compiler/APE/ELF provenance and reject incomplete helper expansion.

    Selection keeps the emitted root and its emitted inline helper unchanged;
    loop bodies/bounds are never edited. Stream addresses and count/order are
    checked against the literal generated workload, not a cold-count product.
    """
    prepared = prepared.resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    plan = json.loads((prepared / 'p/plan.json').read_text())
    output = prepared / 'analysis'
    output.mkdir(exist_ok=False)
    source = prepared / 'source/workload.c'
    plugin, executable = YARDA / 'libMemoryAccessPatterns.so', YARDA / 'backend/yarda_cpp'
    commands = []

    def execute(argv: list[str], log: Path, cwd: Path = output):
        started = time.monotonic()
        row = dict(argv=argv, cwd=str(cwd))
        commands.append(row)
        try:
            with log.open('w') as stream:
                p = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=timeout)
            row['returncode'] = p.returncode
            p.check_returncode()
        finally:
            row['wall_seconds'] = time.monotonic() - started
            write_json(output / 'commands.json', commands)

    tools = {str(p): file_hash(p) for p in (plugin, executable)}
    execute(['clang-14', '-O0', '-Xclang', '-disable-O0-optnone', '-g', '-emit-llvm',
             '-S', str(source), '-o', str(output / 'workload.ll')], output / 'clang.log')
    execute(['opt-14', f'-load-pass-plugin={plugin}',
             '-passes=function(mem2reg),loop-simplify,loop-annotated-trace',
             'workload.ll', '-o', '/dev/null'], output / 'opt.log')
    raw = json.loads((output / 'workload_ape.json').read_text())
    cases, provenance, event_storage = {}, {}, {}
    for task in plan['tasks']:
        task_id, root = task['task_id'], 'task_job_' + task['task_id']
        functions = [f for f in raw['functions']
                     if f['function'] in (root, 'kernel_' + task_id)]
        if len(functions) != 2:
            raise ValueError('Expected the emitted job wrapper and inline kernel')
        ape = output / f'{task_id}.ape.json'
        write_json(ape, {**raw, 'functions': functions})
        accesses = job_access_count(task)
        limit = loop_iterations(task) + 10
        for name in ('g', 'c', 'p'):
            directory = output / name / task_id
            directory.mkdir(parents=True)
            elf = prepared / f'build/{name}.exe'
            layout = check_layout(read_symbols(elf), plan['tasks'])
            results = {}
            for mode, flags in (
                ('element', ['--mode', 'unroll', '--granularity', 'element']),
                ('line', ['--mode', 'unroll', '--granularity', 'cache-line',
                          '--cache', str(prepared / 'cache.yaml')]),
                ('hierarchy', ['--analysis', 'hierarchy-rd', '--cache', str(prepared / 'cache.yaml'),
                               '--elf', str(elf), '--max-source-accesses', str(accesses),
                               '--max-line-references', str(accesses), '--export-events',
                               str(directory / 'events.json'), '--event-limit', str(accesses)])):
                path = directory / (mode + '.json')
                execute([str(executable), str(ape), *flags, '--export', str(path),
                         '--max-single-loop-iterations', str(limit),
                         '--max-cumulative-loop-iterations', str(limit)], directory / (mode + '.log'))
                results[mode] = json.loads(path.read_text())
            hierarchy = results['hierarchy']
            expected = dict(map_sha256=file_hash(ape), elf_sha256=file_hash(elf),
                            cache_config_sha256=file_hash(prepared / 'cache.yaml'))
            events = json.loads((directory / 'events.json').read_text())
            checked = read_analysis(hierarchy, events, root, expected)
            address = next(r['address'] for r in layout if r['symbol'] == 'data_' + task_id)
            check_stream(task, events['events'], address)
            case = dict(ca_caas_element=ca_from_histogram(results['element']['program']['histogram']),
                        ca_global_line=ca_from_histogram(results['line']['program']['histogram']),
                        ca_csrd_l1=ca_csrd(checked.task), modeled_accesses=accesses,
                        clp=list(checked.counts.ratios),
                        cls={str(a): cls(checked.task, dict(l1_capacity=checked.l1.size_bytes,
                                                         llc_capacity=checked.llc.size_bytes), a)
                             for a in DEFAULT_ALPHAS})
            if task_id in cases and (cases[task_id] != case
                    or provenance[task_id]['stream_hash'] != checked.stream_hash):
                raise ValueError('G/C/P locality or linked access stream differs')
            cases[task_id] = case
            revision = re.search(r'git\.([0-9a-f]{40}(?:-dirty)?)', hierarchy['tool_version'])
            if revision is None:
                raise ValueError('Analyzer revision is missing')
            entry = provenance.setdefault(task_id, dict(source_hash=file_hash(source),
                ape_hash=file_hash(ape), stream_hash=checked.stream_hash,
                analyzer_commit=revision.group(1), cache_model_id=hierarchy['model_id'],
                cache_config_hash=expected['cache_config_sha256'], model_hash=None,
                elf_hash=expected['elf_sha256'], elf_hashes={}))
            entry['elf_hashes'][name] = expected['elf_sha256']
            if compress_events:
                event_path = directory / 'events.json'
                event_storage[str(event_path.relative_to(output)) + '.xz'] = archive_events(event_path)
                event_path.unlink()
    check_inputs(prepared, manifest)
    if any(file_hash(Path(p)) != h for p, h in tools.items()):
        raise ValueError('Analyzer changed during analysis')
    report = dict(cases=cases, provenance=provenance, tools=tools,
                  manifest_hash=file_hash(prepared / 'manifest.json'),
                  scope='cold-task-local-job-not-periodic-interference',
                  commands_hash=file_hash(output / 'commands.json'))
    write_json(output / 'locality.json', report)
    write_json(output / 'manifest.json', dict(event_storage=event_storage,
        files={str(p.relative_to(output)): file_hash(p) for p in output.rglob('*') if p.is_file()}))
    return report
