import subprocess
import sys
from unittest.mock import patch

import pytest

from leon_control_plane.coding_process import run
from leon_control_plane.openai_text import ModelPreflightError


def test_actual_process_exit_code_is_preserved():
    assert run([sys.executable,'-c','raise SystemExit(7)'],probe=lambda _:42)==7


def test_failed_preflight_does_not_start_process():
    with patch('leon_control_plane.coding_process.subprocess.Popen') as launch,pytest.raises(ModelPreflightError):
        run(['unused'],probe=lambda _:(_ for _ in ()).throw(ModelPreflightError('cooling')))
    launch.assert_not_called()


def test_actual_running_process_stops_when_guard_fails():
    count=[0]; processes=[];original=subprocess.Popen
    def probe(_):
        count[0]+=1
        if count[0]>1:raise ModelPreflightError('cooling')
        return 42
    def launch(*a,**k):
        p=original(*a,**k);processes.append(p);return p
    with patch('leon_control_plane.coding_process.subprocess.Popen',launch):
        assert run([sys.executable,'-c','import time; time.sleep(100)'],probe=probe)==75
    assert processes[0].poll() is not None


def test_actual_running_process_has_monotone_deadline():
    values=iter([0,11])
    assert run([sys.executable,'-c','import time; time.sleep(100)'],seconds=10,probe=lambda _:42,clock=lambda:next(values))==124
