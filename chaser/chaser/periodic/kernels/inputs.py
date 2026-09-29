"""Bind prepared C and reference contracts to immutable kernel source files."""

from pathlib import Path
import shutil

from tools.rtems_smoke import file_hash

ROOT = Path(__file__).resolve().parents[3]


def input_paths():
    """List kernel and code-generation inputs, excluding caches."""
    paths = [ROOT / 'chaser/periodic/arrays.py']
    for directory in (Path(__file__).parent, ROOT / 'chaser/periodic/codegen',
                      ROOT / 'chaser/periodic/workload', ROOT / 'chaser/periodic/polybench',
                      ROOT / 'rtems/periodic/polybench'):
        paths += sorted(p for p in directory.rglob('*')
                        if p.is_file() and p.suffix in ('.py', '.c', '.h', '.in'))
    paths += [ROOT / 'rtems/periodic/polybench/upstream' / name for name in
              ('UPSTREAM_REVISION', 'LICENSE.txt', 'utilities/benchmark_list')]
    return paths


def snapshot_inputs(prepared):
    """Copy kernel inputs before rendering and return their relative hashes."""
    hashes = {}
    for path in input_paths():
        relative = str(path.relative_to(ROOT))
        destination = prepared / 'kernel-inputs' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        hashes[relative] = file_hash(destination)
    return hashes


def record_inputs(manifest, hashes):
    """Validate the captured inputs and register their artifacts as one unit."""
    if hashes:
        check_current_inputs({'kernel_input_hashes': hashes})
        manifest['kernel_input_hashes'] = hashes
        manifest['files'].update({'kernel-inputs/' + name: value for name, value in hashes.items()})


def check_current_inputs(manifest):
    """Reject analysis with changed Python contracts or C templates.

    Historical manifests without kernel_input_hashes retain their old contract.
    Executing or reloading saved results needs only the archived inputs.
    """
    if 'kernel_input_hashes' in manifest:
        current = {str(p.relative_to(ROOT)): file_hash(p) for p in input_paths()}
        if current != manifest['kernel_input_hashes']:
            raise ValueError('Kernel inputs changed; prepare a new snapshot before analysis')
