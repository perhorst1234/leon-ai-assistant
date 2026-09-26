"""Sampled M40 cutoff and cooling recovery for Leon's own Ollama service."""
import argparse
from contextlib import closing
import json
import os
import re
import selectors
from pathlib import Path
import subprocess
import time
import uuid

from leon_control_plane.openai_text import ModelPreflightError

STATE = Path.home()/'.local/state/leon/m40-thermal.json'
SERVICE = 'leon-ollama.service'


def temperature():
    try:
        result=subprocess.run(['/usr/bin/nvidia-smi','--query-gpu=name,temperature.gpu','--format=csv,noheader,nounits'],
            capture_output=True,text=True,timeout=3,check=False)
        rows=[line.rsplit(',',1)[1].strip() for line in result.stdout.splitlines() if re.fullmatch(r'Tesla M40(?: \d+GB)?',line.split(',',1)[0].strip())]
        if result.returncode==0 and len(rows)==1 and rows[0].isdigit() and 0<=int(rows[0])<=120:
            return int(rows[0])
    except (OSError,subprocess.TimeoutExpired,IndexError):pass
    return None


def load(path=STATE):
    try:
        data=json.loads(path.read_text())
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}


class Samples:
    """Keep NVML open; repeated initialization sometimes stalls on this VM."""
    def __init__(self,process=None):
        self.process=process or subprocess.Popen(['/usr/bin/nvidia-smi','--id=0',
            '--query-gpu=name,temperature.gpu','--format=csv,noheader,nounits','--loop=1'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)
        self.buffer=b''

    def read(self):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if not self.selector.select(max(0,deadline-time.monotonic())):return None
            chunk=os.read(self.process.stdout.fileno(),4096)
            if not chunk:return None
            self.buffer+=chunk
            if len(self.buffer)>8192:return None
            if b'\n' not in self.buffer:continue
            complete,self.buffer=self.buffer.rsplit(b'\n',1)
            lines=complete.decode('utf-8',errors='replace').splitlines()
            values=[line.rsplit(',',1)[1].strip() for line in lines if ',' in line and re.fullmatch(r'Tesla M40(?: \d+GB)?',line.split(',',1)[0].strip())]
            if values and values[-1].isdigit() and 0<=int(values[-1])<=120:return int(values[-1])
            return None
        return None

    def close(self):
        self.selector.close()
        self.process.terminate()
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
        self.process.stdout.close()


def available(limit=89, *, path=STATE, now=None):
    data=load(path)
    now=time.time() if now is None else now
    return (data.get('status')=='ready' and type(data.get('sampled_at')) in {int,float}
        and 0<=now-data['sampled_at']<=3 and data.get('limit_c')==limit)


def check(limit=89):
    if not available(limit):raise ModelPreflightError('local_gpu_cooling_or_guard_unavailable')
    temp=load().get('temperature_c')
    if type(temp) is not int:raise ModelPreflightError('local_gpu_temperature_unavailable')
    if temp>=limit:raise ModelPreflightError('local_gpu_too_hot')


def service(action):
    try:
        result=subprocess.run(['systemctl','--user',action,SERVICE],capture_output=True,text=True,timeout=5,check=False)
        return result.stdout.strip()=='active' if action=='is-active' else result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


class Guard:
    def __init__(self, *, path=STATE, limit=89, control=service, clock=time.time, cool_clock=None):
        if type(limit) is not int or not 65<=limit<=89:raise ValueError('Invalid M40 temperature limit')
        self.path,self.limit,self.control,self.clock=path,limit,control,clock
        self.cool_clock=cool_clock or (time.monotonic if clock is time.time else clock)
        old=load(path)
        self.cooling=old.get('status')=='cooling'
        self.restart_owed=self.cooling and old.get('restart_owed') is True
        self.incident=old.get('incident') if self.cooling else None
        self.pending_event=old.get('pending_event')
        self.cool_since=None

    def step(self,temp):
        now=self.clock();cool_now=self.cool_clock();transition=None;stop_confirmed=None
        if type(temp) is not int or not 0<=temp<=120:temp=None
        if temp is None or temp>=self.limit:
            if not self.cooling:
                self.incident=uuid.uuid4().hex;transition='trip'
            self.cooling=True;self.cool_since=None
            if self.control('is-active'):
                stopped=self.control('stop')
                stop_confirmed=stopped and not self.control('is-active')
                self.restart_owed=self.restart_owed or stop_confirmed
        elif self.cooling:
            if temp<=self.limit-9:
                if self.cool_since is None:self.cool_since=cool_now
                if cool_now-self.cool_since>=30:
                    restored=not self.restart_owed or (self.control('start') and self.control('is-active'))
                    if restored:
                        self.cooling=False;self.restart_owed=False;transition='recovered'
            else:self.cool_since=None
        data={'status':'cooling' if self.cooling else 'ready','sampled_at':now,'temperature_c':temp,
            'limit_c':self.limit,'restart_owed':bool(self.restart_owed),'incident':self.incident,
            'stop_confirmed':stop_confirmed}
        if transition:
            self.pending_event={'phase':transition,'incident':self.incident,'temperature_c':temp,'stop_confirmed':stop_confirmed}
        data['pending_event']=self.pending_event
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as handle:json.dump(data,handle)
        os.replace(temporary,self.path)
        return data,transition


def notify(data,transition, *, store=None):
    if not transition:return
    from leon_control_plane.store import ControlPlaneStore
    from leon_control_plane.owner_updates import publish
    root=Path(__file__).resolve().parents[2]
    store=store or ControlPlaneStore(Path(os.environ.get('LEON_DB_PATH',root/'.runtime/control-plane.sqlite')),root/'state/control-plane.seed.json')
    if transition=='recovered':text='De M40-metingen zijn weer goed en de kaart is koel. Lokale Leon-taken kunnen verder.'
    elif data['temperature_c'] is None:text='Ik kan de M40-temperatuur niet betrouwbaar lezen. Nieuwe lokale taken wachten op herstel.'
    else:text=f"De M40 bereikte {data['temperature_c']} °C. Nieuwe lokale taken wachten totdat hij voldoende is afgekoeld."
    if transition=='trip' and data['stop_confirmed']:text+=' De lokale modelservice is gestopt om af te koelen.'
    with closing(store.connect()) as conn,conn:
        conn.execute('CREATE TABLE IF NOT EXISTS thermal_incidents(incident TEXT PRIMARY KEY,task_id TEXT NOT NULL)')
        row=conn.execute('SELECT task_id FROM thermal_incidents WHERE incident=?',(data['incident'],)).fetchone()
    if row:task_id=row['task_id']
    else:
        task_id=store.create_task(title='M40 afkoelen',goal='Lokale modeltaken hervatten na bevestigde afkoeling.',owner='Leon Server',risk_level='low',source_refs=['thermal:'+str(data['incident'])])
        for status in ('planned','active'):store.update_task_status(task_id,status)
        with closing(store.connect()) as conn,conn:
            conn.execute('INSERT INTO thermal_incidents VALUES(?,?)',(data['incident'],task_id))
    task=store.get_task(task_id)
    if transition=='trip' and task['status']=='active':store.update_task_status(task_id,'blocked',blocked_reason=text)
    elif transition=='recovered' and task['status']!='done':
        if task['status']=='blocked':store.update_task_status(task_id,'active')
        store.update_task_status(task_id,'review')
        store.update_task_status(task_id,'done',result=text,verification_note='M40 gedurende 30 seconden onder de herstartgrens; eventuele eigen serviceherstart bevestigd.')
    publish(store,'thermal:'+str(data['incident'])+':'+transition,text)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    limit=int(os.environ.get('LEON_M40_MAX_TEMP_C','89'))
    if args.check:
        from leon_control_plane.local_model import LocalModelConfig
        limit=LocalModelConfig.from_env(env_file=Path(__file__).resolve().parents[2]/'.env.local').max_temp_c
        check(limit);return
    guard=Guard(limit=limit)
    samples=None
    while True:
        try:
            samples=samples or Samples()
            temp=samples.read()
        except OSError:temp=None
        data,transition=guard.step(temp)
        try:
            if guard.pending_event:
                notify(guard.pending_event,guard.pending_event['phase'])
                guard.pending_event=None
        except Exception:print('M40 notification unavailable',flush=True)
        if temp is None and samples:
            samples.close();samples=None
        if temp is None:time.sleep(2)


if __name__=='__main__':main()
