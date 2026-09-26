"""Owner-requested personal Calendar writes, with durable identity and readback."""
from contextlib import closing
from datetime import datetime, date
import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from zoneinfo import ZoneInfo

from leon_control_plane.google_api import _provider_and_credentials
from leon_control_plane.google_readonly import GoogleReadonlyClient, GoogleReadonlyConfig, _https_transport
from leon_control_plane.secret_scanner import assert_no_secrets

WRITE_SCOPE = 'https://www.googleapis.com/auth/calendar.events.owned'
GOOGLE_KEYS = {'GOOGLE_READONLY_ENABLED','GOOGLE_CALENDAR_WRITE_ENABLED','GOOGLE_ACCESS_TOKEN',
    'GOOGLE_REFRESH_TOKEN','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_GRANTED_SCOPES','GOOGLE_CREDENTIALS_FILE'}
BASE = '/calendar/v3/calendars/primary/events'


class CalendarError(ValueError):
    pass


def initialize(store):
    with closing(store.connect()) as conn,conn:
        conn.executescript('''CREATE TABLE IF NOT EXISTS calendar_seen(
            id TEXT PRIMARY KEY, summary TEXT NOT NULL, start_json TEXT NOT NULL, end_json TEXT NOT NULL, seen_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS calendar_operations(request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            action TEXT NOT NULL, event_id TEXT NOT NULL, payload_json TEXT NOT NULL, task_id TEXT NOT NULL,
            status TEXT NOT NULL, result_json TEXT, deliver INTEGER NOT NULL DEFAULT 0,
            last_check REAL NOT NULL DEFAULT 0, check_count INTEGER NOT NULL DEFAULT 0);''')
        columns={row[1] for row in conn.execute('PRAGMA table_info(calendar_operations)')}
        for name,definition in [('last_check','REAL NOT NULL DEFAULT 0'),('check_count','INTEGER NOT NULL DEFAULT 0')]:
            if name not in columns:conn.execute(f'ALTER TABLE calendar_operations ADD COLUMN {name} {definition}')


def remember(store, items):
    initialize(store)
    with closing(store.connect()) as conn,conn:
        for item in items[:50]:
            conn.execute('INSERT OR REPLACE INTO calendar_seen VALUES(?,?,?,?,?)',
                (item['id'],item.get('summary','')[:300],json.dumps(item.get('start',{})),json.dumps(item.get('end',{})),time.time()))


def context(store,query=''):
    with closing(store.connect()) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='calendar_seen'").fetchone():
            return []
        rows = conn.execute('SELECT * FROM calendar_seen WHERE seen_at>? ORDER BY seen_at DESC LIMIT 100',(time.time()-86400,)).fetchall()
    terms=set(re.findall(r'\w{3,}',query.casefold()))
    def rank(row):
        start=json.loads(row['start_json'])
        return (-len(terms & set(re.findall(r'\w{3,}',row['summary'].casefold()))),start.get('dateTime',start.get('date_time',start.get('date',''))))
    rows=sorted(rows,key=rank)[:8]
    return [{'id':r['id'],'title':r['summary'],'start':json.loads(r['start_json']),'end':json.loads(r['end_json'])} for r in rows]


def writable(values):
    _, credentials = _provider_and_credentials(values)
    return values.get('GOOGLE_CALENDAR_WRITE_ENABLED','').lower() in {'1','true','yes'} and bool(credentials and WRITE_SCOPE in credentials.granted_scopes)


def _time(value):
    if not isinstance(value,str):
        raise CalendarError('calendar_invalid_time')
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            return {'date':date.fromisoformat(value).isoformat()}
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        local=parsed.astimezone(ZoneInfo('Europe/Amsterdam'))
        # A wrong summer/winter offset or nonexistent wall time is ambiguous.
        if local.replace(tzinfo=None)!=parsed.replace(tzinfo=None) or local.utcoffset()!=parsed.utcoffset():
            raise ValueError()
        return {'dateTime':local.isoformat(),'timeZone':'Europe/Amsterdam'}
    except ValueError:
        raise CalendarError('calendar_invalid_time') from None


