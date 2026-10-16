"""Analyze fixed job wrappers against every final executable and check streams."""

import json
from contextlib import ExitStack
from pathlib import Path
import re
import subprocess
import time

from chaser.locality.ca import ca_csrd, ca_from_histogram
from chaser.locality.cls import cls, DEFAULT_ALPHAS
from chaser.locality.instructions import job_ir_counts
from chaser.periodic.event_storage import compress_events as archive_events
from chaser.periodic.event_compression import EventCompressionQueue
from chaser.periodic.build import YARDA, check_layout, read_symbols
from chaser.periodic.kernels import reference_events, segment_tasks, task_from_plan
from chaser.periodic.workload import ArraySpec
from chaser.periodic.kernels.inputs import check_current_inputs
from chaser.periodic.measurement import ARCHITECTURES
from chaser.locality.artifacts import read_analysis
from tools.rtems_smoke import check_inputs, file_hash, write_json


def check_stream(task, events: list[dict], address: dict, *,
                 arrays: list[dict]) -> None:
    """Require the full job's object, address, size and operation order (task: a plan task,
    or a normalized TaskSpec such as one segment of a suspending job)."""
    objects = [a if isinstance(a, ArraySpec) else ArraySpec.from_dict(a) for a in arrays]
    registry = {a.array_id: a for a in objects}
    task = task_from_plan(task)
    if len(events) != task.metrics.source_accesses:
        raise ValueError('Wrapper access count differs from the emitted workload')
    for event, expected in zip(events, reference_events(task, registry), strict=True):
        symbol = registry[expected.array_id].symbol
        if (event['object_id'] != 'global::' + symbol
                or event['linked_address'] != address[symbol] + expected.offset_bytes
                or event['access_size'] != expected.access_size_bytes
                or event['operation'] != expected.operation):
            raise ValueError('Wrapper access order/address/kind differs from workload')


def analyze(prepared: Path, *, timeout: float = 120, compress_events: bool = False,
            compression_queue: EventCompressionQueue | None = None) -> dict:
    """Preserve compiler/APE/ELF provenance and reject incomplete helper expansion.

    Selection keeps the emitted root and its emitted inline helper unchanged;
    loop bodies/bounds are never edited. Stream addresses and count/order are
    checked against the literal generated workload, not a cold-count product.
    A shared compression queue reserves capacity before export and is drained for
    this snapshot before publishing its manifest. The caller owns queue shutdown.
    """
    plan = json.loads((prepared / 'p/plan.json').read_text())
    if plan.get('input_schema_version') == 3:
        if compress_events or compression_queue is not None:
            raise ValueError('Original PolyBench analysis does not export event streams')
        from chaser.periodic.polybench.analysis import analyze_prepared
        return analyze_prepared(prepared, timeout=timeout)
    if compression_queue is not None and not compress_events:
        raise ValueError('A compression queue requires compress_events=True')
    with ExitStack() as reservations:
        return _analyze(prepared, timeout, compress_events, compression_queue, reservations)


def _merge(histograms: list[dict]) -> dict:
    out = {}
    for histogram in histograms:
        for distance, count in histogram.items():
            out[distance] = out.get(distance, 0) + count
    return out


def _case(results: dict, checked, accesses: int, caches: dict) -> dict:
    return dict(ca_caas_element=ca_from_histogram(results['element']['program']['histogram']),
                ca_global_line=ca_from_histogram(results['line']['program']['histogram']),
                ca_csrd_l1=ca_csrd(checked.task), modeled_accesses=accesses,
                clp=list(checked.counts.ratios),
                cls={str(a): cls(checked.task, caches, a) for a in DEFAULT_ALPHAS})


def _combined_case(parts: list[tuple[dict, object, int]], caches: dict) -> dict:
    """One suspending job's case from its segments, each analyzed from a cold cache: histograms
    and first-hit counts are summed, so CLP, CLS and CA describe the two analyses together."""
    total = sum(accesses for _, _, accesses in parts)
    counts = [sum(getattr(checked.counts, k) for _, checked, _ in parts) for k in ('l1', 'llc', 'miss')]
    ratios = [c / total for c in counts]
    profile = dict(modeled_accesses=total, l1_first_hit_ratio=ratios[0], llc_first_hit_ratio=ratios[1],
                   all_cache_miss_ratio=ratios[2])
    return dict(ca_caas_element=ca_from_histogram(_merge([r['element']['program']['histogram'] for r, _, _ in parts])),
                ca_global_line=ca_from_histogram(_merge([r['line']['program']['histogram'] for r, _, _ in parts])),
                ca_csrd_l1=ca_from_histogram(_merge([c.task['l1']['csrd_histogram'] for _, c, _ in parts])),
                modeled_accesses=total, clp=ratios,
                cls={str(a): cls(profile, caches, a) for a in DEFAULT_ALPHAS})


