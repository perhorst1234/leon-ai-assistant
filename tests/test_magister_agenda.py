from datetime import datetime
import pytest
from leon_control_plane.magister_agenda import preview

VALUES={'LEON_MAGISTER_SERVER':'vova.magister.net','LEON_MAGISTER_USERNAME':'student'}
START=datetime.fromisoformat('2026-09-28T00:00:00+02:00')
END=datetime.fromisoformat('2026-09-29T00:00:00+02:00')
ITEM={'id':1,'start':'2026-09-28T07:00:00Z','end':'2026-09-28T08:00:00Z','summary':'School lesson','location':'Room'}


def test_actual_source_schema_and_own_identity_are_required():
    calls=[]
    def run(script):calls.append(script);return {'total':1,'items':[ITEM]}
    d=preview(START,END,run=run,values=VALUES)
    assert d['calendar_connected'] and not d['truncated']
    assert d['items'][0]['id']=='magister-1' and d['items'][0]['source']=='Magister'
    assert 'String(p.stamnummer)!=="student"' in calls[0] and 'school_account_mismatch' in calls[0]
    assert 'location.hostname!=="vova.magister.net"' in calls[0]
    assert 'get("/api/account")' in calls[0] and 'status:1' in calls[0]


def test_complete_response_is_filtered_to_requested_interval():
    d=preview(START,END,run=lambda _: {'total':2,'items':[ITEM,{**ITEM,'id':2,'start':'2026-09-29T07:00:00Z','end':'2026-09-29T08:00:00Z'}]},values=VALUES)
    assert len(d['items'])==1 and not d['truncated']
    assert preview(START,END,run=lambda _: {'total':5,'items':[ITEM]},values=VALUES)['truncated']


@pytest.mark.parametrize('data',[{'total':0,'items':[ITEM]},{'total':1,'items':[{**ITEM,'start':'2026-09-28T07:00:00'}]},{'total':1,'items':[{**ITEM,'end':ITEM['start']}]},{'total':-1,'items':[]}])
def test_unknown_or_inconsistent_dates_never_become_free_time(data):
    with pytest.raises(ValueError):preview(START,END,run=lambda _:data,values=VALUES)


def test_period_is_bounded_before_browser_access():
    with pytest.raises(ValueError):preview(START,datetime.fromisoformat('2026-10-10T00:00:00+02:00'),run=lambda _:pytest.fail('browser called'),values=VALUES)


def test_school_lessons_block_google_gaps_and_missing_school_never_means_free(monkeypatch):
    from leon_control_plane.calendar_planner import find_slots
    monkeypatch.setattr('leon_control_plane.calendar_planner.preview',lambda *a:{'items':[],'truncated':False})
    school={'items':[{'id':'magister-1','start':{'date_time':'2026-09-28T09:00:00+02:00'},'end':{'date_time':'2026-09-28T12:00:00+02:00'}}],'truncated':False}
    monkeypatch.setattr('leon_control_plane.magister_agenda.preview',lambda *a:school)
    result=find_slots(None,{'LEON_MAGISTER_AGENDA_ENABLED':'1'},{'period':'today'},now=START)
    assert result['slots'][0]['start'][11:16]=='12:00' and 'Magister' in result['text']
    school['truncated']=True
    assert find_slots(None,{'LEON_MAGISTER_AGENDA_ENABLED':'1'},{'period':'today'},now=START)['status']=='incomplete'
    monkeypatch.setattr('leon_control_plane.magister_agenda.preview',lambda *a:(_ for _ in ()).throw(ValueError('expired')))
    assert find_slots(None,{'LEON_MAGISTER_AGENDA_ENABLED':'1'},{'period':'today'},now=START)['slots']==[]


def test_chat_school_read_uses_source_without_router_or_google(monkeypatch):
    from leon_control_plane.chat_actions import may_be_action,route,apply
    assert may_be_action('Toon mijn Magister-agenda morgen')
    decision=route('Toon mijn Magister-agenda morgen',[],{})
    assert decision=={'action':'school.read','args':{'period':'tomorrow'}}
    monkeypatch.setattr('leon_control_plane.magister_agenda.preview',lambda *a:{'items':[],'truncated':False})
    assert apply(None,'id',decision,None,owner_content='Toon mijn Magister-agenda morgen')=='Geen schoolafspraken in deze periode.'
