import hashlib
import uuid
from contextlib import closing

import pytest

from leon_control_plane.code_tools import register,catalog,invoke,schemas
from test_control_plane import make_store


def payload(source='def gb_to_mb(gb: int):\n return gb * 1024\n'):
    return {'tests_executed':True,'tests_passed':True,'test_exit_code':0,'test_image':'sha256:'+'a'*64,
        'files':{'tool.py':{'source':source,'sha256':hashlib.sha256(source.encode()).hexdigest()}}}


def test_only_tested_identical_sources_register_without_host_import(tmp_path):
    store=make_store(tmp_path);bid=str(uuid.uuid4());data=payload()
    assert register(store,bid,{**data,'tests_passed':False})==[]
    ids=register(store,bid,data)
    assert register(store,bid,data)==ids and len(catalog(store))==1
    bad=payload();bad['files']['tool.py']['source']='raise RuntimeError("must not execute on host")'
    with pytest.raises(ValueError,match='digest mismatch'):register(store,str(uuid.uuid4()),bad)
    assert schemas('import socket\ndef connect(): return 1')==[]
    assert schemas('async def run(): return 1')==[]


def test_invocation_is_typed_bound_and_deduplicated(tmp_path):
    store=make_store(tmp_path);tid=register(store,str(uuid.uuid4()),payload())[0];rid=str(uuid.uuid4());calls=[]
    def executor(row,args):calls.append((row['sha256'],args));return args['gb']*1024
    assert invoke(store,rid,tid,{'gb':64},executor=executor)==65536
    assert invoke(store,rid,tid,{'gb':64},executor=lambda *a:pytest.fail('replayed'))==65536
    assert len(calls)==1
    for args in ({'gb':'64'},{'gb':True},{},{'gb':64,'host':'elsewhere'}):
        with pytest.raises(ValueError):invoke(store,str(uuid.uuid4()),tid,args,executor=lambda *a:pytest.fail('wrong arguments'))
    with pytest.raises(ValueError,match='identity changed'):invoke(store,rid,tid,{'gb':128},executor=executor)


def test_unknown_outcome_not_replayed_and_source_mutation_is_rejected(tmp_path):
    store=make_store(tmp_path);tid=register(store,str(uuid.uuid4()),payload())[0];rid=str(uuid.uuid4())
    with pytest.raises(ValueError):invoke(store,rid,tid,{'gb':64},executor=lambda *a:(_ for _ in ()).throw(RuntimeError('private-runtime-error')))
    with pytest.raises(ValueError,match='no automatic retry'):invoke(store,rid,tid,{'gb':64},executor=lambda *a:pytest.fail('replay'))
    with closing(store.connect()) as c,c:
        assert 'private-runtime-error' not in '\n'.join(c.iterdump())
        c.execute('UPDATE generated_tools SET source=?',('def gb_to_mb(gb): return -1',))
    with pytest.raises(ValueError,match='source changed'):invoke(store,str(uuid.uuid4()),tid,{'gb':64})
    assert catalog(store)==[]


def test_defaults_and_metadata_do_not_execute_generated_source():
    data=schemas('raise RuntimeError("host execution forbidden")\ndef format_value(value: str, upper: bool=False):\n return value\n')
    assert data[0]['parameters']==[{'name':'value','type':'str','required':True},{'name':'upper','type':'bool','required':False}]


def test_limits_and_non_json_output_fail_closed(tmp_path):
    store=make_store(tmp_path);tid=register(store,str(uuid.uuid4()),payload())[0]
    for executor in (lambda *a:float('inf'),lambda *a:'a'*20000):
        with pytest.raises(ValueError,match='not confirmed'):invoke(store,str(uuid.uuid4()),tid,{'gb':1},executor=executor)


def test_async_result_delivery_resumes_without_second_execution(tmp_path,monkeypatch):
    from leon_control_plane import owner_updates
    from leon_control_plane.code_tools import enqueue_call,process_pending
    store=make_store(tmp_path);tid=register(store,str(uuid.uuid4()),payload())[0];rid=str(uuid.uuid4())
    monkeypatch.setattr('leon_control_plane.code_tools.subprocess.run',lambda *a,**k:None)
    task=enqueue_call(store,rid,tid,{'gb':64})
    assert enqueue_call(store,rid,tid,{'gb':64})==task
    original=owner_updates.publish
    monkeypatch.setattr(owner_updates,'publish',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('delivery')))
    with pytest.raises(RuntimeError):process_pending(store,executor=lambda *a:65536)
    monkeypatch.setattr(owner_updates,'publish',original)
    assert process_pending(store,executor=lambda *a:pytest.fail('replayed container'))==1
    assert store.get_task(task)['status']=='done'
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==1


def test_abandoned_tool_execution_is_visible_and_not_replayed(tmp_path,monkeypatch):
    from leon_control_plane.code_tools import enqueue_call,process_pending
    store=make_store(tmp_path);tid=register(store,str(uuid.uuid4()),payload())[0];rid=str(uuid.uuid4())
    monkeypatch.setattr('leon_control_plane.code_tools.subprocess.run',lambda *a,**k:None)
    task=enqueue_call(store,rid,tid,{'gb':64})
    with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='running'")
    assert process_pending(store,executor=lambda *a:pytest.fail('unknown execution replay'),notify=False)==1
    assert store.get_task(task)['status']=='blocked'