def _analyze(prepared, timeout, compress_events, compression_queue, reservations):
    prepared = prepared.resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    check_inputs(prepared, manifest)
    check_current_inputs(manifest)
    plan = json.loads((prepared / 'p/plan.json').read_text())
    if plan.get('input_schema_version') != 2:
        raise ValueError('Legacy prepared input is deprecated; prepare schema_version: 2 arrays')
    output = prepared / 'analysis'
    output.mkdir(exist_ok=False)
    source = prepared / 'source/workload.c'
    plugin, executable = YARDA / 'libMemoryAccessPatterns.so', YARDA / 'backend/yarda_cpp'
    commands = []

    def execute(argv: list[str], log: Path, cwd: Path = output):
        if compression_queue is not None and '--export-events' in argv:
            argv = compression_queue.export_command(argv)
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
    registry = {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}
    for task in plan['tasks']:
        task_id = task['task_id']
        # A suspending job is analyzed per segment (task_job_<id>, task_job_resume_<id>), then combined.
        segments = []
        for segment in segment_tasks(task_from_plan(task), registry):
            root, helper = 'task_job_' + segment.task_id, 'kernel_' + segment.task_id
            functions = [f for f in raw['functions']
                         if f['function'] in (root, helper)
                         or f['function'].startswith(helper + '_')]
            if not any(f['function'] == root for f in functions):
                raise ValueError('Expected the emitted job wrapper and inline kernel')
            ape = output / f'{segment.task_id}.ape.json'
            write_json(ape, {**raw, 'functions': functions})
            segments.append((segment, root, ape))
        # The job's static IR instructions (every segment) give the placement's memory intensity (mpki);
        # None when a segment's loop trip counts are not constant.
        counts = [job_ir_counts({'functions': json.loads(a.read_text())['functions']}, r) for _, r, a in segments]
        instructions = None
        if None not in counts:
            if sum(m for _, m in counts) != sum(s.metrics.source_accesses for s, _, _ in segments):
                raise ValueError('IR loads and stores differ from the emitted workload accesses')
            instructions = sum(i for i, _ in counts)
        for name in ARCHITECTURES:
            elf = prepared / f'build/{name}.exe'
            layout = check_layout(read_symbols(elf), plan['arrays'])
            address = {r['symbol']: r['address'] for r in layout}
            parts = []
            for segment, root, ape in segments:
                reservation = (reservations.enter_context(compression_queue.reserve())
                               if compression_queue is not None else None)
                directory = output / name / segment.task_id
                directory.mkdir(parents=True)
                accesses = segment.metrics.source_accesses
                limit = segment.metrics.loop_iterations + 10
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
                check_stream(segment, events['events'], address, arrays=plan['arrays'])
                parts.append((results, checked, accesses))
                if compress_events:
                    event_path = directory / 'events.json'
                    key = str(event_path.relative_to(output)) + '.xz'
                    if reservation is not None:
                        event_storage[key] = reservation.submit(event_path)
                    else:
                        event_storage[key] = archive_events(event_path)
                        event_path.unlink()
                del events
            caches = dict(l1_capacity=checked.l1.size_bytes, llc_capacity=checked.llc.size_bytes)
            single = [_case(results, checked, accesses, caches) for results, checked, accesses in parts]
            case = single[0] if len(parts) == 1 else dict(
                _combined_case(parts, caches), segments={s.task_id: c for (s, _, _), c in zip(segments, single)})
            case['ir_instructions'] = instructions
            stream_hash = '+'.join(c.stream_hash for _, c, _ in parts)
            if task_id in cases and (cases[task_id] != case
                    or provenance[task_id]['stream_hash'] != stream_hash):
                raise ValueError('G/C/P locality or linked access stream differs')
            cases[task_id] = case
            revision = re.search(r'git\.([0-9a-f]{40}(?:-dirty)?)', hierarchy['tool_version'])
            if revision is None:
                raise ValueError('Analyzer revision is missing')
            entry = provenance.setdefault(task_id, dict(source_hash=file_hash(source),
                ape_hash='+'.join(file_hash(a) for _, _, a in segments), stream_hash=stream_hash,
                analyzer_commit=revision.group(1), cache_model_id=hierarchy['model_id'],
                cache_config_hash=expected['cache_config_sha256'], model_hash=None,
                elf_hash=expected['elf_sha256'], elf_hashes={}))
            entry['elf_hashes'][name] = expected['elf_sha256']
    if compression_queue is not None:
        event_storage = {key: future.result() for key, future in event_storage.items()}
    check_inputs(prepared, manifest)
    if any(file_hash(Path(p)) != h for p, h in tools.items()):
        raise ValueError('Analyzer changed during analysis')
    report = dict(cases=cases, provenance=provenance, tools=tools,
                  manifest_hash=file_hash(prepared / 'manifest.json'),
                  scope='cold-task-local-job-not-periodic-interference',
                  commands_hash=file_hash(output / 'commands.json'))
    report.update(input_schema_version=2, kernel_contract_id=plan['kernel_contract_id'],
                  analysis_compiler='clang-14-O0',
                  workload_optimization=plan['workload_optimization'],
                  store_model='demand-residency-same-as-load; excludes-write-traffic-and-timing',
                  dataset_eligible=False)
    write_json(output / 'locality.json', report)
    write_json(output / 'manifest.json', dict(event_storage=event_storage,
        files={str(p.relative_to(output)): file_hash(p) for p in output.rglob('*') if p.is_file()}))
    return report
