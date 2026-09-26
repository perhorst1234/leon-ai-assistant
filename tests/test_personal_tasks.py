from contextlib import closing
import json
import uuid
import pytest
from leon_control_plane.personal_tasks import execute,control,reconcile
from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.work_queue import WorkQueue
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.local_model import LocalModelConfig
from leon_control_plane.chat_api import ChatService
from test_control_plane import make_store


def test_local_task_uses_real_queue_and_completes_without_external_model(tmp_path,monkeypatch):
    monkeypatch.setenv('LEON_LOCAL_MODEL_ENABLED','1')
    store=make_store(tmp_path);rid=str(uuid.uuid4());args={'title':'Schrijf een checklist','goal':'Maak een checklist','role':'planner'}
    queued=execute(store,rid,args)
    assert execute(store,rid,args)==queued
    queue=WorkQueue(store)
    called=[]
    def local(payload,config):
        called.append(payload)
        return {'model':payload['model'],'response':'1. Voorbereiden\n2. Controleren','done':True,'done_reason':'stop','prompt_eval_count':12,'eval_count':8}
    worker=LocalWorker(queue,model_executor=ModelExecutor(queue,local_config=LocalModelConfig.from_env(),local_transport=local,transport=lambda *a:pytest.fail('External provider must not be called')))
    assert worker.run_once()
    assert store.get_task(queued['task_id'])['status']=='done'
    assert store.get_task(queued['task_id'])['result']=='1. Voorbereiden\n2. Controleren'
    assert queue.get(queued['job_id'])['accounted_microusd']==0
    reconcile(queue);assert len(called)==1
    with pytest.raises(ValueError):execute(store,rid,{**args,'goal':'Andere opdracht'})


def test_pause_resume_cancel_only_personal_jobs(tmp_path,monkeypatch):
    monkeypatch.setenv('LEON_LOCAL_MODEL_ENABLED','1')
    store=make_store(tmp_path);q=execute(store,str(uuid.uuid4()),{'title':'Checklist','goal':'Schrijf een checklist'})
    assert control(store,q['task_id'],'pause')['status']=='paused'
    assert control(store,q['task_id'],'resume')['status']=='queued'
    assert control(store,q['task_id'],'cancel')['status']=='cancelled'
    ordinary=store.create_task(title='Andere taak',goal='Niet deze taak',risk_level='low')
    with pytest.raises(ValueError):control(store,ordinary,'cancel')


def test_result_delivered_to_chat_once_even_after_parent_already_completed(tmp_path,monkeypatch):
    monkeypatch.setenv('LEON_LOCAL_MODEL_ENABLED','1')
    store=make_store(tmp_path);service=ChatService(store);rid=str(uuid.uuid4())
    conversation=service.create_conversation({'request_id':str(uuid.uuid4())})
    with closing(store.connect()) as conn,conn:
        conn.execute("INSERT INTO chat_messages(id,conversation_id,request_id,role,content,status,created_at,updated_at,execution_kind) VALUES(?,?,?,'assistant','Gestart','complete',1,1,'action')",('origin',conversation['id'],rid))
    q=execute(store,rid,{'title':'Checklist','goal':'Schrijf een checklist'})
    queue=WorkQueue(store);claim=queue.claim()
    queue.checkpoint(claim,{'ok':True,'text':'Werkelijk resultaat','step':'model'})
    for status in ['review','done']:
        store.update_task_status(q['task_id'],status,**({'result':'Werkelijk resultaat','verification_note':'Alleen tekst geleverd'} if status=='done' else {}))
    reconcile(queue);reconcile(queue)
    messages=service.get_conversation(conversation['id'])['messages']
    assert [m['content'] for m in messages]==['Gestart','Werkelijk resultaat']


def test_research_summary_has_real_sources_in_task_and_delivered_chat(tmp_path, monkeypatch):
    monkeypatch.setenv('LEON_LOCAL_MODEL_ENABLED','1')
    store=make_store(tmp_path);ChatService(store)
    queued=execute(store,str(uuid.uuid4()),{'title':'Onderzoek','goal':'Vat bronnen samen','role':'researcher'},
        evidence='Echte bron: asyncio cancellation.',source_refs=['research-source:https://docs.python.org/3/library/asyncio.html'])
    queue=WorkQueue(store);claim=queue.claim()
    queue.checkpoint(claim,{'ok':True,'text':'Samenvatting https://invented.example/fake','step':'model'})
    reconcile(queue)
    task=store.get_task(queued['task_id'])
    assert task['status']=='done'
    assert 'https://docs.python.org/3/library/asyncio.html' in task['result']
    assert 'invented.example' not in task['result']
