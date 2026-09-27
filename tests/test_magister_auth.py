from contextlib import closing
import json
import uuid

import pytest

from leon_control_plane.magister_auth import browser,config,status,submit
from test_control_plane import make_store

VALUES={'LEON_MAGISTER_SERVER':'vova.magister.net','LEON_MAGISTER_MICROSOFT_ACCOUNT':'student@example.edu'}


def test_school_username_uses_account_local_part_when_not_configured(monkeypatch):
    monkeypatch.setattr('leon_control_plane.server.parse_selected_env_values',lambda _:dict(VALUES))
    assert config()['LEON_MAGISTER_USERNAME']=='student'
    monkeypatch.setattr('leon_control_plane.server.parse_selected_env_values',lambda _:{**VALUES,'LEON_MAGISTER_USERNAME':'explicit'})
    assert config()['LEON_MAGISTER_USERNAME']=='explicit'


def test_browser_addresses_school_target_even_when_another_tab_is_active(monkeypatch):
    from io import BytesIO
    from contextlib import nullcontext
    targets=[{'type':'page','url':'https://login.microsoftonline.com/secret-oauth-query',
        'webSocketDebuggerUrl':'ws://127.0.0.1:9223/devtools/page/school'},
        {'type':'page','url':'http://127.0.0.1:3000','webSocketDebuggerUrl':'ws://127.0.0.1:9223/devtools/page/web'}]
    monkeypatch.setattr('leon_control_plane.magister_auth.urllib.request.urlopen',lambda *a,**k:BytesIO(json.dumps(targets).encode()))
    class Connection:
        def send(self,value):assert json.loads(value)['method']=='Runtime.evaluate'
        def recv(self,**kwargs):return json.dumps({'id':1,'result':{'result':{'value':'{"host":"login.microsoftonline.com"}'}}})
    def connect(endpoint,**kwargs):
        assert endpoint.endswith('/school')
        return nullcontext(Connection())
    monkeypatch.setattr('leon_control_plane.magister_auth.websocket_connect',connect)
    assert browser('JSON.stringify({host:location.hostname})')['host']=='login.microsoftonline.com'


