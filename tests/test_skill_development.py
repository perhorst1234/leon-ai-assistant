from contextlib import closing
import json
import uuid

import pytest

from leon_control_plane.skill_development import develop,reconcile
from leon_control_plane.skill_discovery import discover
from leon_control_plane.code_worker import run_once,artifacts
from test_control_plane import make_store


def skill(store,goal='Maak een Python functie die het totale GB geheugen uit aantal sticks en GB per stick berekent.'):
    return store.create_task(title='Vaardigheid: geheugen berekenen',goal='Bouwprompt: '+goal+'\nAanleiding uit gesprek: Ik wil zo een functie.\nZoek eerst bestaande gratis MCP/plugins.',owner='Leon Zelfleren',risk_level='low')


def searched(store):
    return discover(store,query_model=lambda _:['memory-calculator'],catalog=lambda _:[],notify=False)


def build(workspace,brief):
    workspace.mkdir(parents=True)
    (workspace/'tool.py').write_text('def ram_total(sticks: int, gb_per_stick: int):\n return sticks * gb_per_stick\n')
    (workspace/'test_tool.py').write_text('from tool import ram_total\ndef test_ram():\n assert ram_total(4,32) == 128\n')
    return artifacts(workspace)


@pytest.fixture(autouse=True)
def private_home(tmp_path,monkeypatch):monkeypatch.setenv('HOME',str(tmp_path))


def test_learned_tool_queues_real_build_and_finishes_only_after_registered_tests(tmp_path,monkeypatch):
    store=make_store(tmp_path);parent=skill(store);searched(store)
    assert develop(store,model=lambda *a:{'kind':'local_function','reason':'Concreet offline rekenen.'},notify=False)['prepared']==1
    with closing(store.connect()) as c:
        row=c.execute('SELECT * FROM skill_developments').fetchone();job=c.execute('SELECT * FROM code_builds').fetchone()
    assert store.get_task(parent)['status']=='active'
    assert store.get_task(job['parent_id'])['parent_task_id']==parent
    assert 'MCP/plugins' not in job['brief']
    assert develop(store,model=lambda *a:pytest.fail('decision repeated'),notify=False)['prepared']==0
    monkeypatch.setattr('leon_control_plane.code_worker.test_artifacts',lambda p:{'tests_executed':True,'tests_passed':True,'test_exit_code':0,'test_image':'sha256:'+'a'*64})
    run_once(store,builder=build,notify=False);reconcile(store,notify=False)
    assert store.get_task(parent)['status']=='done'
    with closing(store.connect()) as c:assert c.execute('SELECT status FROM skill_developments').fetchone()[0]=='done'


def test_failed_tests_keep_learned_parent_open(tmp_path,monkeypatch):
    store=make_store(tmp_path);parent=skill(store);searched(store)
    develop(store,model=lambda *a:{'kind':'local_function','reason':'Offline.'},notify=False)
    monkeypatch.setattr('leon_control_plane.code_worker.test_artifacts',lambda p:{'tests_executed':True,'tests_passed':False,'test_reason':'test_failed'})
    run_once(store,builder=build,notify=False);reconcile(store,notify=False)
    assert store.get_task(parent)['status']=='blocked'


def test_school_missing_auth_is_visible_and_never_fake_completed(tmp_path):
    store=make_store(tmp_path);parent=skill(store,'Koppel mijn Magister-agenda.');searched(store)
    develop(store,model=lambda *a:pytest.fail('unnecessary inference'),school_status={'state':'mfa_needed'},notify=False)
    assert store.get_task(parent)['status']=='blocked'
    assert '2FA' in store.get_task(parent)['blocked_reason']
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==0


def test_external_action_never_becomes_local_function_even_if_model_would_say_so(tmp_path):
    store=make_store(tmp_path);parent=skill(store,'Maak een functie die mijn tickets koopt.');searched(store)
    develop(store,model=lambda *a:pytest.fail('external action classified locally'),notify=False)
    assert store.get_task(parent)['status']=='blocked'
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==0


def test_changed_goal_does_not_receive_old_completion(tmp_path,monkeypatch):
    store=make_store(tmp_path);parent=skill(store);searched(store)
    develop(store,model=lambda *a:{'kind':'local_function','reason':'Offline.'},notify=False)
    with closing(store.connect()) as c,c:c.execute('UPDATE tasks SET goal=? WHERE id=?',('Bouwprompt: Een andere vaardigheid.',parent))
    reconcile(store,notify=False)
    assert store.get_task(parent)['status']!='done'
    with closing(store.connect()) as c:assert c.execute('SELECT status FROM skill_developments').fetchone()[0]=='superseded'


