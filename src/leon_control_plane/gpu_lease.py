"""One M40 inference owner across Leon workers and the coding wrapper."""
from contextlib import contextmanager
from contextlib import closing
import fcntl
import os
from pathlib import Path
import time
import sqlite3
import uuid

from leon_control_plane.openai_text import ModelPreflightError

LOCK_PATH = Path.home()/'.local/state/leon/m40.lock'
PRIORITIES={'chat':0,'reply':0,'shopper':1,'background':2,'coding':3}
AGE_SECONDS=30
try:BOOT_ID=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
except OSError:BOOT_ID=''


def _process_start(pid):
    try:return BOOT_ID+':'+Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None


def _queue(path):
    db=path.with_suffix('.queue.sqlite')
    if db.is_symlink():raise ModelPreflightError('local_gpu_scheduler_unavailable')
    conn=sqlite3.connect(db,timeout=2)
    os.chmod(db,0o600)
    conn.execute('CREATE TABLE IF NOT EXISTS waiting(id TEXT PRIMARY KEY,pid INTEGER,start TEXT,priority INTEGER,created REAL,expires REAL)')
    conn.commit()
    return conn


def _prune(conn,now):
    for id,pid,start,expires in conn.execute('SELECT id,pid,start,expires FROM waiting').fetchall():
        if expires<now or _process_start(pid)!=start:
            conn.execute('DELETE FROM waiting WHERE id=?',(id,))


def waiting(*,path=LOCK_PATH):
    """Metadata only; no prompts or task contents enter GPU coordination."""
    if not path.parent.exists():return []
    now=time.monotonic()
    with closing(_queue(path)) as conn,conn:
        _prune(conn,now)
        return [{'priority':row[0],'waiting_seconds':max(0,round(now-row[1],1))}
            for row in conn.execute('SELECT priority,created FROM waiting ORDER BY created')]


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
def acquire(timeout_seconds=180, *, path=LOCK_PATH,priority='background'):
    if priority not in PRIORITIES:raise ModelPreflightError('local_gpu_priority_invalid')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,0o600)
    deadline=time.monotonic()+timeout_seconds
    ticket=uuid.uuid4().hex
    acquired=False
    try:
        with closing(_queue(path)) as conn,conn:
            conn.execute('INSERT INTO waiting VALUES(?,?,?,?,?,?)',(ticket,os.getpid(),_process_start(os.getpid()),PRIORITIES[priority],time.monotonic(),deadline+2))
        while True:
            acquired=False
            with closing(_queue(path)) as conn,conn:
                conn.execute('BEGIN IMMEDIATE')
                now=time.monotonic();_prune(conn,now)
                head=conn.execute('SELECT id FROM waiting ORDER BY MAX(0,priority-CAST((?-created)/? AS INTEGER)),created,id LIMIT 1',(now,AGE_SECONDS)).fetchone()
                if head and head[0]==ticket:
                    try:
                        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
                        conn.execute('DELETE FROM waiting WHERE id=?',(ticket,));acquired=True
                    except BlockingIOError:pass
            if acquired:break
            if time.monotonic()>=deadline:
                raise ModelPreflightError('local_gpu_busy') from None
            time.sleep(0.1)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
        if not acquired:
            try:
                with closing(_queue(path)) as conn,conn:
                    conn.execute('DELETE FROM waiting WHERE id=?',(ticket,))
            except sqlite3.Error:pass  # Expiry/dead-process pruning remains available.


if __name__=='__main__':
    # The coding wrapper has already taken FD9; yield if a request is waiting.
    raise SystemExit(75 if waiting() else 0)