def normalize(action,args):
    if action not in {'create','update','delete'} or not isinstance(args,dict):
        raise CalendarError('calendar_invalid_action')
    allowed={'title','start','end'} | ({'event_id'} if action!='create' else set())
    if set(args)-allowed or (action=='create' and not {'title','start','end'}<=set(args)):
        raise CalendarError('calendar_missing_fields')
    payload={}
    if 'title' in args:
        if not isinstance(args['title'],str) or not 1<=len(args['title'])<=300:
            raise CalendarError('calendar_invalid_title')
        payload['summary']=args['title']
    if ('start' in args)!=('end' in args):
        raise CalendarError('calendar_start_and_end_required')
    if 'start' in args:
        start,end=_time(args['start']),_time(args['end'])
        key='date' if 'date' in start else 'dateTime'
        if key not in end or datetime.fromisoformat(start[key])>=datetime.fromisoformat(end[key]):
            raise CalendarError('calendar_invalid_duration')
        payload.update(start=start,end=end)
    if action=='update' and not payload:
        raise CalendarError('calendar_update_empty')
    if action=='delete' and set(args)!={'event_id'}:
        raise CalendarError('calendar_delete_requires_event_only')
    if action!='create' and (not isinstance(args.get('event_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',args['event_id'])):
        raise CalendarError('calendar_invalid_event_id')
    assert_no_secrets('Calendar input',args)
    return payload


class Writer:
    def __init__(self,values,transport=None):
        if not writable(values):
            raise CalendarError('calendar_write_scope_missing')
        provider,credentials=_provider_and_credentials(values)
        self.transport=transport or _https_transport
        client=GoogleReadonlyClient(config=GoogleReadonlyConfig(enabled=True),credential_provider=provider,transport=self.transport)
        self.token=credentials.access_token or client._refresh_access_token(credentials)
        if not self.token or len(self.token)>8192 or any(c.isspace() for c in self.token):
            raise CalendarError('calendar_credentials_invalid')

    def request(self,method,path,body=None,etag=None):
        headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','Content-Type':'application/json'}
        if etag:
            headers['If-Match']=etag
        response=self.transport(method,'www.googleapis.com',path,headers,json.dumps(body).encode() if body is not None else None,15,256*1024)
        if len(response.body)>256*1024:
            raise CalendarError('calendar_response_too_large')
        try:
            data=json.loads(response.body) if response.body else {}
        except (ValueError,UnicodeError):
            raise CalendarError('calendar_invalid_response') from None
        if not isinstance(data,dict):
            raise CalendarError('calendar_invalid_response')
        return response.status,data


def execute(store,values,request_id,action,args,*,owner_content,writer_factory=Writer):
    request_id=str(uuid.UUID(request_id))
    payload=normalize(action,args)
    assert_no_secrets('Calendar owner command',owner_content)
    fingerprint=hashlib.sha256(json.dumps([action,args,owner_content],sort_keys=True).encode()).hexdigest()
    initialize(store)
    # Same lock is used by backend chat and the persistent worker. No network
    # mutation can race a replay or another edit of the same calendar.
    with open(str(store.db_path)+'.calendar.lock','a') as lock:
        os.chmod(lock.name,0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        with closing(store.connect()) as conn:
            old=conn.execute('SELECT * FROM calendar_operations WHERE request_id=?',(request_id,)).fetchone()
        if old and old['fingerprint']!=fingerprint:
            raise CalendarError('calendar_request_rebound')
        if old and old['status'] in {'completed','failed'}:
            return json.loads(old['result_json'])
        if old and old['status']=='sending':
            return {'status':'unknown','task_id':old['task_id'],'text':'Deze agenda-actie is nog niet bevestigd. Ik stuur hem niet opnieuw.'}
        if not old:
            event_id='leon'+uuid.UUID(request_id).hex if action=='create' else args['event_id']
            if action!='create':
                with closing(store.connect()) as conn:
                    if not conn.execute('SELECT 1 FROM calendar_seen WHERE id=?',(event_id,)).fetchone():
                        raise CalendarError('calendar_event_not_known')
            task_id=store.create_task(title='Agenda: '+args.get('title',action),goal=owner_content,owner='Leon Planner',risk_level='low',source_refs=['calendar-request:'+request_id])
            for status in ('planned','active'):
                store.update_task_status(task_id,status,actor_type='system',actor_id='calendar-writer')
            with closing(store.connect()) as conn,conn:
                conn.execute("INSERT INTO calendar_operations(request_id,fingerprint,action,event_id,payload_json,task_id,status,deliver) VALUES(?,?,?,?,?,?,'ready',0)",(request_id,fingerprint,action,event_id,json.dumps({'args':args,'owner_command':owner_content}),task_id))
        else:
            task_id,event_id=old['task_id'],old['event_id']
        if not writable(values):
            result={'status':'waiting_for_google','task_id':task_id,'text':'Ik heb de agenda-opdracht bewaard in Werk. Google heeft nog geen schrijfrechten gegeven. Kies bij Je agenda: Afspraken beheren inschakelen. Daarna voer ik de opdracht automatisch uit.'}
            if store.get_task(task_id)['status']=='active':
                store.update_task_status(task_id,'blocked',blocked_reason='Google Calendar schrijfrecht ontbreekt.',actor_type='system',actor_id='calendar-writer')
            with closing(store.connect()) as conn,conn:
                conn.execute("UPDATE calendar_operations SET status='waiting_for_google',result_json=?,deliver=1 WHERE request_id=?",(json.dumps(result),request_id))
            return result
        if store.get_task(task_id)['status']=='blocked':
            store.update_task_status(task_id,'active',actor_type='system',actor_id='calendar-writer')
        with closing(store.connect()) as conn,conn:
            conn.execute("UPDATE calendar_operations SET status='sending' WHERE request_id=?",(request_id,))
        try:
            writer=writer_factory(values)
            target=BASE+'/'+event_id
            if action=='create':
                body={**payload,'id':event_id,'extendedProperties':{'private':{'leon_request':fingerprint}}}
                code,_=writer.request('POST',BASE+'?sendUpdates=none',body)
                if code not in {200,201,409}:
                    raise CalendarError('calendar_write_rejected')
            else:
                code,current=writer.request('GET',target)
                if code!=200 or current.get('attendees') or current.get('recurringEventId') or current.get('recurrence'):
                    raise CalendarError('calendar_event_not_personal')
                if not current.get('organizer',{}).get('self'):
                    raise CalendarError('calendar_event_not_owned')
                etag=current.get('etag')
                if not isinstance(etag,str) or not etag:
                    raise CalendarError('calendar_event_version_missing')
                code,_=writer.request('PATCH' if action=='update' else 'DELETE',target+'?sendUpdates=none',payload if action=='update' else None,etag)
                if code not in ({200} if action=='update' else {204,404,410}):
                    raise CalendarError('calendar_write_rejected')
            code,actual=writer.request('GET',target)
            if action=='delete':
                confirmed=code in {404,410} or actual.get('status')=='cancelled'
            else:
                confirmed=code==200 and actual.get('id')==event_id and actual.get('status')!='cancelled' and _matches(actual,payload)
                if action=='create':
                    confirmed=confirmed and actual.get('extendedProperties',{}).get('private',{}).get('leon_request')==fingerprint
            if not confirmed:
                raise CalendarError('calendar_readback_not_confirmed')
            text={'create':'Afspraak toegevoegd aan je agenda.','update':'Afspraak aangepast in je agenda.','delete':'Afspraak staat niet meer in je agenda.'}[action]
            result={'status':'completed','task_id':task_id,'event_id':event_id,'text':text}
            if action=='delete':
                with closing(store.connect()) as conn,conn:
                    conn.execute('DELETE FROM calendar_seen WHERE id=?',(event_id,))
            else:
                remember(store,[actual])
            store.update_task_status(task_id,'review',actor_type='system',actor_id='calendar-writer')
            store.update_task_status(task_id,'done',result=text,verification_note='Gewenste toestand teruggelezen via Google Calendar.',actor_type='system',actor_id='calendar-writer')
        except Exception:
            # A transport failure may follow a successful Google mutation.
            # Never infer failure, completion or permission to send again.
            result={'status':'unknown','task_id':task_id,'text':'De agenda-actie kon niet worden bevestigd. Kijk in je agenda; ik verstuur de actie niet opnieuw.'}
            if store.get_task(task_id)['status']=='active':
                store.update_task_status(task_id,'blocked',blocked_reason='Google-uitvoering niet bevestigd; geen automatische herhaling.',actor_type='system',actor_id='calendar-writer')
        with closing(store.connect()) as conn,conn:
            conn.execute('UPDATE calendar_operations SET status=?,result_json=? WHERE request_id=?',('completed' if result['status']=='completed' else 'sending',json.dumps(result),request_id))
        return result


def _matches(actual,payload):
    for key,value in payload.items():
        if key in {'start','end'}:
            observed=actual.get(key,{})
            if 'date' in value:
                if observed.get('date')!=value['date']:return False
            else:
                try:
                    if datetime.fromisoformat(observed['dateTime'].replace('Z','+00:00'))!=datetime.fromisoformat(value['dateTime']):return False
                except (ValueError,KeyError,TypeError):return False
        elif actual.get(key)!=value:
            return False
    return True


def reconcile(store):
    with closing(store.connect()) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='calendar_operations'").fetchone():return
        columns={r[1] for r in conn.execute('PRAGMA table_info(calendar_operations)')}
    if not {'last_check','check_count'}<=columns:
        initialize(store)
    with closing(store.connect()) as conn:
        row=conn.execute("SELECT * FROM calendar_operations WHERE status='waiting_for_google' OR (status='completed' AND deliver=1) OR (status='sending' AND last_check<? AND check_count<5) ORDER BY CASE status WHEN 'completed' THEN 0 WHEN 'waiting_for_google' THEN 1 ELSE 2 END LIMIT 1",(time.time()-60,)).fetchone()
    if not row:return
    values={key:os.environ.get(key,'') for key in GOOGLE_KEYS}
    if row['status']=='sending':
        if not writable(values):return
        result=_recover(store,values,row)
        if not result:return
    elif row['status']=='waiting_for_google':
        if not writable(values):return
        saved=json.loads(row['payload_json'])
        try:
            result=execute(store,values,row['request_id'],row['action'],saved['args'],owner_content=saved['owner_command'])
        except CalendarError:
            return
        if result['status']!='completed':return
    else:
        result=json.loads(row['result_json'])
    from leon_control_plane.owner_updates import publish
    publish(store,'calendar-result:'+row['request_id'],result['text'],request_id=row['request_id'])
    with closing(store.connect()) as conn,conn:
        conn.execute('UPDATE calendar_operations SET deliver=0 WHERE request_id=?',(row['request_id'],))


def _recover(store,values,row):
    with open(str(store.db_path)+'.calendar.lock','a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        # Inspect the exact resource after an interrupted write. Never resend.
        with closing(store.connect()) as conn,conn:
            changed=conn.execute("UPDATE calendar_operations SET last_check=?,check_count=check_count+1 WHERE request_id=? AND last_check=? AND status='sending'",(time.time(),row['request_id'],row['last_check'])).rowcount
        if not changed:return
        try:
            code,actual=Writer(values).request('GET',BASE+'/'+row['event_id'])
            saved=json.loads(row['payload_json'])
            expected=normalize(row['action'],saved['args'])
            confirmed=(code in {404,410} or actual.get('status')=='cancelled') if row['action']=='delete' else code==200 and actual.get('id')==row['event_id'] and actual.get('status')!='cancelled' and _matches(actual,expected)
            if row['action']=='create':
                confirmed=confirmed and actual.get('extendedProperties',{}).get('private',{}).get('leon_request')==row['fingerprint']
            if not confirmed:return
            text='De agenda-actie is alsnog bevestigd door teruglezen: '+{'create':'afspraak toegevoegd.','update':'afspraak aangepast.','delete':'afspraak staat niet meer in je agenda.'}[row['action']]
            task=store.get_task(row['task_id'])
            if task['status']=='blocked':store.update_task_status(task['id'],'active')
            if store.get_task(task['id'])['status']=='active':store.update_task_status(task['id'],'review')
            if store.get_task(task['id'])['status']=='review':store.update_task_status(task['id'],'done',result=text,verification_note='Gewenste Google-toestand teruggelezen na onzekere uitvoering.')
            result={'status':'completed','task_id':task['id'],'event_id':row['event_id'],'text':text}
            if row['action']!='delete':remember(store,[actual])
            else:
                with closing(store.connect()) as conn,conn:
                    conn.execute('DELETE FROM calendar_seen WHERE id=?',(row['event_id'],))
            with closing(store.connect()) as conn,conn:
                conn.execute("UPDATE calendar_operations SET status='completed',result_json=?,deliver=1 WHERE request_id=?",(json.dumps(result),row['request_id']))
        except Exception:return None
        return result
