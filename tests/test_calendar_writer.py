from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
import uuid
from unittest.mock import patch
import pytest
from leon_control_plane.calendar_writer import execute,normalize,reconcile,WRITE_SCOPE,CalendarError,remember
from leon_control_plane.chat_api import ChatService
from test_control_plane import make_store

VALUES={'GOOGLE_CALENDAR_WRITE_ENABLED':'true','GOOGLE_ACCESS_TOKEN':'opaque','GOOGLE_GRANTED_SCOPES':WRITE_SCOPE}
ARGS={'title':'Testafspraak','start':'2026-09-27T14:00:00+02:00','end':'2026-09-27T15:00:00+02:00'}
OWNER='Zet Testafspraak op 27 september van 14:00 tot 15:00 in mijn agenda.'

class Google:
    def __init__(self):self.events={};self.calls=[];self.fail_after_write=False;self.mismatch=False
    def __call__(self,values):return self
    def request(self,method,path,body=None,etag=None):
        self.calls.append((method,path,body,etag))
        event_id=path.split('?')[0].split('/')[-1]
        if method=='POST':
            self.events[body['id']]={**body,'organizer':{'self':True},'etag':'v1'}
            if self.fail_after_write:raise TimeoutError('unknown outcome')
            return 200,self.events[body['id']]
        if method=='PATCH':
            assert etag=='v1'
            self.events[event_id].update(body)
            return 200,self.events[event_id]
        if method=='DELETE':
            assert etag=='v1'
            self.events.pop(event_id,None)
            return 204,{}
        if event_id not in self.events:return 404,{}
        event=dict(self.events[event_id])
        if self.mismatch:event['summary']='Changed elsewhere'
        return 200,event


def test_actual_calendar_protocol_create_update_delete_verified_and_no_replay(tmp_path):
    store=make_store(tmp_path);g=Google();rid=str(uuid.uuid4())
    result=execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g)
    assert result['status']=='completed' and store.get_task(result['task_id'])['status']=='done'
    assert execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g)==result
    assert len([c for c in g.calls if c[0]=='POST'])==1
    event_id=result['event_id']
    updated=execute(store,VALUES,str(uuid.uuid4()),'update',{'event_id':event_id,'title':'Nieuwe titel'},owner_content='Wijzig de titel',writer_factory=g)
    assert updated['status']=='completed' and g.events[event_id]['summary']=='Nieuwe titel'
    deleted=execute(store,VALUES,str(uuid.uuid4()),'delete',{'event_id':event_id},owner_content='Verwijder de afspraak',writer_factory=g)
    assert deleted['status']=='completed' and event_id not in g.events
    assert all('sendUpdates=none' in c[1] for c in g.calls if c[0] in {'POST','PATCH','DELETE'})


def test_unknown_outcome_never_repeats_mutation_or_claims_completion(tmp_path):
    store=make_store(tmp_path);g=Google();g.fail_after_write=True;rid=str(uuid.uuid4())
    r=execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g)
    assert r['status']=='unknown' and store.get_task(r['task_id'])['status']=='blocked'
    assert execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g)['status']=='unknown'
    assert len(g.calls)==1 and len(g.events)==1
    with pytest.raises(CalendarError,match='rebound'):
        execute(store,VALUES,rid,'create',{**ARGS,'title':'Andere titel'},owner_content=OWNER,writer_factory=g)


def test_mismatched_readback_is_not_success(tmp_path):
    g=Google();g.mismatch=True
    assert execute(make_store(tmp_path),VALUES,str(uuid.uuid4()),'create',ARGS,owner_content=OWNER,writer_factory=g)['status']=='unknown'


def test_pending_scope_resumes_original_command_and_delivers_to_origin_once(tmp_path,monkeypatch):
    store=make_store(tmp_path);service=ChatService(store);rid=str(uuid.uuid4());g=Google()
    conversation=service.create_conversation({'request_id':str(uuid.uuid4())})
    with closing(store.connect()) as conn,conn:
        conn.execute("INSERT INTO chat_messages(id,conversation_id,request_id,role,content,status,created_at,updated_at,execution_kind) VALUES(?,?,?,'assistant','Wacht op Google','complete',1,1,'action')",('origin',conversation['id'],rid))
    waiting=execute(store,{},rid,'create',ARGS,owner_content=OWNER,writer_factory=g)
    assert waiting['status']=='waiting_for_google' and not g.calls
    # Edited task display text must not replace the immutable authorized command.
    with closing(store.connect()) as conn,conn:
        conn.execute("UPDATE tasks SET goal='Gewijzigde weergavetekst' WHERE id=?",(waiting['task_id'],))
    for k,v in VALUES.items():monkeypatch.setenv(k,v)
    original=execute
    with patch('leon_control_plane.calendar_writer.execute',side_effect=lambda *a,**kw:original(*a,**kw,writer_factory=g)):
        reconcile(store);reconcile(store)
    loaded=service.get_conversation(conversation['id'])
    assert len(loaded['messages'])==2 and 'toegevoegd' in loaded['messages'][-1]['content']
    assert store.get_task(waiting['task_id'])['status']=='done'
    assert len([c for c in g.calls if c[0]=='POST'])==1


