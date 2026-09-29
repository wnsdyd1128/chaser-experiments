import json
from pathlib import Path
import pytest

@pytest.fixture
def config():
    return json.loads((Path(__file__).parent / 'fixtures/gemm-flat.json').read_text())['configuration']


@pytest.fixture
def shaped_config(config):
    for array, shape in zip(config['arrays'], ([2, 3], [3, 2], [2, 2])):
        array.pop('length')
        array['shape'] = shape
    for key in ('m', 'n', 'k', 'lda', 'ldb', 'ldc'):
        config['tasks'][0].pop(key)
    return config
