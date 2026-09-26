"""One M40 inference owner across Leon workers and the coding wrapper."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import time

from leon_control_plane.openai_text import ModelPreflightError

LOCK_PATH = Path.home()/'.local/state/leon/m40.lock'


def busy(path=LOCK_PATH):
    try:
        fd=os.open(path,os.O_RDWR | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd,fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
    finally:
        os.close(fd)


@contextmanager
def acquire(timeout_seconds=180, *, path=LOCK_PATH):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,0o600)
    deadline=time.monotonic()+timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    raise ModelPreflightError('local_gpu_busy') from None
                time.sleep(0.1)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
