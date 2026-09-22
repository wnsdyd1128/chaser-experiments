import importlib
import json
import sys
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0,str(SCRIPTS))


def test_materialized_inputs_match_frozen_identities_and_preserve_parent(tmp_path):
    module = importlib.import_module('supplement_inputs')
    output=tmp_path/'inputs'
    report=module.materialize(output)
    assert module.verify_inputs(output)==report
    assert report['projected_split_counts']=={'train':126,'validation':45,'test':40}
    assert len(report['workloads'])==4
    for member in report['workloads']:
        assert member['split_group']=='validation'
        assert len(json.loads((output/'configs'/f"{member['workload_id']}.json").read_text())['tasks'])==10


def test_materialize_refuses_existing_output(tmp_path):
    module = importlib.import_module('supplement_inputs')
    with pytest.raises(FileExistsError):
        module.materialize(tmp_path)


def test_verifier_rejects_config_tamper_even_with_rehashed_file_list(tmp_path):
    module = importlib.import_module('supplement_inputs')
    output=tmp_path/'inputs'; module.materialize(output)
    path=next((output/'configs').glob('*.json'))
    data=json.loads(path.read_text());data['tasks'][0]['sweeps']+=1
    path.write_text(json.dumps(data))
    manifest=json.loads((output/'manifest.json').read_text())
    manifest['files'][str(path.relative_to(output))]=module.file_hash(path)
    (output/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='configuration'):
        module.verify_inputs(output)


def test_preparation_failure_blocks_all_u_runs(monkeypatch,tmp_path):
    module=importlib.import_module('collect_supplement')
    inputs=tmp_path/'inputs';module.materialize(inputs)
    monkeypatch.setattr(module,'prepare_member',lambda *args: (_ for _ in ()).throw(ValueError('build failure')))
    monkeypatch.setattr(module,'run_batch',lambda *args: pytest.fail('U must not start'))
    output=tmp_path/'collection'
    assert module.collect(inputs,output)==1
    progress=json.loads((output/'progress.json').read_text())
    assert progress['phase']=='prepare_failed'
    assert len(progress['prepare'])==4
    assert not (output/'runs').exists()


def test_failed_u_batch_is_reparsed_without_retry(monkeypatch,tmp_path):
    module=importlib.import_module('collect_supplement')
    calls=[]
    rows=[{'execution_status':'failed' if i==0 else 'ok'} for i in range(10)]
    monkeypatch.setattr(module,'run',lambda *args,**kwargs: calls.append(kwargs))
    monkeypatch.setattr(module,'load_batch',lambda *args: rows)
    result=module.run_batch(tmp_path,'workload',3)
    assert result['status']=='failed'
    assert result['successful_runs']==9
    assert result['raw_revalidated'] is True
    assert calls==[dict(architecture=2,mode=4,runs=10,timeout=600)]


def test_collection_refuses_second_invocation(monkeypatch,tmp_path):
    module=importlib.import_module('collect_supplement')
    inputs=tmp_path/'inputs';module.materialize(inputs)
    output=tmp_path/'collection';output.mkdir()
    protocol=output/'protocol.json';protocol.write_text('preserved history')
    with pytest.raises(FileExistsError):
        module.collect(inputs,output)
    assert protocol.read_text()=='preserved history'
