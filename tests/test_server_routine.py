from contextlib import closing
import json
from unittest.mock import patch

from leon_control_plane.server_routine import SERVICES, inspect
from leon_control_plane.owner_updates import publish
from leon_control_plane.chat_api import ChatService
from test_control_plane import make_store


class Host:
    def __init__(self, failed=(), recoverable=True):
        self.states={name:'failed' if name in failed else 'active' for name in SERVICES}
        self.calls=[]
        self.recovers=recoverable
    def __call__(self,args):
        self.calls.append(args)
        if args[0]=='nvidia-smi':
            return '42'
        if args[2]=='is-active':
            return self.states[args[3]]
        if args[2]=='restart' and self.recovers:
            self.states[args[3]]='active'
        return ''


def test_healthy_inspection_tracks_real_completion_without_chat_noise(tmp_path):
    store=make_store(tmp_path);host=Host()
    with patch('leon_control_plane.owner_updates.publish') as notify:
        result=inspect(store,tmp_path,key='week-one',run=host)
        assert result['status']=='healthy'
        assert store.get_task(result['task_id'])['status']=='done'
        assert 'M40: 42' in store.get_task(result['task_id'])['result']
        assert inspect(store,tmp_path,key='week-one',run=host)==result
        inspect(store,tmp_path,key='week-two',run=host)
        notify.assert_not_called()
    assert not any(c[2]=='restart' for c in host.calls if c[0]=='systemctl')


def test_service_recovery_reprobes_and_unchanged_failure_stays_quiet(tmp_path):
    store=make_store(tmp_path);host=Host(['leon-web'],recoverable=False)
    with patch('leon_control_plane.owner_updates.publish') as notify:
        first=inspect(store,tmp_path,key='first',run=host,clock=lambda:10000)
        assert first['status']=='attention' and first['recovery_attempts']==['leon-web']
        assert notify.call_count==1
        second=inspect(store,tmp_path,key='second',run=host,clock=lambda:10001)
        assert second['recovery_attempts']==[]
        assert notify.call_count==1
        host.states['leon-web']='active'
        third=inspect(store,tmp_path,key='third',run=host,clock=lambda:10002)
        assert third['status']=='healthy' and notify.call_count==2
    assert [c for c in host.calls if c[0]=='systemctl' and c[2]=='restart']==[['systemctl','--user','restart','leon-web']]


def test_recovery_never_restarts_ollama_or_hot_worker(tmp_path):
    host=Host(['leon-ollama','leon-worker'])
    def hot(args):
        return '89' if args[0]=='nvidia-smi' else host(args)
    with patch('leon_control_plane.owner_updates.publish'):
        result=inspect(make_store(tmp_path),tmp_path,key='hot',run=hot)
    assert result['status']=='attention' and not result['recovery_attempts']
    assert 'gpu:temperature_at_or_above_89C' in result['issues']
    assert not any(c[2]=='restart' for c in host.calls)


def test_successful_recovery_is_evidenced_in_final_snapshot(tmp_path):
    with patch('leon_control_plane.owner_updates.publish'):
        result=inspect(make_store(tmp_path),tmp_path,key='recover',run=Host(['leon-web']))
    assert result['status']=='healthy' and result['services']['leon-web']=='active'
    assert result['recovery_attempts']==['leon-web']


def test_owner_updates_deliver_once_to_one_durable_conversation(tmp_path):
    store=make_store(tmp_path)
    assert publish(store,'incident-one','Er is een nieuwe servermelding.')
    assert not publish(store,'incident-one','Er is een nieuwe servermelding.')
    assert publish(store,'incident-two','De server is hersteld.')
    with closing(store.connect()) as conn:
        conversations=conn.execute("SELECT id FROM chat_conversations WHERE title='Leon updates'").fetchall()
    assert len(conversations)==1
    messages=ChatService(store).get_conversation(conversations[0][0])['messages']
    assert len(messages)==2 and messages[-1]['content']=='De server is hersteld.'
