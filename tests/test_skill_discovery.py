from contextlib import closing
from unittest.mock import patch

import pytest

from leon_control_plane.skill_discovery import discover, candidates, search, validate_queries
from test_control_plane import make_store


def skill(store,number=1):
    return store.create_task(title='Vaardigheid: printer '+str(number),goal='Bouwprompt: Maak een Moonraker-koppeling '+str(number),owner='Leon Zelfleren',risk_level='low')


def metadata(name='io.github.example/moonraker'):
    return {'servers':[{'server':{'name':name,'version':'1.2.3','description':'Printer status',
        'repository':{'url':'https://github.com/example/moonraker'},
        'packages':[{'registryType':'pypi','identifier':'printer-mcp','version':'1.2.3'}]},
        '_meta':{'io.modelcontextprotocol.registry/official':{'status':'active'}}}]}


def test_real_search_child_completes_without_claiming_skill_installed(tmp_path):
    store=make_store(tmp_path);parent=skill(store);calls=[]
    result=discover(store,query_model=lambda _:['moonraker'],catalog=lambda q:calls.append(q) or candidates(metadata()),clock=lambda:100.)
    assert result=={'completed_searches':1,'cost_microusd':0} and calls==['moonraker']
    assert store.get_task(parent)['status']=='new'
    with closing(store.connect()) as conn:
        child=conn.execute('SELECT id FROM tasks WHERE parent_task_id=?',(parent,)).fetchone()
    task=store.get_task(child['id'])
    assert task['status']=='done' and '1.2.3' in task['result'] and 'niets is geïnstalleerd' in task['result']
    assert 'https://github.com/example/moonraker' in task['result']
    assert discover(store,query_model=lambda _:pytest.fail('repeated model'),clock=lambda:100000)['completed_searches']==0


def test_no_result_is_not_proof_of_no_available_tool(tmp_path):
    store=make_store(tmp_path);parent=skill(store)
    assert discover(store,query_model=lambda _:['fluidd'],catalog=lambda _:[],clock=lambda:100.,notify=False)['completed_searches']==1
    with closing(store.connect()) as c:
        assert 'Dit bewijst niet' in c.execute('SELECT result FROM tasks WHERE parent_task_id=?',(parent,)).fetchone()[0]


def test_failed_search_waits_one_day_then_reuses_child(tmp_path):
    store=make_store(tmp_path);parent=skill(store)
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _: (_ for _ in ()).throw(RuntimeError('network')),clock=lambda:100.,notify=False)['completed_searches']==0
    assert discover(store,query_model=lambda _:pytest.fail('early retry'),clock=lambda:200.,notify=False)['completed_searches']==0
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],clock=lambda:86501.,notify=False)['completed_searches']==1
    with closing(store.connect()) as c:
        assert c.execute('SELECT COUNT(*) FROM tasks WHERE parent_task_id=?',(parent,)).fetchone()[0]==1


def test_known_product_uses_local_names_without_unnecessary_model_call():
    from leon_control_plane.skill_discovery import queries
    with patch('leon_control_plane.shopper_runtime.model_json',side_effect=AssertionError('unnecessary inference')):
        assert queries('Bouwprompt: Koppel mijn Magister-agenda')==['magister']
        assert queries('Ik wil mijn Fluidd koppelen')==['fluidd','moonraker']


def test_explicit_retry_only_bypasses_verified_failed_cooldown(tmp_path):
    store=make_store(tmp_path);skill(store)
    discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:(_ for _ in ()).throw(RuntimeError()),clock=lambda:100.,notify=False)
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],clock=lambda:101.,notify=False,retry_failed=True)['completed_searches']==1


def test_pending_delivery_resumes_saved_catalog_without_another_request(tmp_path,monkeypatch):
    from leon_control_plane import owner_updates
    store=make_store(tmp_path);parent=skill(store);original=owner_updates.publish
    monkeypatch.setattr(owner_updates,'publish',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError):
        discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],clock=lambda:100.)
    monkeypatch.setattr(owner_updates,'publish',original)
    assert discover(store,query_model=lambda _:pytest.fail('repeated model'),catalog=lambda _:pytest.fail('repeated network'),clock=lambda:101.)['completed_searches']==1
    with closing(store.connect()) as c:
        assert c.execute('SELECT COUNT(*) FROM owner_updates').fetchone()[0]==1


def test_two_attempt_limit_and_ordinary_info_tasks_are_not_searched(tmp_path):
    store=make_store(tmp_path)
    for n in range(3):skill(store,n)
    store.create_task(title='Meer informatie: printer',goal='Vraag aan de eigenaar: IP?',owner='Leon Zelfleren',risk_level='low')
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],clock=lambda:100.,notify=False)['completed_searches']==2
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],clock=lambda:101.,notify=False)['completed_searches']==1


def test_changed_owner_goal_gets_new_discovery_instead_of_old_completion(tmp_path):
    store=make_store(tmp_path);parent=skill(store)
    assert discover(store,query_model=lambda _:['moonraker'],catalog=lambda _:[],notify=False)['completed_searches']==1
    with closing(store.connect()) as c,c:
        c.execute('UPDATE tasks SET goal=? WHERE id=?',('Bouwprompt: Zoek een andere printerkoppeling.',parent))
    assert discover(store,query_model=lambda _:['fluidd'],catalog=lambda _:[],notify=False)['completed_searches']==1


@pytest.mark.parametrize('query',['https://example.com','$(command)','mcp','foo bar','--install'])
def test_query_cannot_be_a_command_or_destination(query):
    with pytest.raises(ValueError):validate_queries({'queries':[query]})


def test_catalog_data_cannot_provide_executable_arguments_or_private_urls():
    data=metadata();server=data['servers'][0]['server']
    server['repository']['url']='https://localhost/secret'
    server['packages'][0]['runtimeArguments']=['--run-malicious-code']
    candidate=candidates(data)[0]
    assert candidate['repository']=='' and 'runtimeArguments' not in candidate['packages'][0]
    assert candidate['installed'] is candidate['cost_verified'] is False


def test_https_is_fixed_bounded_and_redirects_are_not_followed():
    calls=[]
    class Response:
        status=302
        def read(self,n):calls.append(n);return b'{}'
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('closed')
    class Opener:
        def open(self,request,timeout):calls.append((request.full_url,timeout));return Response()
    from leon_control_plane.skill_discovery import NoRedirect
    def build(handler):
        assert isinstance(handler,NoRedirect)
        assert handler.redirect_request(None,None,302,'',{},'https://evil.example') is None
        return Opener()
    with patch('leon_control_plane.skill_discovery.build_opener',build),pytest.raises(RuntimeError):
        search('moonraker')
    assert calls[0][0].startswith('https://registry.modelcontextprotocol.io/v0.1/servers?') and calls[0][1]==15 and calls[-1]=='closed'
    assert 262145 in calls
