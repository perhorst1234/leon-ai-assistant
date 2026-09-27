"""Register tested generated functions and invoke them only in offline Docker."""
from contextlib import closing
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import subprocess
import time
import uuid

from leon_control_plane.code_tests import container_args,docker,snapshot_directory
from leon_control_plane.secret_scanner import assert_no_secrets

TYPES={'str':str,'int':int,'float':(int,float),'bool':bool,'list':list,'dict':dict}
LOCAL_MODULES={'math','re','json','datetime','decimal','statistics','collections','itertools','functools','typing','hashlib','base64','unicodedata'}


def initialize(store):
    store.initialize()
    with closing(store.connect()) as c,c:
        c.executescript('''CREATE TABLE IF NOT EXISTS generated_tools(
            id TEXT PRIMARY KEY,build_id TEXT NOT NULL,name TEXT NOT NULL,
            schema_json TEXT NOT NULL,source TEXT NOT NULL,sha256 TEXT NOT NULL,
            test_image TEXT NOT NULL,created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS generated_tool_calls(
            id TEXT PRIMARY KEY,tool_id TEXT NOT NULL,args_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,result TEXT);
            CREATE TABLE IF NOT EXISTS generated_tool_requests(
            id TEXT PRIMARY KEY,tool_id TEXT NOT NULL,args_json TEXT NOT NULL,
            task_id TEXT NOT NULL,status TEXT NOT NULL,result TEXT);''')


def schemas(source):
    items=[]
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import) and any(a.name.split('.')[0] not in LOCAL_MODULES for a in node.names):return []
        if isinstance(node,ast.ImportFrom) and (node.level or (node.module or '').split('.')[0] not in LOCAL_MODULES):return []
    for node in tree.body:
        if not isinstance(node,ast.FunctionDef) or node.name.startswith('_'):continue
        if not re.fullmatch('[a-z][a-z0-9_]{0,63}',node.name) or node.decorator_list or node.args.posonlyargs or node.args.vararg or node.args.kwarg or node.args.kwonlyargs:continue
        if len(node.args.args)>8:continue
        params=[];defaults=len(node.args.defaults)
        for i,a in enumerate(node.args.args):
            annotation=a.annotation.id if isinstance(a.annotation,ast.Name) else 'json'
            if annotation not in TYPES:annotation='json'
            params.append({'name':a.arg,'type':annotation,'required':i<len(node.args.args)-defaults})
        items.append({'name':node.name,'parameters':params,'description':(ast.get_docstring(node) or 'Zelfgebouwde lokale functie')[:160]})
    return items[:4]


def register(store,build_id,payload):
    initialize(store);build_id=str(uuid.UUID(build_id))
    if payload.get('tests_executed') is not True or payload.get('tests_passed') is not True or payload.get('test_exit_code')!=0:return []
    image=payload.get('test_image','')
    if not isinstance(image,str) or not re.fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Invalid tested tool image')
    file=payload['files']['tool.py'];source=file['source']
    if not isinstance(source,str) or not 1<=len(source.encode())<=32768:raise ValueError('Invalid tool source')
    digest=hashlib.sha256(source.encode()).hexdigest()
    if digest!=file['sha256']:raise ValueError('Tested source digest mismatch')
    assert_no_secrets('Registered tool',source)
    items=schemas(source);assert_no_secrets('Tool metadata',items)
    with closing(store.connect()) as c,c:
        for item in items:
            key=build_id+':'+item['name']
            old=c.execute('SELECT sha256,test_image FROM generated_tools WHERE id=?',(key,)).fetchone()
            if old and (old['sha256']!=digest or old['test_image']!=image):raise ValueError('Registered tool identity changed')
            c.execute('INSERT OR IGNORE INTO generated_tools VALUES(?,?,?,?,?,?,?,?)',
                (key,build_id,item['name'],json.dumps(item),source,digest,image,time.time()))
    return [build_id+':'+i['name'] for i in items]


def catalog(store):
    initialize(store)
    with closing(store.connect()) as c:
        rows=c.execute('SELECT id,schema_json,source,sha256 FROM generated_tools ORDER BY created_at DESC,id LIMIT 8').fetchall()
    return [{'id':r['id'],**json.loads(r['schema_json'])} for r in rows
        if hashlib.sha256(r['source'].encode()).hexdigest()==r['sha256']]