def test_missing_current_discovery_does_not_queue_inference_or_build(tmp_path):
    store=make_store(tmp_path);skill(store)
    assert develop(store,model=lambda *a:pytest.fail('no source search'),notify=False)['prepared']==0


def test_invalid_model_waits_before_retry_and_has_no_effect(tmp_path):
    store=make_store(tmp_path);skill(store);searched(store)
    develop(store,model=lambda *a:{'kind':'install_paid','reason':'unknown'},clock=lambda:100,notify=False)
    assert develop(store,model=lambda *a:pytest.fail('too soon'),clock=lambda:101,notify=False)['prepared']==0
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==0


def test_actual_chat_source_reuses_existing_build_without_catalog_or_model(tmp_path):
    from leon_control_plane.chat_api import ChatService
    from leon_control_plane.code_worker import enqueue
    store=make_store(tmp_path);chat=ChatService(store);conv=chat.create_conversation({'request_id':str(uuid.uuid4())});rid=str(uuid.uuid4())
    owner='Maak een Python functie die het totale GB geheugen berekent.';mid='chatmsg-'+uuid.uuid4().hex
    with closing(store.connect()) as c,c:
        c.execute("INSERT INTO chat_messages(id,conversation_id,role,content,status,created_at,updated_at) VALUES(?,?,'user',?,'complete',100,100)",(mid,conv['id'],owner))
        c.execute("INSERT INTO chat_messages(id,conversation_id,request_id,request_content,role,content,status,created_at,updated_at) VALUES(?,?,?,?,'assistant','Bouw gestart','complete',101,101)",('reply-'+uuid.uuid4().hex,conv['id'],rid,owner))
    enqueue(store,rid,owner)
    parent=store.create_task(title='Vaardigheid: RAM berekenen',goal='Bouwprompt: '+owner,owner='Leon Zelfleren',risk_level='low',source_refs=['chat-message:'+mid])
    assert discover(store,query_model=lambda *a:pytest.fail('duplicate discovery'),catalog=lambda *a:pytest.fail('duplicate network'),notify=False)['completed_searches']==0
    develop(store,model=lambda *a:pytest.fail('duplicate classifier'),notify=False)
    with closing(store.connect()) as c:
        assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==1
        assert c.execute('SELECT build_id FROM skill_developments').fetchone()[0]==rid
    assert store.get_task(parent)['status']=='active'


def test_changed_goal_requires_current_discovery_not_stale_candidates(tmp_path):
    store=make_store(tmp_path);parent=skill(store);searched(store)
    with closing(store.connect()) as c,c:c.execute('UPDATE tasks SET goal=? WHERE id=?',('Bouwprompt: Maak een andere Python functie.',parent))
    assert develop(store,model=lambda *a:pytest.fail('stale discovery used'),notify=False)['prepared']==0


def test_brief_keeps_original_request_details_without_installation_suffix():
    from leon_control_plane.skill_development import brief
    result=brief('Bouwprompt: Geheugencalculatie\nAanleiding uit gesprek: Bereken GB uit aantal sticks en GB per stick.\nZoek eerst bestaande gratis MCP/plugins. Controleer werking en kosten.')
    assert 'aantal sticks en GB per stick' in result
    assert 'MCP/plugins' not in result


def test_legacy_catalog_result_migrates_only_exact_journal_key(tmp_path):
    store=make_store(tmp_path);parent=skill(store);searched(store)
    with closing(store.connect()) as c,c:
        row=c.execute('SELECT id,payload FROM skill_discoveries').fetchone()
        data=json.loads(row['payload']);data.pop('goal')
        c.execute('UPDATE skill_discoveries SET payload=? WHERE id=?',(json.dumps(data),row['id']))
    discover(store,query_model=lambda *a:pytest.fail('repeated search'),notify=False)
    assert develop(store,model=lambda *a:{'kind':'local_function','reason':'Offline rekenen.'},notify=False)['prepared']==1


@pytest.mark.parametrize('state,connected',[('signed_in_unverified',False),('connected',True)])
def test_existing_school_session_never_requests_unnecessary_login_or_finishes_other_sources(tmp_path,state,connected):
    store=make_store(tmp_path);parent=skill(store,'Koppel mijn Magister-huiswerk.');searched(store)
    develop(store,model=lambda *a:pytest.fail('unnecessary inference'),school_status={'state':state,'calendar_connected':connected},notify=False)
    task=store.get_task(parent)
    assert task['status']=='blocked' and '2FA' not in task['blocked_reason']
    assert 'schoolbron' in task['blocked_reason'].lower()
    with closing(store.connect()) as c:assert c.execute('SELECT COUNT(*) FROM code_builds').fetchone()[0]==0
