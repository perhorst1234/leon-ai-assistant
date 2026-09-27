from dataclasses import replace
from unittest.mock import patch
import uuid
import pytest

from leon_control_plane.thermal_guard import Guard,available,check,temperature,notify
from leon_control_plane.local_model import LocalModelConfig,send_response,is_busy
from leon_control_plane.openai_text import ModelPreflightError
from leon_control_plane.work_queue import WorkQueue,MODEL_KIND,KIND
from test_control_plane import make_store


class Service:
    def __init__(self,active=True):self.active=active;self.calls=[];self.fail_start=False
    def __call__(self,action):
        self.calls.append(action)
        if action=='is-active':return self.active
        if action=='stop':self.active=False;return True
        if self.fail_start:return False
        self.active=True;return True


def test_trip_stops_owned_service_then_restarts_only_after_sustained_cooling(tmp_path):
    clock=[100.];host=Service();path=tmp_path/'thermal.json'
    guard=Guard(path=path,control=host,clock=lambda:clock[0])
    data,transition=guard.step(88)
    assert transition is None and available(path=path,now=100)
    data,transition=guard.step(89)
    assert transition=='trip' and data['stop_confirmed'] and not host.active
    assert not available(path=path,now=100)
    assert Guard(path=path,control=host).pending_event['phase']=='trip'
    clock[0]=101;guard.step(80)
    clock[0]=130;guard.step(80)
    assert not host.active
    clock[0]=131;data,transition=guard.step(80)
    assert host.active and transition=='recovered' and data['status']=='ready'
    assert host.calls.count('stop')==host.calls.count('start')==1


def test_unreadable_temperature_stops_and_rewarming_resets_cooling_interval(tmp_path):
    now=[100.];host=Service();guard=Guard(path=tmp_path/'guard',control=host,clock=lambda:now[0])
    assert guard.step(None)[1]=='trip'
    now[0]=110;guard.step(80)
    now[0]=139;guard.step(81)
    now[0]=150;guard.step(79)
    now[0]=180;assert guard.step(79)[1]=='recovered'


def test_system_clock_jump_cannot_shorten_physical_cooling_period(tmp_path):
    wall=[100.];elapsed=[0.];host=Service()
    guard=Guard(path=tmp_path/'guard',control=host,clock=lambda:wall[0],cool_clock=lambda:elapsed[0])
    guard.step(89);guard.step(79)
    wall[0]+=100000;elapsed[0]=10
    assert guard.step(79)[0]['status']=='cooling' and not host.active
    elapsed[0]=30
    assert guard.step(79)[1]=='recovered'


def test_guard_restart_preserves_ownership_and_does_not_restart_manual_stop(tmp_path):
    path=tmp_path/'guard';now=[100.];host=Service(False)
    guard=Guard(path=path,control=host,clock=lambda:now[0]);guard.step(90)
    guard=Guard(path=path,control=host,clock=lambda:now[0]);guard.step(75)
    now[0]=131;guard.step(75)
    assert 'start' not in host.calls and not host.active
    host.active=True;guard.step(90)
    guard=Guard(path=path,control=host,clock=lambda:now[0]);guard.step(75)
    host.fail_start=True;now[0]=162
    assert guard.step(75)[0]['status']=='cooling'
    host.fail_start=False;assert guard.step(75)[1]=='recovered'


def test_stale_missing_and_wrong_limit_guard_are_not_ready(tmp_path):
    path=tmp_path/'guard';guard=Guard(path=path,control=Service(),clock=lambda:100)
    assert not available(path=path,now=100)
    guard.step(70)
    assert not available(path=path,now=111)
    assert not available(path=path,now=99)
    assert not available(85,path=path,now=100)


def test_preflight_blocks_hot_or_unreadable_gpu_without_model_transport(tmp_path):
    from leon_control_plane.gpu_lease import acquire
    config=LocalModelConfig(enabled=True,thermal_guard_enabled=True)
    for temp in [None,89]:
        with patch('leon_control_plane.thermal_guard.available',return_value=True), \
             patch('leon_control_plane.thermal_guard.load',return_value={'temperature_c':temp}), \
             patch('leon_control_plane.gpu_lease.acquire',side_effect=lambda timeout,**kwargs:acquire(timeout,path=tmp_path/'test-gpu.lock',**kwargs)), \
             patch('leon_control_plane.local_model._send_response') as transport:
            with pytest.raises(ModelPreflightError):send_response({},config)
        transport.assert_not_called()
    with patch('leon_control_plane.thermal_guard.available',return_value=False),patch('leon_control_plane.local_model.http.client.HTTPConnection') as http:
        assert is_busy(config)
        http.assert_not_called()


