from datetime import datetime
from unittest.mock import patch
import pytest

from leon_control_plane.calendar_planner import find_slots


def event(id,start,end,**fields):
    key='date' if len(start)==10 else 'date_time'
    return {'id':id,'start':{key:start},'end':{key:end},**fields}


def run(items,args=None,now='2026-09-28T08:00:00+02:00',truncated=False):
    with patch('leon_control_plane.calendar_planner.preview',return_value={'items':items,'truncated':truncated}) as read:
        result=find_slots(None,{},args or {'period':'today','duration_minutes':60},now=datetime.fromisoformat(now))
    assert read.call_args.args[3]['limit']==50
    return result


def test_overlapping_events_merge_and_end_boundary_is_free():
    items=[event('a','2026-09-28T09:00:00+02:00','2026-09-28T11:00:00+02:00'),
        event('b','2026-09-28T10:00:00+02:00','2026-09-28T12:00:00+02:00'),
        event('c','2026-09-28T13:00:00+02:00','2026-09-28T15:00:00+02:00')]
    result=run(items)
    assert [(s['start'][11:16],s['end'][11:16]) for s in result['slots']]==[('12:00','13:00'),('15:00','17:00')]


def test_all_day_event_blocks_day_and_cancelled_does_not():
    assert run([event('a','2026-09-28','2026-09-29')])['slots']==[]
    assert len(run([event('a','2026-09-28','2026-09-29',status='cancelled')])['slots'])==1
    assert len(run([event('a','2026-09-28','2026-09-29',transparency='transparent')])['slots'])==1


def test_normalized_google_nonblocking_events_remain_nonblocking():
    from leon_control_plane.google_readonly import _calendar_event
    raw={'id':'transparent-event','transparency':'transparent','start':{'date':'2026-09-28'},'end':{'date':'2026-09-29'}}
    assert len(run([_calendar_event(raw)])['slots'])==1


def test_chat_availability_command_uses_real_tool_even_without_word_agenda():
    from leon_control_plane.chat_actions import may_be_action,apply
    assert may_be_action('Wanneer heb ik een uurtje vrij?')
    assert may_be_action('Zoek vrije momenten voor morgen')
    with patch('leon_control_plane.server.parse_selected_env_values',return_value={}), \
         patch('leon_control_plane.calendar_planner.preview',return_value={'items':[],'truncated':False}):
        text=apply(None,'unused',{'action':'calendar.find_slots','args':{'period':'tomorrow','duration_minutes':60}},None)
    assert 'primaire Google-agenda' in text and 'geen afspraak aangemaakt' in text


def test_missing_pages_and_missing_truncation_marker_never_claim_availability():
    for marker in [True,None]:
        result=run([],truncated=marker)
        assert result['status']=='incomplete' and result['slots']==[]


def test_past_times_are_not_offered_and_midnight_offsets_follow_dst():
    result=run([],now='2026-09-28T10:30:15+02:00')
    assert result['slots'][0]['start']=='2026-09-28T10:31:00+02:00'
    result=run([],{'period':'week','duration_minutes':60},now='2026-10-23T08:00:00+02:00')
    assert result['slots'][0]['start'].endswith('+02:00')
    assert result['slots'][-1]['start'].endswith('+01:00')


def test_spring_clock_jump_does_not_invent_elapsed_time():
    result=run([],{'period':'today','duration_minutes':180,'day_start':'01:00','day_end':'04:00'},now='2027-03-28T00:00:00+01:00')
    assert result['slots']==[]  # Three hours on the clock, only two real hours.


def test_actual_model_datetime_windows_are_normalized_without_ignoring_date():
    args={'period':'today','duration_minutes':60,'day_start':'2026-09-28T09:00+02:00','day_end':'2026-09-28T17:00+02:00'}
    assert len(run([],args)['slots'])==1
    args['day_start']='2026-09-29T09:00+02:00'
    with pytest.raises(ValueError):run([],args)
    args['day_start']='2026-09-28T09:00+01:00'
    with pytest.raises(ValueError):run([],args)


@pytest.mark.parametrize('args',[{'duration_minutes':True},{'duration_minutes':0},{'period':'year'},
    {'day_start':'17:00','day_end':'09:00'},{'calendar_id':'foreign'},{'attendees':['other']}])
def test_invalid_requests_do_not_fetch_calendar(args):
    with patch('leon_control_plane.calendar_planner.preview') as read:
        with pytest.raises(ValueError):find_slots(None,{},args)
    read.assert_not_called()
