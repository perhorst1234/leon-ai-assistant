"""Real weekly server inspection and limited recovery of Leon's own services."""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import argparse
import json
import os
import subprocess
import time
from zoneinfo import ZoneInfo

from leon_control_plane.server_monitor import server_status
from leon_control_plane.store import ControlPlaneStore

SERVICES = ('leon-backend', 'leon-web', 'leon-worker', 'leon-ollama')
RECOVERABLE = {'leon-backend', 'leon-web', 'leon-worker'}
COOLDOWN_SECONDS = 6 * 3600


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return result.stdout.strip()[:500]
    except (OSError, subprocess.TimeoutExpired):
        return 'unavailable'


def snapshot(root, run=command):
    health = server_status(paths=(('Leon', Path(root)),))
    states = {name: run(['systemctl','--user','is-active',name]) for name in SERVICES}
    if os.environ.get('LEON_M40_THERMAL_GUARD_ENABLED')=='1':
        states['leon-m40-guard']=run(['systemctl','--user','is-active','leon-m40-guard'])
    raw = run(['nvidia-smi','--query-gpu=temperature.gpu','--format=csv,noheader,nounits'])
    try:
        temp = int(raw.splitlines()[0])
        if not 0 <= temp <= 120:
            temp = None
    except (ValueError, IndexError):
        temp = None
    issues = [f'service:{name}:{state}' for name,state in states.items() if state != 'active']
    for disk in health['disk']:
        if disk['status'] == 'ok' and disk['free_bytes'] < 2 * 1024**3:
            issues.append('disk:less_than_2GB_free')
    if temp is not None and temp >= 89:
        issues.append('gpu:temperature_at_or_above_89C')
    return {'services':states,'gpu_temp_c':temp,'issues':issues,'disk':health['disk']}


def inspect(store, root, *, key=None, recover=True, notify=True, run=command, clock=time.time):
    store.initialize()
    now = clock()
    week = datetime.fromtimestamp(now, ZoneInfo('Europe/Amsterdam')).strftime('%G-W%V')
    key = key or 'server-week:' + week
    with closing(store.connect()) as conn, conn:
        conn.executescript('''CREATE TABLE IF NOT EXISTS server_inspections(
            key TEXT PRIMARY KEY, task_id TEXT, status TEXT NOT NULL, result_json TEXT, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS server_recovery(service TEXT PRIMARY KEY, attempted_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS server_health(id INTEGER PRIMARY KEY CHECK(id=1), issues_json TEXT NOT NULL);''')
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT status,result_json FROM server_inspections WHERE key=?',(key,)).fetchone()
        if old:
            return json.loads(old['result_json']) if old['result_json'] else {'status':'running_or_interrupted','automatic_retry':False}
        conn.execute("INSERT INTO server_inspections(key,status,created_at) VALUES(?,'running',?)",(key,now))
    task_id = store.create_task(title='Servercontrole '+week, goal='Controleer Leon-services, vrije schijfruimte en M40-temperatuur.',
        owner='Leon Server',risk_level='low',source_refs=[key],actor_type='system',actor_id='server-routine')
    for state in ('planned','active'):
        store.update_task_status(task_id,state,actor_type='system',actor_id='server-routine')
    before = snapshot(root,run)
    recovered = []
    if recover:
        for name,state in before['services'].items():
            if name not in RECOVERABLE or state not in {'failed','inactive'}:
                continue
            if name == 'leon-worker' and (before['gpu_temp_c'] is None or before['gpu_temp_c'] >= 89):
                continue
            with closing(store.connect()) as conn,conn:
                conn.execute('BEGIN IMMEDIATE')
                last = conn.execute('SELECT attempted_at FROM server_recovery WHERE service=?',(name,)).fetchone()
                if last and now-last[0] < COOLDOWN_SECONDS:
                    continue
                conn.execute('INSERT OR REPLACE INTO server_recovery VALUES(?,?)',(name,now))
            run(['systemctl','--user','restart',name])
            recovered.append(name)
    after = snapshot(root,run) if recovered else before
    result = {'status':'attention' if after['issues'] else 'healthy', 'task_id':task_id,
              'checked_at':now,'services':after['services'],'gpu_temp_c':after['gpu_temp_c'],
              'issues':after['issues'],'recovery_attempts':recovered,'week':week}
    text = describe(result)
    # The inspection is complete even if its observed system needs attention.
    # Failed services are evidence in the result, never a claim of recovery.
    store.update_task_status(task_id,'review',actor_type='system',actor_id='server-routine')
    store.update_task_status(task_id,'done',result=text,verification_note='Werkelijke vaste OS-probes; herstartresultaat opnieuw gecontroleerd.',actor_type='system',actor_id='server-routine')
    issues = json.dumps(sorted(after['issues']))
    with closing(store.connect()) as conn,conn:
        previous = conn.execute('SELECT issues_json FROM server_health WHERE id=1').fetchone()
        previous_issues = json.loads(previous[0]) if previous else []
    should_notify = bool(recovered or (previous_issues != sorted(after['issues']) and (previous_issues or after['issues'])))
    if should_notify and notify:
        from leon_control_plane.owner_updates import publish
        publish(store,key,text)
    with closing(store.connect()) as conn,conn:
        conn.execute('INSERT OR REPLACE INTO server_health VALUES(1,?)',(issues,))
        conn.execute("UPDATE server_inspections SET task_id=?,status='completed',result_json=? WHERE key=?",(task_id,json.dumps(result),key))
    return result


def describe(result):
    if result['issues']:
        message = 'De servercontrole vraagt aandacht: ' + ', '.join(result['issues']) + '.'
    else:
        message = 'Servercontrole afgerond: Leon-services actief en voldoende vrije schijfruimte.'
    if result['gpu_temp_c'] is not None:
        message += f" M40: {result['gpu_temp_c']} °C."
    if result.get('recovery_attempts'):
        message += ' Herstart geprobeerd voor: '+', '.join(result['recovery_attempts'])+'. De status is daarna opnieuw gecontroleerd.'
    return message


def main(argv=None):
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Leon weekly server inspection')
    parser.add_argument('--db',type=Path,default=root/'.runtime/control-plane.sqlite')
    args = parser.parse_args(argv)
    store = ControlPlaneStore(args.db, root/'state/control-plane.seed.json')
    result = inspect(store,root)
    print(json.dumps({'status':result['status'],'issues':len(result.get('issues',[])),'recovery_attempts':len(result.get('recovery_attempts',[]))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