def test_temperature_probe_selects_m40_and_rejects_multiple_or_failed_samples():
    from types import SimpleNamespace
    for output,code,expected in [('Tesla M40 24GB, 47',0,47),('Other GPU, 20\nTesla M40, 52\n',0,52),('Tesla M40, 52\nTesla M40, 53\n',0,None),('Tesla M40, 52',1,None),('Tesla M40, N/A',0,None)]:
        with patch('leon_control_plane.thermal_guard.subprocess.run',return_value=SimpleNamespace(stdout=output,returncode=code)) as run:
            assert temperature()==expected
            assert run.call_args.args[0][0]=='/usr/bin/nvidia-smi'


def test_persistent_sampler_keeps_latest_complete_measurement_and_closes_child():
    import os
    from types import SimpleNamespace
    from unittest.mock import Mock
    from leon_control_plane.thermal_guard import Samples
    read,write=os.pipe();stdout=os.fdopen(read,'rb',buffering=0)
    process=SimpleNamespace(stdout=stdout,terminate=Mock(),kill=Mock(),wait=Mock())
    samples=Samples(process)
    try:
        os.write(write,b'Tesla M40 24GB, 45\nTesla M40 24GB, 46\n')
        assert samples.read()==46
        os.write(write,b'Tesla M40 24GB, N/A\n')
        assert samples.read() is None
    finally:samples.close();os.close(write)
    process.terminate.assert_called_once()
    assert stdout.closed


def test_missing_sample_is_stopped_and_reported_before_hung_sampler_cleanup(monkeypatch):
    from leon_control_plane import thermal_guard
    calls=[]
    class Monitor:
        def __init__(self,**kwargs):self.pending_event=None
        def step(self,temp):
            assert temp is None
            calls.append('stop_and_persist')
            self.pending_event={'phase':'trip'}
            return {},'trip'
    class Sampler:
        def read(self):calls.append('sample');return None
        def close(self):calls.append('cleanup');raise RuntimeError('simulated hung cleanup')
    monkeypatch.setattr('sys.argv',['guard'])
    monkeypatch.setattr(thermal_guard,'Guard',Monitor)
    monkeypatch.setattr(thermal_guard,'Samples',Sampler)
    monkeypatch.setattr(thermal_guard,'notify',lambda *args:calls.append('notify'))
    with pytest.raises(RuntimeError,match='hung cleanup'):thermal_guard.main()
    assert calls==['sample','stop_and_persist','notify','cleanup']


def test_cooling_preserves_local_job_attempts_and_other_work_can_run(tmp_path):
    config=LocalModelConfig(enabled=True)
    queue=WorkQueue(make_store(tmp_path),local_model_config=config)
    task=queue.store.create_task(title='M40',goal='M40',risk_level='low')
    local=queue.enqueue(task_id=task,request_id=str(uuid.uuid4()),kind=MODEL_KIND,
        model_request={'prompt':'Hallo','max_output_tokens':32,'max_cost_microusd':1,'provider':'ollama','approve_external_text':True})
    other=queue.enqueue(task_id=task,request_id=str(uuid.uuid4()),kind=KIND)
    claim=queue.claim(local_ready=False)
    assert claim['id']==other['id']
    assert queue.get(local['id'])['status']=='queued' and queue.get(local['id'])['attempts']==0
    assert queue.claim(local_ready=True)['id']==local['id']


def test_worker_waits_for_guard_without_consuming_local_attempts(tmp_path):
    from leon_control_plane.local_worker import LocalWorker
    from leon_control_plane.model_work import ModelExecutor
    config=LocalModelConfig(enabled=True,thermal_guard_enabled=True)
    queue=WorkQueue(make_store(tmp_path),local_model_config=config)
    task=queue.store.create_task(title='M40',goal='M40',risk_level='low')
    local=queue.enqueue(task_id=task,request_id=str(uuid.uuid4()),kind=MODEL_KIND,
        model_request={'prompt':'Hallo','max_output_tokens':32,'max_cost_microusd':1,'provider':'ollama','approve_external_text':True})
    worker=LocalWorker(queue,model_executor=ModelExecutor(queue,local_config=config))
    with patch('leon_control_plane.thermal_guard.available',return_value=False):
        for _ in range(5):assert worker.run_once() is False
    assert queue.get(local['id'])['attempts']==0
    assert queue.get(local['id'])['status']=='queued'


def test_meaningful_thermal_events_are_deduplicated_in_chat_and_work(tmp_path):
    from contextlib import closing
    store=make_store(tmp_path)
    data={'incident':uuid.uuid4().hex,'temperature_c':89,'stop_confirmed':True}
    notify(data,'trip',store=store);notify(data,'trip',store=store)
    with closing(store.connect()) as c:
        task_id=c.execute('SELECT task_id FROM thermal_incidents').fetchone()[0]
        assert c.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==1
    assert store.get_task(task_id)['status']=='blocked'
    notify({**data,'temperature_c':79},'recovered',store=store)
    notify({**data,'temperature_c':79},'recovered',store=store)
    assert store.get_task(task_id)['status']=='done'
    with closing(store.connect()) as c:
        assert c.execute('SELECT COUNT(*) FROM thermal_incidents').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==2
