from contextlib import closing
import json
import uuid

import pytest

from leon_control_plane.code_worker import enqueue,run_once,artifacts
from leon_control_plane.chat_actions import route,may_be_action,apply
from test_control_plane import make_store

BRIEF='Maak een Python functie die een leerlingnummer uit een e-mailadres haalt.'


@pytest.fixture(autouse=True)
def private_test_home(tmp_path,monkeypatch):
    monkeypatch.setenv('HOME',str(tmp_path))
    monkeypatch.setattr('leon_control_plane.code_worker.test_artifacts',lambda p:{'tests_executed':False,'tests_passed':False,'test_reason':'fixture_no_execution'})


def files(workspace,brief):
    workspace.mkdir(parents=True)
    (workspace/'tool.py').write_text("def username(account):\n    return account.split('@',1)[0]\n")
    (workspace/'test_tool.py').write_text("from tool import username\ndef test_username():\n    assert username('student@example.edu') == 'student'\n")
    return artifacts(workspace)


def test_chat_routes_explicit_coding_without_model_and_queues_once(tmp_path):
    store=make_store(tmp_path);rid=str(uuid.uuid4())
    assert may_be_action(BRIEF) and route(BRIEF,[],{})=={'action':'code.build','args':{}}
    assert 'Werk' in apply(store,rid,route(BRIEF,[],{}),None,owner_content=BRIEF)
    first=enqueue(store,rid,BRIEF)
    assert enqueue(store,rid,BRIEF)==first
    with pytest.raises(ValueError):enqueue(store,rid,BRIEF+' Anders.')
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==1


def test_real_artifacts_finish_only_generation_and_keep_tool_open(tmp_path):
    store=make_store(tmp_path);rid=str(uuid.uuid4());parent=enqueue(store,rid,BRIEF)['task_id']
    assert run_once(store,builder=files,clock=lambda:100,notify=False)
    assert store.get_task(parent)['status']=='blocked'
    with closing(store.connect()) as c:
        row=c.execute('SELECT * FROM code_builds').fetchone()
    payload=json.loads(row['payload'])
    assert payload['tests_executed'] is False and payload['installed'] is False
    assert len(payload['files']['tool.py']['sha256'])==64
    assert store.get_task(row['child_id'])['status']=='done'
    assert not run_once(store,builder=lambda *a:pytest.fail('repeated coding'),clock=lambda:1000)


def test_delivery_failure_resumes_without_regenerating(tmp_path,monkeypatch):
    from leon_control_plane import owner_updates
    store=make_store(tmp_path);enqueue(store,str(uuid.uuid4()),BRIEF);original=owner_updates.publish
    monkeypatch.setattr(owner_updates,'publish',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('delivery')))
    with pytest.raises(RuntimeError):run_once(store,builder=files,clock=lambda:100)
    monkeypatch.setattr(owner_updates,'publish',original)
    assert run_once(store,builder=lambda *a:pytest.fail('regenerated'),clock=lambda:200)
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==1


def test_gpu_yield_is_delayed_and_resumable_without_blocking_parent(tmp_path):
    store=make_store(tmp_path);parent=enqueue(store,str(uuid.uuid4()),BRIEF)['task_id']
    assert not run_once(store,builder=lambda *a:None,clock=lambda:100,notify=False)
    assert not run_once(store,builder=lambda *a:pytest.fail('early retry'),clock=lambda:120,notify=False)
    assert store.get_task(parent)['status']=='active'
    assert run_once(store,builder=files,clock=lambda:161,notify=False)


def test_unknown_failed_build_is_not_automatically_replayed(tmp_path):
    store=make_store(tmp_path);enqueue(store,str(uuid.uuid4()),BRIEF)
    assert run_once(store,builder=lambda *a:(_ for _ in ()).throw(ValueError('private-input')),clock=lambda:100,notify=False)
    assert not run_once(store,builder=lambda *a:pytest.fail('replayed'),clock=lambda:100000,notify=False)
    with closing(store.connect()) as c:assert 'private-input' not in '\n'.join(c.iterdump())


def test_abandoned_build_becomes_visible_blocker_without_replay(tmp_path):
    store=make_store(tmp_path);parent=enqueue(store,str(uuid.uuid4()),BRIEF)['task_id']
    with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='building'")
    assert not run_once(store,builder=lambda *a:pytest.fail('unknown generation replayed'),notify=False)
    assert store.get_task(parent)['status']=='blocked'
    with closing(store.connect()) as c:assert c.execute('SELECT status FROM code_builds').fetchone()[0]=='failed'


def test_source_rejects_symlinks_extra_files_and_stub(tmp_path):
    workspace=tmp_path/'code';files(workspace,BRIEF)
    (workspace/'tool.py').unlink();(workspace/'tool.py').symlink_to(tmp_path/'outside')
    with pytest.raises(OSError):artifacts(workspace)
    (workspace/'tool.py').unlink();(workspace/'tool.py').write_text('# no implementation')
    with pytest.raises(ValueError):artifacts(workspace)
    (workspace/'outside.txt').write_text('unexpected')
    with pytest.raises(ValueError):artifacts(workspace)