def test_browser_errors_never_expose_secret_script(monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('dummy-private-input')
    monkeypatch.setattr('leon_control_plane.magister_auth.urllib.request.urlopen',fail)
    with pytest.raises(ValueError,match='^magister_browser_action_failed$'):
        browser('dummy-private-input')


def test_trusted_click_stays_on_school_cdp_target(monkeypatch):
    from io import BytesIO
    from contextlib import nullcontext
    targets=[{'type':'page','url':'https://accounts.magister.net/login','webSocketDebuggerUrl':'ws://127.0.0.1:9223/devtools/page/school'}]
    monkeypatch.setattr('leon_control_plane.magister_auth.urllib.request.urlopen',lambda *a,**k:BytesIO(json.dumps(targets).encode()))
    commands=[]
    class Connection:
        def send(self,value):commands.append(json.loads(value))
        def recv(self,**kwargs):
            id=commands[-1]['id']
            return json.dumps({'id':id,'result':{'result':{'value':'{"x":100,"y":200}'}}} if id==1 else {'id':id,'result':{}})
    monkeypatch.setattr('leon_control_plane.magister_auth.websocket_connect',lambda *a,**k:nullcontext(Connection()))
    assert browser('fixed-school-control-script',click=True)=={'submitted':True}
    assert commands[0]['params']['awaitPromise'] is True
    assert [c['params']['type'] for c in commands[1:]]==['mousePressed','mouseReleased']


def page(**kwargs):
    return {'host':'login.microsoftonline.com','account':True,'password':True,'mfa':False,'wrong':False,**kwargs}


def test_password_state_is_not_calendar_connection():
    result=status(VALUES,lambda _:page())
    assert result['state']=='password_needed' and result['calendar_connected'] is False


def test_expired_school_session_is_not_username_form():
    assert status(VALUES,lambda _:page(host='accounts.magister.net',expired=True,username=False))['state']=='session_expired'
    assert status(VALUES,lambda _:page(host='accounts.magister.net',expired=False,username=True))['state']=='username_needed'
    assert status(VALUES,lambda _:page(host='accounts.magister.net',expired=False,username=False))['state']=='signing_in'
    assert status(VALUES,lambda _:page(host='accounts.magister.net',expired=False,school=True,username=True))['state']=='school_needed'


def test_expired_session_restarts_exact_school_link_without_password(monkeypatch,tmp_path):
    from leon_control_plane.magister_auth import start
    binary=tmp_path/'.npm/_npx/example/node_modules/agent-browser/bin/agent-browser.js'
    binary.parent.mkdir(parents=True);binary.write_text('')
    monkeypatch.setenv('HOME',str(tmp_path));calls=[]
    monkeypatch.setattr('leon_control_plane.magister_auth.status',lambda _: {'state':'session_expired'})
    monkeypatch.setattr('leon_control_plane.magister_auth.browser',lambda script,**kwargs:calls.append(script))
    assert start({**VALUES,'LEON_MAGISTER_USERNAME':'student'})['state']=='signing_in'
    assert len(calls)==1 and 'Opnieuw inloggen' in calls[0] and 'new URL(link.href).hostname' in calls[0]
    assert 'input[type=password]' not in calls[0]


def test_school_username_targets_real_web_component_and_skips_school_field(monkeypatch,tmp_path):
    from leon_control_plane.magister_auth import start
    binary=tmp_path/'.npm/_npx/example/node_modules/agent-browser/bin/agent-browser.js'
    binary.parent.mkdir(parents=True);binary.write_text('')
    monkeypatch.setenv('HOME',str(tmp_path));calls=[]
    monkeypatch.setattr('leon_control_plane.magister_auth.status',lambda _: {'state':'username_needed'})
    monkeypatch.setattr('leon_control_plane.magister_auth.browser',lambda script,**kwargs:calls.append(script))
    assert start({**VALUES,'LEON_MAGISTER_USERNAME':'student'})['state']=='signing_in'
    assert '#username_submit' in calls[0] and 'button,sl-button' in calls[0] and '#username:not([disabled])' in calls[0]


def test_school_selector_opens_configured_portal_without_typing_student_number(monkeypatch,tmp_path):
    from leon_control_plane.magister_auth import start
    binary=tmp_path/'.npm/_npx/example/node_modules/agent-browser/bin/agent-browser.js'
    binary.parent.mkdir(parents=True);binary.write_text('')
    monkeypatch.setenv('HOME',str(tmp_path));calls=[]
    monkeypatch.setattr('leon_control_plane.magister_auth.status',lambda _: {'state':'school_needed'})
    monkeypatch.setattr('leon_control_plane.magister_auth.browser',lambda script,**kwargs:calls.append(script))
    start({**VALUES,'LEON_MAGISTER_USERNAME':'student'})
    assert 'location.assign("https://vova.magister.net")' in calls[0]
    assert 'set.call' not in calls[0]


def test_mfa_code_and_authenticator_number_are_distinct():
    code=status(VALUES,lambda _:page(password=False,code=True,mfa=True))
    assert code['state']=='mfa_needed' and code['mfa_kind']=='code'
    push=status(VALUES,lambda _:page(password=False,mfa=True,number='47'))
    assert push['mfa_kind']=='approval' and push['confirmation_number']=='47'
    assert 'confirmation_number' not in status(VALUES,lambda _:page(password=False,mfa=True,number='private account text'))


def test_password_is_only_in_transient_script_not_database_or_result(tmp_path):
    store=make_store(tmp_path);scripts=[]
    def browser(script):
        scripts.append(script)
        return page() if script.startswith('JSON.stringify') else {'submitted':True}
    request={'request_id':str(uuid.uuid4()),'password':'dummy-school-pass'}
    result=submit(store,request,VALUES,browser)
    assert result['state']=='signing_in' and 'dummy-school-pass' not in json.dumps(result)
    assert 'dummy-school-pass' in scripts[-1]
    assert 'login.microsoftonline.com' in scripts[-1] and 'account_mismatch' in scripts[-1]
    with closing(store.connect()) as c:
        assert 'dummy-school-pass' not in '\n'.join(c.iterdump())
    assert submit(store,request,VALUES,browser)['state']=='submission_unknown'
    assert len([s for s in scripts if 'button.click()' in s])==1


def test_code_is_only_submitted_to_visible_code_challenge(tmp_path):
    store=make_store(tmp_path);scripts=[]
    def browser(script):
        scripts.append(script);return page(password=False,mfa=True,code=True) if script.startswith('JSON.stringify') else {'submitted':True}
    assert submit(store,{'request_id':str(uuid.uuid4()),'code':'123456'},VALUES,browser)['state']=='signing_in'
    assert 'idTxtBx_SAOTCC_OTC' in scripts[-1]
    with closing(store.connect()) as c:
        assert '123456' not in '\n'.join(c.iterdump())


def test_foreign_page_or_account_never_gets_credentials(tmp_path):
    store=make_store(tmp_path);scripts=[]
    def browser(script):scripts.append(script);return page(account=False)
    result=submit(store,{'request_id':str(uuid.uuid4()),'password':'dummy-school-pass'},VALUES,browser)
    assert result['state']=='login_needed' and len(scripts)==1 and 'dummy-school-pass' not in scripts[0]


@pytest.mark.parametrize('data',[{'password':'dummy'}, {'request_id':'bad','password':'dummy'}, {'request_id':str(uuid.uuid4()),'code':'bad'}, {'request_id':str(uuid.uuid4()),'password':'dummy','code':'123456'}])
def test_malformed_submissions_are_not_sent(tmp_path,data):
    with pytest.raises(ValueError):submit(make_store(tmp_path),data,VALUES,lambda _:pytest.fail('sent'))