SCRIPT='''import contextlib,json,os,sys
request=json.load(sys.stdin)
with open(os.devnull,'w') as quiet,contextlib.redirect_stdout(quiet):
 import tool
 result=getattr(tool,request['function'])(**request['args'])
print(json.dumps({'ok':True,'result':result},ensure_ascii=False,allow_nan=False))
'''


def execute_container(row,args):
    """Bound stdout while reading; never accumulate an unbounded communicate()."""
    name='leon-tool-call-'+uuid.uuid4().hex
    with snapshot_directory() as temp:
        root=Path(temp);(root/'tool.py').write_text(row['source']);(root/'runner.py').write_text(SCRIPT)
        argv=container_args(root,row['test_image'],name)
        argv.insert(1,'--interactive');argv+=['python','/work/runner.py']
        command=['sg','docker','-c',shlex.join(['/usr/bin/docker',*argv])]
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env={'PATH':'/usr/bin:/bin','HOME':str(Path.home())})
        try:
            process.stdin.write(json.dumps({'function':row['name'],'args':args},allow_nan=False).encode());process.stdin.close()
            output=bytearray();deadline=time.monotonic()+15
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                while True:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise ValueError('Tool execution timeout')
                    if not selector.select(remaining):raise ValueError('Tool execution timeout')
                    chunk=os.read(process.stdout.fileno(),4096)
                    if not chunk:break
                    output.extend(chunk)
                    if len(output)>8192:raise ValueError('Tool output too large')
            process.wait(timeout=2)
            if process.returncode:raise ValueError('Tool execution failed')
            value=json.loads(output,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Non-finite JSON')))
            if not isinstance(value,dict) or set(value)!={'ok','result'} or value['ok'] is not True:raise ValueError('Invalid tool result')
            assert_no_secrets('Generated tool result',value)
            return value['result']
        finally:
            try:docker(['rm','--force',name],timeout=5)
            finally:
                if process.poll() is None:process.kill()
                process.wait(timeout=2)
                if process.stdin and not process.stdin.closed:process.stdin.close()
                process.stdout.close()


def validate_arguments(store,tool_id,args):
    initialize(store)
    if not isinstance(args,dict) or len(json.dumps(args,allow_nan=False).encode())>4096:raise ValueError('Invalid tool arguments')
    assert_no_secrets('Tool arguments',args)
    with closing(store.connect()) as c:
        row=c.execute('SELECT * FROM generated_tools WHERE id=?',(tool_id,)).fetchone()
    if not row:raise ValueError('Unknown generated tool')
    if hashlib.sha256(row['source'].encode()).hexdigest()!=row['sha256']:raise ValueError('Registered source changed')
    params=json.loads(row['schema_json'])['parameters'];known={p['name'] for p in params}
    if set(args)-known or any(p['required'] and p['name'] not in args for p in params):raise ValueError('Missing or unexpected arguments')
    for p in params:
        if p['name'] not in args:continue
        value=args[p['name']];kind=p['type']
        if kind in TYPES and (not isinstance(value,TYPES[kind]) or kind in {'int','float'} and isinstance(value,bool)):
            raise ValueError('Wrong tool argument type')
    digest=hashlib.sha256(json.dumps(args,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return row,digest


def invoke(store,request_id,tool_id,args,*,executor=execute_container):
    request_id=str(uuid.UUID(request_id));row,digest=validate_arguments(store,tool_id,args)
    with closing(store.connect()) as c,c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM generated_tool_calls WHERE id=?',(request_id,)).fetchone()
        if old:
            if old['tool_id']!=tool_id or old['args_sha256']!=digest:raise ValueError('Tool request identity changed')
            if old['status']=='done':return json.loads(old['result'])
            raise ValueError('Tool result not confirmed; no automatic retry')
        c.execute("INSERT INTO generated_tool_calls VALUES(?,?,?,'running',NULL)",(request_id,tool_id,digest))
    try:
        result=executor(row,args);encoded=json.dumps(result,ensure_ascii=False,allow_nan=False)
        if len(encoded.encode())>8192:raise ValueError('Tool result too large')
        assert_no_secrets('Tool result',result)
    except Exception:
        with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_calls SET status='failed' WHERE id=?",(request_id,))
        raise ValueError('Generated tool execution not confirmed') from None
    with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_calls SET status='done',result=? WHERE id=?",(encoded,request_id))
    return result


def enqueue_call(store,request_id,tool_id,args):
    request_id=str(uuid.UUID(request_id));row,_=validate_arguments(store,tool_id,args)
    encoded=json.dumps(args,sort_keys=True,allow_nan=False)
    from leon_control_plane.code_worker import lock
    with lock(store,'tool-enqueue'):
        with closing(store.connect()) as c:
            old=c.execute('SELECT * FROM generated_tool_requests WHERE id=?',(request_id,)).fetchone()
            existing=c.execute('SELECT id FROM tasks WHERE EXISTS(SELECT 1 FROM json_each(source_refs_json) WHERE value=?)',('generated-call:'+request_id,)).fetchone()
        if old:
            if old['tool_id']!=tool_id or old['args_json']!=encoded:raise ValueError('Tool request identity changed')
            return old['task_id']
        task=existing['id'] if existing else store.create_task(title='Functie gebruiken: '+row['name'],
            goal='Voer de geteste lokale functie uit en bezorg het bevestigde resultaat in het oorspronkelijke gesprek.',
            owner='Leon Code',risk_level='low',source_refs=['generated-call:'+request_id])
        with closing(store.connect()) as c,c:c.execute("INSERT INTO generated_tool_requests VALUES(?,?,?,?,'queued',NULL)",(request_id,tool_id,encoded,task))
    # Wake the fixed worker; its timer also recovers a missed wakeup.
    try:subprocess.run(['systemctl','--user','start','--no-block','leon-code-tools.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,check=False)
    except (OSError,subprocess.TimeoutExpired):pass
    return task


def process_pending(store,*,executor=execute_container,notify=True):
    initialize(store)
    from leon_control_plane.code_worker import lock,transition
    from leon_control_plane.owner_updates import publish
    with lock(store,'tool-worker'):
        with closing(store.connect()) as c:
            rows=c.execute("SELECT * FROM generated_tool_requests WHERE status IN ('running','ready','queued') ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'ready' THEN 1 ELSE 2 END,rowid LIMIT 4").fetchall()
        for row in rows:
            if row['status']=='running':
                # Prior process no longer holds this lock. Reuse a saved call result.
                with closing(store.connect()) as c:call=c.execute('SELECT * FROM generated_tool_calls WHERE id=?',(row['id'],)).fetchone()
                if not call or call['status']!='done':
                    transition(store,row['task_id'],'blocked',blocked_reason='Functie-uitkomst onbekend; geen automatische herhaling.')
                    with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='failed' WHERE id=?",(row['id'],))
                    if notify:publish(store,'tool-call-failed:'+row['id'],'De functie-uitkomst is nog onbekend; ik herhaal de uitvoering niet automatisch. De opdracht staat in Werk.',request_id=row['id'])
                    continue
                saved=call['result']
            elif row['status']=='ready':saved=row['result']
            else:
                with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='running' WHERE id=?",(row['id'],))
                transition(store,row['task_id'],'active')
                try:saved=json.dumps(invoke(store,row['id'],row['tool_id'],json.loads(row['args_json']),executor=executor),ensure_ascii=False,allow_nan=False)
                except Exception:
                    transition(store,row['task_id'],'blocked',blocked_reason='Functie-uitvoering niet bevestigd; geen automatische herhaling.')
                    with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='failed' WHERE id=?",(row['id'],))
                    if notify:publish(store,'tool-call-failed:'+row['id'],'De lokale functie kon geen bevestigd resultaat leveren. De blokkade staat in Werk.',request_id=row['id'])
                    continue
            with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='ready',result=? WHERE id=?",(saved,row['id']))
            value=json.loads(saved);text='Resultaat: '+(value if isinstance(value,str) else saved)
            transition(store,row['task_id'],'done',result=text,verification_note='Resultaat werkelijk ontvangen uit de begrensde offline container.')
            if notify:publish(store,'tool-call-done:'+row['id'],text,request_id=row['id'])
            with closing(store.connect()) as c,c:c.execute("UPDATE generated_tool_requests SET status='done' WHERE id=?",(row['id'],))
        return len(rows)


def main(argv=None):
    from leon_control_plane.store import ControlPlaneStore
    from leon_control_plane.conversation_learning import ROOT
    parser=argparse.ArgumentParser();parser.add_argument('--db',type=Path,default=ROOT/'.runtime/control-plane.sqlite')
    args=parser.parse_args(argv)
    print(json.dumps({'processed':process_pending(ControlPlaneStore(args.db,ROOT/'state/control-plane.seed.json'))}))


if __name__=='__main__':main()
