from concurrent.futures import ThreadPoolExecutor
import json
import time
from unittest.mock import patch

import pytest
from leon_control_plane.gpu_lease import acquire,busy
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
