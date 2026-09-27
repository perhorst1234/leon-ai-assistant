"""Owner-operated school sign-in in Leon's existing server browser."""
from contextlib import closing
import json
import math
from pathlib import Path
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit
import urllib.request

from websockets.sync.client import connect as websocket_connect

LOCK = threading.Lock()
ROOT = Path(__file__).resolve().parents[2]


def student_username(account: str) -> str:
    return account.split('@',1)[0]


def config():
    from leon_control_plane.server import parse_selected_env_values
    values = parse_selected_env_values({'LEON_MAGISTER_SERVER','LEON_MAGISTER_USERNAME','LEON_MAGISTER_MICROSOFT_ACCOUNT'})
    if not values.get('LEON_MAGISTER_USERNAME') and values.get('LEON_MAGISTER_MICROSOFT_ACCOUNT'):
        values['LEON_MAGISTER_USERNAME'] = student_username(values['LEON_MAGISTER_MICROSOFT_ACCOUNT'])
    return values


def browser(script,*,click=False):
    # Address the school page itself. CDP's active tab is shared by other agents.
    try:
        with urllib.request.urlopen('http://127.0.0.1:9223/json/list',timeout=2) as response:
            targets=json.loads(response.read(262144))
        target=next(t for t in reversed(targets) if t.get('type')=='page' and
            urlsplit(t.get('url','')).hostname in {'vova.magister.net','accounts.magister.net','login.microsoftonline.com'})
        endpoint=target['webSocketDebuggerUrl']
        if urlsplit(endpoint).hostname not in {'127.0.0.1','localhost'} or urlsplit(endpoint).port!=9223:
            raise ValueError('invalid_browser_endpoint')
        with websocket_connect(endpoint,open_timeout=2,close_timeout=1,max_size=65536,proxy=None) as connection:
            connection.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':script,'returnByValue':True,'awaitPromise':True}}))
            deadline=time.monotonic()+5
            while True:
                value=json.loads(connection.recv(timeout=max(0.01,deadline-time.monotonic())))
                if value.get('id')==1:break
                if time.monotonic()>=deadline:raise TimeoutError()
            if click:
                raw=value.get('result',{}).get('result',{}).get('value')
                point=json.loads(raw) if isinstance(raw,str) else raw
                if not isinstance(point,dict) or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) or not 0<=point[k]<=50000 for k in ('x','y')):
                    raise ValueError('invalid_control_position')
                for index,kind in ((2,'mousePressed'),(3,'mouseReleased')):
                    connection.send(json.dumps({'id':index,'method':'Input.dispatchMouseEvent','params':{'type':kind,'x':point['x'],'y':point['y'],'button':'left','clickCount':1}}))
                    while True:
                        reply=json.loads(connection.recv(timeout=max(0.01,deadline-time.monotonic())))
                        if reply.get('id')==index:
                            if 'error' in reply:raise ValueError('browser_click_failed')
                            break
                return {'submitted':True}
        if 'error' in value or 'exceptionDetails' in value.get('result',{}):
            raise ValueError('browser_evaluation_failed')
        result=value['result']['result']['value']
        return json.loads(result) if isinstance(result,str) else result
    except Exception:
        # Errors can include script input; never expose them or secret values.
        raise ValueError('magister_browser_action_failed')


def start(values=None):
    values=config() if values is None else values
    if values.get('LEON_MAGISTER_SERVER')!='vova.magister.net' or not values.get('LEON_MAGISTER_USERNAME'):
        raise ValueError('magister_school_not_configured')
    candidates=sorted((Path.home()/'.npm/_npx').glob('*/node_modules/agent-browser/bin/agent-browser.js'))
    if not candidates:raise ValueError('magister_browser_unavailable')
    command=[str(Path.home()/'.local/bin/node'),str(candidates[0]),'--session','leon-magister-server','--max-output','1000']
    with LOCK:
        current=status(values)
        if current['state'] in {'password_needed','wrong_password','mfa_needed','signed_in_unverified'}:
            return current
        if current['state']=='school_needed':
            browser('(()=>{if(location.hostname!=="accounts.magister.net"||!document.querySelector("#scholenkiezer_value"))'
                'throw new Error("school_page_mismatch");location.assign("https://vova.magister.net");'
                'return JSON.stringify({submitted:true});})()')
            return {'configured':True,'school':'vova.magister.net','state':'signing_in','calendar_connected':False}
        if current['state']=='session_expired':
            browser('(()=>{if(location.hostname!=="accounts.magister.net")throw new Error("school_page_mismatch");'
                'const link=[...document.querySelectorAll("a")].find(a=>a.innerText.trim()==="Opnieuw inloggen");'
                'if(!link||new URL(link.href).hostname!=="accounts.magister.net")throw new Error("restart_control_missing");'
                'link.click();return JSON.stringify({submitted:true});})()')
            return {'configured':True,'school':'vova.magister.net','state':'signing_in','calendar_connected':False}
        if current['state']=='username_needed':
            browser('(()=>{if(location.hostname!=="accounts.magister.net")throw new Error("school_page_mismatch");'
                'const input=document.querySelector("#username:not([disabled]),input[autocomplete~=username]:not([disabled])");'
                'const button=document.querySelector("#username_submit")||[...document.querySelectorAll("button,sl-button")].find(b=>b.innerText.trim()==="Doorgaan");'
                'if(!input||!button)throw new Error("username_controls_missing");'
                'Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,'+json.dumps(values['LEON_MAGISTER_USERNAME'])+');'
                'input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));'
                'const r=button.getBoundingClientRect();if(button.disabled||r.width<=0||r.height<=0)throw new Error("username_control_not_ready");'
                'return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()',click=True)
            return {'configured':True,'school':'vova.magister.net','state':'signing_in','calendar_connected':False}
        for args in [['connect','http://127.0.0.1:9223'],['tab','new','https://vova.magister.net']]:
            result=subprocess.run(command+args,capture_output=True,text=True,timeout=6,check=False)
            if result.returncode:raise ValueError('magister_browser_action_failed')
        return {'configured':True,'school':'vova.magister.net','state':'login_needed','calendar_connected':False}


