from contextlib import closing
from unittest.mock import patch
import json
import time
import uuid
import pytest
from leon_control_plane.chat_api import ChatService
from leon_control_plane.chat_actions import ActionRunner, validate_authority, calendar_time
from test_control_plane import make_store

@pytest.mark.parametrize('content,cents,expected', [('zoek ddr3 onder 50 euro',5000,'shopper.create'),('zoek ddr3 tot €49,99',4999,'shopper.create'),('zoek ddr3 onder 50 euro',50000,'clarify'),('zoek ddr3 128 gb',12800,'clarify')])
def test_budget_must_come_from_owner(content,cents,expected):
    assert validate_authority({'action':'shopper.create','args':{'query':'ddr3','max_total_cents':cents}},content)['action']==expected

def test_write_memory_requires_current_command():
    decision={'action':'memory.save','args':{'text':'hello'}}
    assert validate_authority(decision,'Wat staat in mijn geheugen?')['action']=='clarify'
    assert validate_authority(decision,'Onthoud dit')['action']=='memory.save'
    assert calendar_time({'date':'2026-09-26'})=='2026-09-26 (hele dag)'
    assert calendar_time({'date_time':'2026-09-26T10:30:00Z'})=='26-09 12:30'

def test_chat_action_is_durable_idempotent_and_read_does_not_repeat(tmp_path,monkeypatch):
    monkeypatch.setenv('LEON_LOCAL_MODEL_ENABLED','1')
    store=make_store(tmp_path);service=ChatService(store)
    conversation=service.create_conversation({'request_id':str(uuid.uuid4())})
    content='Hoe gaat het met mijn shopper opdracht?'
    with patch('leon_control_plane.chat_actions.shopper_service') as shopper, patch('leon_control_plane.chat_actions.route',return_value={'action':'shopper.status','args':{}}) as route, patch('leon_control_plane.chat_actions.apply',return_value='Geen leads; ik zoek verder.') as apply:
        shopper.return_value.state.return_value={'watches':[]}
        quote=service.preview({'conversation_id':conversation['id'],'content':content,'max_output_tokens':128,'max_cost_microusd':2000})
        payload={'request_id':str(uuid.uuid4()),'content':content,'max_output_tokens':128,'max_cost_microusd':2000,'approve_external_text':True,'provider':'ollama','preview_sha256':quote['prompt_sha256']}
        message,job=service.submit(conversation['id'],payload)
        assert job['kind']=='chat_action'
        for _ in range(100):
            loaded=service.get_conversation(conversation['id'])
            if loaded['messages'][-1]['status']=='complete':break
            time.sleep(.01)
        assert loaded['messages'][-1]['content']=='Geen leads; ik zoek verder.'
        service.submit(conversation['id'],payload);service.get_conversation(conversation['id'])
        assert apply.call_count==route.call_count==1
        with closing(store.connect()) as c:
            assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='work_jobs'").fetchone()[0]==0

def test_interrupted_action_is_unknown_without_replay(tmp_path):
    store=make_store(tmp_path);ChatService(store)
    message={'id':'missing-msg','request_id':str(uuid.uuid4())}
    with closing(store.connect()) as c,c:
        c.execute('INSERT INTO chat_actions VALUES(?,?,?,?,?,?)',(message['id'],message['request_id'],'applying',time.time()-400,json.dumps({'action':'shopper.create'}),None))
    with patch('leon_control_plane.chat_actions.threading.Thread') as thread:
        ActionRunner(store).start(message)
        thread.assert_not_called()
    with closing(store.connect()) as c:
        assert c.execute('SELECT status FROM chat_actions').fetchone()[0]=='unknown'


def test_work_projection_includes_real_status_and_read_only_unapproved_tasks(tmp_path):
    from leon_control_plane.work_api import work_request
    store=make_store(tmp_path)
    task=store.create_task(title='Concert zoeken',goal='Vind een ticket',status='new',approval_required=True)
    data=work_request(store,method='GET',path='/api/work/status')
    item=next(t for t in data['tasks'] if t['id']==task)
    assert item['status']=='new' and item['goal']=='Vind een ticket'
    eligible=work_request(store,method='GET',path='/api/work/tasks')['tasks']
    assert not any(t['id']==task for t in eligible)
    with pytest.raises(ValueError):work_request(store,method='POST',path='/api/work/status',body={})
