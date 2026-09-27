"""Run standalone generated Python tool tests in a bounded offline container."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[2]
IMAGE_FILE=ROOT/'.runtime/code-test-image-id'


def snapshot_directory():
    # Docker's daemon cannot see a user's systemd PrivateTmp mount namespace.
    root=ROOT/'.runtime/code-containers'
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    return tempfile.TemporaryDirectory(prefix='snapshot-',dir=root)


def docker(args,*,timeout=10):
    # New login groups may not yet be inherited by the existing user manager.
    command=['sg','docker','-c',shlex.join(['/usr/bin/docker',*args])]
    return subprocess.run(command,env={'PATH':'/usr/bin:/bin','HOME':str(Path.home())},
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout,check=False)


def container_args(root,image,name):
    return ['run','--rm','--name',name,'--pull','never','--network','none','--read-only',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--user',f'{os.getuid()}:{os.getgid()}',
        '--pids-limit','64','--memory','256m','--memory-swap','256m','--cpus','1',
        '--ulimit','fsize=1048576:1048576','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
        '--log-driver','none','--mount',f'type=bind,src={root},dst=/work,readonly',
        '--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',image]


def test_artifacts(payload,*,image_file=IMAGE_FILE,runner=docker):
    try:image=image_file.read_text().strip()
    except OSError:return {'tests_executed':False,'tests_passed':False,'test_reason':'test_image_unavailable'}
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Invalid code test image')
    name='leon-code-test-'+uuid.uuid4().hex
    with snapshot_directory() as temp:
        root=Path(temp)
        for name_in_files in ('tool.py','test_tool.py'):
            (root/name_in_files).write_text(payload['files'][name_in_files]['source'])
        args=container_args(root,image,name)
        try:
            result=runner(args,timeout=35)
            executed=result.returncode in {0,1,2,3,4,5}
            return {'tests_executed':executed,'tests_passed':result.returncode==0,
                'test_exit_code':result.returncode,'test_image':image,
                'test_reason':'passed' if result.returncode==0 else 'test_failed' if executed else 'container_unavailable'}
        except subprocess.TimeoutExpired:
            return {'tests_executed':True,'tests_passed':False,'test_reason':'test_timeout','test_image':image}
        finally:
            runner(['rm','--force',name],timeout=5)