def status(values=None,run=browser):
    values = config() if values is None else values
    host = values.get('LEON_MAGISTER_SERVER')
    account = values.get('LEON_MAGISTER_MICROSOFT_ACCOUNT')
    if host!='vova.magister.net' or not account:
        return {'configured':False,'state':'not_configured'}
    try:
        result=run('JSON.stringify({host:location.hostname,password:!!document.querySelector("input[type=password]"),'
            'username:!!document.querySelector("#username:not([disabled]),input[autocomplete~=username]:not([disabled])"),'
            'school:!!document.querySelector("#scholenkiezer_value"),'
            'expired:/inloggen mislukt|opnieuw inloggen|sessie verlopen|login failed/i.test(document.body.innerText),'
            'wrong:/incorrect|onjuist|verkeerd wachtwoord/i.test(document.body.innerText),'
            'account:document.body.innerText.toLowerCase().includes('+json.dumps(account.lower())+'),'
            'code:!!document.querySelector("#idTxtBx_SAOTCC_OTC,[autocomplete=one-time-code]"),'
            'number:(document.querySelector("#idRichContext_DisplaySign")?.innerText??"").trim(),'
            'mfa:/authenticator|approve sign|goedkeur|verify your identity|identiteit verifi|enter code|code invoeren|verification code|verificatiecode/i.test(document.body.innerText)})')
        if result.get('host')=='login.microsoftonline.com' and result.get('account'):
            state='wrong_password' if result.get('wrong') else 'password_needed' if result.get('password') else 'mfa_needed' if result.get('mfa') or result.get('code') else 'signing_in'
        elif result.get('host')=='accounts.magister.net':
            state='session_expired' if result.get('expired') else 'school_needed' if result.get('school') else 'username_needed' if result.get('username') else 'signing_in'
        elif result.get('host')==host:
            state='signed_in_unverified'
        else:
            state='login_needed'
        result_data={'configured':True,'school':host,'account':account,'state':state,'calendar_connected':False}
        if state=='mfa_needed':
            result_data['mfa_kind']='code' if result.get('code') else 'approval'
            number=result.get('number','')
            if isinstance(number,str) and number.isdigit() and 1<=len(number)<=3:
                result_data['confirmation_number']=number
        return result_data
    except (ValueError,OSError,subprocess.TimeoutExpired):
        return {'configured':True,'school':host,'state':'browser_unavailable','calendar_connected':False}


def submit(store,data,values=None,run=browser):
    if not isinstance(data,dict) or set(data) not in ({'request_id','password'},{'request_id','code'}):
        raise ValueError('magister_invalid_login_request')
    request_id=str(uuid.UUID(data['request_id']))
    password=data.get('password')
    code=data.get('code')
    if password is not None and (not isinstance(password,str) or not 1<=len(password)<=512):
        raise ValueError('magister_password_required')
    if code is not None and (not isinstance(code,str) or not code.isdigit() or not 6<=len(code)<=8):
        raise ValueError('magister_invalid_verification_code')
    values=config() if values is None else values
    account=values.get('LEON_MAGISTER_MICROSOFT_ACCOUNT','')
    with LOCK:
        current=status(values,run)
        if password is not None and current['state'] not in {'password_needed','wrong_password'}:
            return current
        if code is not None and (current['state']!='mfa_needed' or current.get('mfa_kind')!='code'):
            return current
        with closing(store.connect()) as conn,conn:
            conn.execute('CREATE TABLE IF NOT EXISTS magister_login_attempts(request_id TEXT PRIMARY KEY,created_at REAL NOT NULL)')
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM magister_login_attempts WHERE request_id=?',(request_id,)).fetchone():
                return {**current,'state':'submission_unknown','automatic_retry':False}
            conn.execute('INSERT INTO magister_login_attempts VALUES(?,?)',(request_id,time.time()))
        selector='input[type=password]' if password is not None else '#idTxtBx_SAOTCC_OTC,[autocomplete=one-time-code]'
        script=('(()=>{const account='+json.dumps(account.lower())+';'
            'if(location.hostname!=="login.microsoftonline.com"||!document.body.innerText.toLowerCase().includes(account))'
            'throw new Error("account_mismatch");'
            'const input=document.querySelector('+json.dumps(selector)+');const button=document.querySelector("#idSIButton9,#idSubmit_SAOTCC_Continue");'
            'if(!input||!button)throw new Error("login_controls_missing");'
            'Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,'+json.dumps(password if password is not None else code)+');'
            'input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));'
            'button.click();return JSON.stringify({submitted:true});})()')
        run(script)
        return {'configured':True,'school':values['LEON_MAGISTER_SERVER'],'state':'signing_in','calendar_connected':False,'automatic_retry':False}
