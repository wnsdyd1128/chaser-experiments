import json
from pathlib import Path
import pytest

@pytest.fixture
def config():
    return json.loads((Path(__file__).resolve().parents[3] /
        'configs/periodic-multi-array/gemm-u32-smoke.json').read_text())
