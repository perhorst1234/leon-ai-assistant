from types import SimpleNamespace
import subprocess

from leon_control_plane.code_tests import test_artifacts as run_tests


def image(tmp_path):
    p=tmp_path/'image';p.write_text('sha256:'+'a'*64);return p


def payload():
    return {'files':{'tool.py':{'source':'def f(): return 1'},'test_tool.py':{'source':'def test_f(): assert True'}}}


def test_test_container_is_offline_bounded_and_cleaned(tmp_path):
    calls=[]
    def runner(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(returncode=0)
    result=run_tests(payload(),image_file=image(tmp_path),runner=runner)
    assert result['tests_executed'] and result['tests_passed']
    args=calls[0][0]
    assert args[args.index('--network')+1]=='none' and '--read-only' in args
    assert args[args.index('--cap-drop')+1]=='ALL'
    assert args[args.index('--mount')+1].endswith(',dst=/work,readonly')
    assert '--memory' in args and '--pids-limit' in args and '--cpus' in args
    assert '--privileged' not in args and '--env-file' not in args
    assert calls[-1][0][:2]==['rm','--force']


def test_no_tests_or_container_failure_is_not_success(tmp_path):
    for code,executed in [(5,True),(125,False)]:
        r=run_tests(payload(),image_file=image(tmp_path),runner=lambda *a,**k:SimpleNamespace(returncode=code))
        assert not r['tests_passed'] and r['tests_executed']==executed


def test_timeout_still_removes_only_owned_container(tmp_path):
    calls=[]
    def runner(args,**kwargs):
        calls.append(args)
        if args[0]=='run':raise subprocess.TimeoutExpired('docker',35)
        return SimpleNamespace(returncode=0)
    r=run_tests(payload(),image_file=image(tmp_path),runner=runner)
    assert r['test_reason']=='test_timeout' and not r['tests_passed']
    assert calls[-1][-1]==calls[0][calls[0].index('--name')+1]


def test_missing_image_does_not_execute(tmp_path):
    result=run_tests(payload(),image_file=tmp_path/'missing',runner=lambda *a,**k:None)
    assert result['tests_executed'] is False
