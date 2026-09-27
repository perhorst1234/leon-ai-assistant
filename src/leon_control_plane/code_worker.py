"""Durable local file generation; execution/deployment require real test evidence."""
from contextlib import closing,contextmanager
import argparse
import ast
import hashlib
import fcntl
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import time
import uuid

from leon_control_plane.conversation_learning import ROOT
from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.code_tests import test_artifacts


@contextmanager
def lock(store,name):
    fd=os.open(Path(store.db_path).with_suffix('.'+name+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def initialize(store):
    store.initialize()
    with closing(store.connect()) as c,c:
        c.execute('''CREATE TABLE IF NOT EXISTS code_builds(
            id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,child_id TEXT NOT NULL,
            brief TEXT NOT NULL,status TEXT NOT NULL,payload TEXT,attempted_at REAL NOT NULL)''')


def enqueue(store,request_id,brief):
    initialize(store)
    request_id=str(uuid.UUID(request_id))
    if not isinstance(brief,str) or not 10<=len(brief.encode())<=2048:
        raise ValueError('Invalid coding brief')
    assert_no_secrets('Coding brief',brief)
    with lock(store,'code-enqueue'):
        with closing(store.connect()) as c:
            old=c.execute('SELECT * FROM code_builds WHERE id=?',(request_id,)).fetchone()
        if old:
            if old['brief']!=brief:raise ValueError('Coding request already belongs to another brief')
            return {'task_id':old['parent_id'],'status':old['status']}
        # Stable source references recover task creation after an interrupted enqueue.
        def task(marker,**kwargs):
            with closing(store.connect()) as c:
                row=c.execute('SELECT id FROM tasks WHERE EXISTS(SELECT 1 FROM json_each(tasks.source_refs_json) WHERE value=?)',(marker,)).fetchone()
            return row['id'] if row else store.create_task(source_refs=[marker],owner='Leon Code',risk_level='low',**kwargs)
        parent=task('code-request:'+request_id,title='Tool bouwen: '+brief[:80],goal=brief,
            acceptance_criteria='Code genereren, werkelijke uitvoeringstests en aansluiting bewijzen; broncode alleen is niet klaar.')
        child=task('code-generation:'+request_id,title='M40: broncode en tests schrijven',goal=brief,parent_task_id=parent,
            acceptance_criteria='Werkelijke bestanden met hashes bewaren; alleen codegeneratie, geen uitvoering of installatie claimen.')
        with closing(store.connect()) as c,c:
            c.execute("INSERT INTO code_builds VALUES(?,?,?,?,'queued',NULL,0)",(request_id,parent,child,brief))
        return {'task_id':parent,'status':'queued'}


def artifacts(workspace):
    result={}
    if {p.name for p in workspace.iterdir()}!={'tool.py','test_tool.py'}:
        raise ValueError('Unexpected coding output')
    for name in ('tool.py','test_tool.py'):
        fd=os.open(workspace/name,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('Invalid coding output')
            with os.fdopen(fd,'rb',closefd=False) as f:data=f.read(32769)
        finally:os.close(fd)
        if not data or len(data)>32768:raise ValueError('Coding output size limit')
        source=data.decode('utf-8');assert_no_secrets('Generated source',source)
        tree=ast.parse(source,filename=name)
        definitions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
        if not definitions or all(len(n.body)==1 and isinstance(n.body[0],ast.Pass) for n in definitions):
            raise ValueError('Coding output has no implementation')
        if name=='test_tool.py' and not any(isinstance(n,ast.Assert) for n in ast.walk(tree)):
            raise ValueError('Coding tests have no assertions')
        result[name]={'sha256':hashlib.sha256(data).hexdigest(),'source':source,'bytes':len(data)}
    return {'files':result,'syntax_checked':True,'tests_executed':False,'installed':False,'cost_microusd':0}


def generate(workspace,brief):
    workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    if any(workspace.iterdir()):raise ValueError('Coding workspace already contains an attempt')
    (workspace/'tool.py').write_text('# Implement the requested Python tool here.\n')
    (workspace/'test_tool.py').write_text('# Write meaningful pytest cases for tool.py here.\n')
    prompt=('Workspace: '+str(workspace)+'. Exact files: '+str(workspace/'tool.py')+' and '+str(workspace/'test_tool.py')+'. '
        'Use exactly these file paths; do not guess or change their spelling. '
        'Read tool.py and test_tool.py. Implement the owner request as a Python module in tool.py '
        'and meaningful pytest cases in test_tool.py. Use the Python standard library only. '
        'No shell, installation, credentials, or other files. Do not invent a successful external API call. '
        'If an API/account is missing, report that rather than pretending it works. '
        'Do not claim tests were run. Read back both files when finished. Owner request:\n'+brief)
    env={k:os.environ[k] for k in ('HOME','PATH','LANG') if k in os.environ}
    env.update({'LEON_CODING_COMPACT':'1','LEON_M40_CODING_TIMEOUT_SECONDS':'600'})
    # The wrapper owns process/thermal deadlines. Do not expose raw agent logs to chat.
    result=subprocess.run([str(ROOT/'scripts/leon-m40-coding-agent'),'run','--dir',str(workspace),
        '--agent','leon-compact','--format','json',prompt],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode==75:return None
    if result.returncode:raise ValueError('Coding agent did not complete')
    return artifacts(workspace)


def transition(store,task_id,target,**kwargs):
    current=store.get_task(task_id)['status']
    steps={'new':['planned','active'],'planned':['active'],'blocked':['active'],'active':[],'review':[],'done':[]}[current]
    for state in steps:store.update_task_status(task_id,state,actor_type='system',actor_id='code-worker')
    if store.get_task(task_id)['status']!=target:
        if target=='done' and store.get_task(task_id)['status']=='active':
            store.update_task_status(task_id,'review',actor_type='system',actor_id='code-worker')
        store.update_task_status(task_id,target,actor_type='system',actor_id='code-worker',**kwargs)


def finish(store,row,payload,notify):
    checked=payload.get('tests_passed',False)
    from leon_control_plane.code_tools import register
    external=bool(re.search(r'\b(mcp|api|plugin|installeer|marktplaats|vinted|ticketswap|google|agenda|gmail|magister|paypal|rabobank|server|printer|fluidd)\b',row['brief'],re.I))
    tools=register(store,row['id'],payload) if not external else []
    payload['installed']=bool(tools)
    payload['tool_ids']=tools
    with closing(store.connect()) as c,c:c.execute('UPDATE code_builds SET payload=? WHERE id=?',(json.dumps(payload),row['id']))
    summary='M40 heeft broncode en tests geschreven. Python-syntax gecontroleerd. '
    summary+=('De uitvoeringstests in Docker zijn geslaagd. '+('Beschikbaar vanuit chat: '+', '.join(t.split(':',1)[1] for t in tools)+'.\n' if tools else 'Live toolaansluiting nog niet uitgevoerd.\n') if checked else
        'Uitvoeringstests nog niet geslaagd: '+payload.get('test_reason','niet uitgevoerd')+'. Niets geïnstalleerd.\n')
    summary+='\n'.join(f"{name}: {f['bytes']} bytes, SHA256 {f['sha256']}" for name,f in payload['files'].items())
    transition(store,row['child_id'],'done',result=summary,verification_note='Bestanden werkelijk teruggelezen; AST-syntaxcheck, geen uitvoering.')
    # Offline function availability cannot prove a requested external integration.
    complete=bool(tools) and not external
    transition(store,row['parent_id'],'done' if complete else 'blocked',result=summary,
        **({'verification_note':'Werkelijke Docker-tests geslaagd; geteste bron/hash en aanroepbare offline functies geregistreerd.'} if complete else {'blocked_reason':'Live integratie nog niet bewezen.' if checked else 'Uitvoeringstests en toolaansluiting ontbreken.'}))
    if notify:
        from leon_control_plane.owner_updates import publish
        publish(store,'code-built:'+row['id'],summary+('Je kunt deze lokale functie nu in de chat gebruiken.' if complete else '\nDe opdracht blijft open tot de echte aansluiting bewezen is.'),request_id=row['id'])
    with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='built' WHERE id=?",(row['id'],))


def run_once(store,*,builder=generate,notify=True,clock=time.time):
    initialize(store)
    with lock(store,'code-worker'):
        # Owning the process lock proves no prior worker still owns these runs.
        # Preserve partial files and never replay an uncertain generation.
        with closing(store.connect()) as c:
            interrupted=c.execute("SELECT * FROM code_builds WHERE status='building' LIMIT 10").fetchall()
        for old in interrupted:
            for task_id in (old['child_id'],old['parent_id']):
                transition(store,task_id,'blocked',blocked_reason='Bouwwerker onderbroken; gedeeltelijke bestanden bewaard, geen automatische herhaling.')
            with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='failed' WHERE id=?",(old['id'],))
            if notify:
                from leon_control_plane.owner_updates import publish
                publish(store,'code-interrupted:'+old['id'],'De bouwwerker is onderbroken. De opdracht en blokkade staan in Werk; gedeeltelijke code wordt niet automatisch geïnstalleerd of opnieuw gebouwd.',request_id=old['id'])
        with closing(store.connect()) as c:
            row=c.execute("SELECT * FROM code_builds WHERE status='ready' ORDER BY attempted_at LIMIT 1").fetchone()
        if row:
            finish(store,row,json.loads(row['payload']),notify);return True
        with closing(store.connect()) as c:
            row=c.execute("SELECT * FROM code_builds WHERE status='queued' AND attempted_at<=? ORDER BY attempted_at,id LIMIT 1",(clock()-60,)).fetchone()
        if not row:return False
        # Short stable paths prevent the local model from mistyping long UUIDs.
        namespace=hashlib.sha256(str(Path(store.db_path).resolve()).encode()).hexdigest()[:8]
        workspace=Path.home()/'.local/state/leon/code'/namespace/row['id'].replace('-','')[:12]
        with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='building',attempted_at=? WHERE id=?",(clock(),row['id']))
        transition(store,row['parent_id'],'active')
        transition(store,row['child_id'],'active')
        try:
            payload=builder(workspace,row['brief'])
            if payload is None:
                # GPU yield/cooling: discard this private, unapplied file attempt.
                if workspace.exists():
                    for name in ('tool.py','test_tool.py'):
                        (workspace/name).unlink(missing_ok=True)
                    workspace.rmdir()
                with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='queued' WHERE id=?",(row['id'],))
                return False
            assert_no_secrets('Code artifacts',payload)
            payload.update(test_artifacts(payload))
        except Exception:
            transition(store,row['child_id'],'blocked',blocked_reason='Codebouw niet afgerond; onzekere pogingen worden niet automatisch herhaald.')
            transition(store,row['parent_id'],'blocked',blocked_reason='M40-codebouw niet afgerond; er is nog geen bruikbare tool.')
            with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='failed' WHERE id=?",(row['id'],))
            if notify:
                from leon_control_plane.owner_updates import publish
                publish(store,'code-failed:'+row['id'],'De M40-codebouw is niet afgerond. De opdracht staat met de blokkade in Werk; er is niets geïnstalleerd.',request_id=row['id'])
            return True
        with closing(store.connect()) as c,c:c.execute("UPDATE code_builds SET status='ready',payload=? WHERE id=?",(json.dumps(payload),row['id']))
        finish(store,row,payload,notify)
        return True


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--db',type=Path,default=ROOT/'.runtime/control-plane.sqlite')
    args=parser.parse_args(argv)
    print(json.dumps({'processed':run_once(ControlPlaneStore(args.db,ROOT/'state/control-plane.seed.json'))}))


if __name__=='__main__':main()
