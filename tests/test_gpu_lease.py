from concurrent.futures import ThreadPoolExecutor
import json
import time
from unittest.mock import patch

import pytest
from leon_control_plane.gpu_lease import acquire,busy,waiting
from leon_control_plane.local_model import LocalModelConfig,is_busy
from leon_control_plane.openai_text import ModelPreflightError


def test_gpu_lease_is_shared_exclusive_and_released_after_exception(tmp_path):
    path=tmp_path/'m40.lock'
    assert not busy(path)
    with pytest.raises(ValueError):
        with acquire(path=path):
            assert busy(path)
            with pytest.raises(ModelPreflightError,match='local_gpu_busy'):
                with acquire(0,path=path):
                    pytest.fail('Concurrent inference must not start')
            raise ValueError('interrupted inference')
    assert not busy(path)
    with acquire(path=path):
        assert busy(path)


def test_waiting_request_runs_after_current_generation_finishes(tmp_path):
    path=tmp_path/'m40.lock'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with acquire(path=path):
            def waiting():
                with acquire(1,path=path):
                    return True
            future=pool.submit(waiting)
            time.sleep(.05)
            assert not future.done()
        assert future.result(timeout=2)


@pytest.mark.parametrize('models,expected', [([],False),([{'name':'qwen2.5-coder:14b'}],False),([{'name':'gpt-oss:20b'}],True),(None,True)])
def test_model_cache_does_not_force_paid_fallback(models,expected):
    class Response:
        status=200
        def read(self,*args):return json.dumps({'models':models}).encode()
    class Connection:
        def __init__(self,*args,**kwargs):pass
        def request(self,*args):pass
        def getresponse(self):return Response()
        def close(self):pass
    with patch('leon_control_plane.gpu_lease.busy',return_value=False),patch('leon_control_plane.local_model.http.client.HTTPConnection',Connection):
        assert is_busy(LocalModelConfig(enabled=True)) is expected


def test_inflight_generation_counts_as_busy_even_with_same_cached_model():
    with patch('leon_control_plane.gpu_lease.busy',return_value=True),patch('leon_control_plane.local_model.http.client.HTTPConnection') as http:
        assert is_busy(LocalModelConfig(enabled=True))
        http.assert_not_called()


def await_waiters(path,count):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if len(waiting(path=path))==count:return
        time.sleep(.01)
    pytest.fail('GPU request did not reach the shared queue')


@pytest.mark.parametrize('aged,expected',[(False,['chat','background']),(True,['background','chat'])])
def test_chat_priority_and_aging_prevent_background_starvation(tmp_path,aged,expected):
    import sqlite3
    path=tmp_path/'m40.lock';order=[]
    def run(priority):
        with acquire(3,path=path,priority=priority):order.append(priority)
    with ThreadPoolExecutor(max_workers=2) as pool:
        with acquire(path=path):
            background=pool.submit(run,'background');await_waiters(path,1)
            if aged:
                with sqlite3.connect(path.with_suffix('.queue.sqlite')) as conn:
                    conn.execute('UPDATE waiting SET created=created-90')
            chat=pool.submit(run,'chat');await_waiters(path,2)
            assert order==[]  # The existing generation is never preempted.
        background.result(timeout=4);chat.result(timeout=4)
    assert order==expected and waiting(path=path)==[]


def test_dead_process_or_old_boot_cannot_block_future_requests(tmp_path):
    import sqlite3
    from leon_control_plane.gpu_lease import _queue
    path=tmp_path/'m40.lock';path.parent.mkdir(exist_ok=True)
    conn=_queue(path)
    with conn:
        conn.execute('INSERT INTO waiting VALUES(?,?,?,?,?,?)',('dead',99999999,'old-boot',0,time.monotonic()-100,time.monotonic()+100))
    conn.close()
    with acquire(0,path=path,priority='chat'):assert busy(path)
    assert waiting(path=path)==[]


def test_timed_out_request_is_removed_without_stealing_existing_lease(tmp_path):
    path=tmp_path/'m40.lock'
    with acquire(path=path):
        with pytest.raises(ModelPreflightError,match='local_gpu_busy'):
            with acquire(0,path=path,priority='chat'):pytest.fail('Occupied lease')
        assert busy(path) and waiting(path=path)==[]


def test_verified_generation_release_does_not_depend_on_scheduler_database(tmp_path):
    path=tmp_path/'m40.lock';lease=acquire(path=path);lease.__enter__()
    with patch('leon_control_plane.gpu_lease._queue',side_effect=AssertionError('Database unavailable after generation')):
        lease.__exit__(None,None,None)
    assert not busy(path)