def test_two_simultaneous_requests_share_one_calendar_mutation(tmp_path):
    store=make_store(tmp_path);g=Google();rid=str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g),range(2)))
    assert results[0]==results[1] and len(g.events)==1
    assert len([c for c in g.calls if c[0]=='POST'])==1


@pytest.mark.parametrize('bad',[
    {**ARGS,'start':'2026-09-27T14:00:00'},
    {**ARGS,'start':'2026-09-27T14:00:00+01:00'},
    {**ARGS,'end':ARGS['start']},
    {**ARGS,'attendees':['someone@example.test']},
])
def test_invalid_time_or_unsupported_fields_rejected_before_external_calls(bad):
    with pytest.raises(CalendarError):normalize('create',bad)


def test_all_day_supported_and_unknown_events_cannot_be_edited(tmp_path):
    assert normalize('create',{'title':'Vrij','start':'2026-09-27','end':'2026-09-28'})['start']=={'date':'2026-09-27'}
    with pytest.raises(CalendarError,match='not_known'):
        execute(make_store(tmp_path),VALUES,str(uuid.uuid4()),'delete',{'event_id':'invented'},owner_content='Verwijder afspraak')


def test_uncertain_write_is_recovered_only_by_readback_and_delivered(tmp_path,monkeypatch):
    store=make_store(tmp_path);g=Google();g.fail_after_write=True;rid=str(uuid.uuid4())
    unknown=execute(store,VALUES,rid,'create',ARGS,owner_content=OWNER,writer_factory=g)
    for k,v in VALUES.items():monkeypatch.setenv(k,v)
    with patch('leon_control_plane.calendar_writer.Writer',return_value=g):
        reconcile(store);reconcile(store)
    assert store.get_task(unknown['task_id'])['status']=='done'
    assert len([c for c in g.calls if c[0]=='POST'])==1
    assert len([c for c in g.calls if c[0]=='GET'])==1


def test_recovery_does_not_observe_an_active_locked_write(tmp_path,monkeypatch):
    import fcntl
    store=make_store(tmp_path);g=Google();g.fail_after_write=True
    execute(store,VALUES,str(uuid.uuid4()),'create',ARGS,owner_content=OWNER,writer_factory=g)
    for k,v in VALUES.items():monkeypatch.setenv(k,v)
    with open(str(store.db_path)+'.calendar.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with patch('leon_control_plane.calendar_writer.Writer',return_value=g):reconcile(store)
    assert len(g.calls)==1


def test_writer_uses_fixed_google_host_and_supported_http_statuses():
    from leon_control_plane.calendar_writer import Writer,BASE
    from leon_control_plane.google_readonly import HTTPResponse
    calls=[]
    def wire(method,host,path,headers,body,timeout,max_bytes):
        calls.append((method,host,path,body))
        assert headers['Authorization']=='Bearer opaque'
        return HTTPResponse(status=204,body=b'')
    writer=Writer(VALUES,transport=wire)
    assert writer.request('DELETE',BASE+'/leonabc?sendUpdates=none',etag='etag')==(204,{})
    assert calls[0][1]=='www.googleapis.com'


def test_worker_migrates_earlier_calendar_ledger_without_crashing(tmp_path):
    store=make_store(tmp_path)
    with closing(store.connect()) as conn,conn:
        conn.execute('CREATE TABLE calendar_operations(request_id TEXT PRIMARY KEY,fingerprint TEXT,action TEXT,event_id TEXT,payload_json TEXT,task_id TEXT,status TEXT,result_json TEXT,deliver INTEGER)')
    reconcile(store)
    with closing(store.connect()) as conn:
        assert {'last_check','check_count'}<={r[1] for r in conn.execute('PRAGMA table_info(calendar_operations)')}
