"""Find real gaps in the owner's primary calendar, without sample data."""
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from leon_control_plane.google_api import preview
from leon_control_plane.planner_preview import _free_slots

ZONE = ZoneInfo('Europe/Amsterdam')


def _clock(value, on_day):
    if not isinstance(value,str):raise ValueError('calendar_invalid_day_window')
    if 'T' in value:
        parsed=datetime.fromisoformat(value)
        local=parsed.astimezone(ZONE)
        if parsed.tzinfo is None or parsed.second or parsed.microsecond or parsed.date()!=on_day or local.replace(tzinfo=None)!=parsed.replace(tzinfo=None) or local.utcoffset()!=parsed.utcoffset():
            raise ValueError('calendar_invalid_day_window')
        value=parsed.strftime('%H:%M')
    parsed=time.fromisoformat(value)
    if parsed.tzinfo or parsed.second or parsed.microsecond:
        raise ValueError('calendar_invalid_day_window')
    return parsed


def _event_time(value):
    if 'date' in value:
        return datetime.combine(datetime.fromisoformat(value['date']).date(),time(),ZONE)
    parsed=datetime.fromisoformat(value['date_time'].replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('calendar_unknown_busy_time')
    return parsed.astimezone(ZONE)


def find_slots(store, values, args, *, now=None):
    if not isinstance(args,dict) or set(args)-{'period','duration_minutes','day_start','day_end'}:
        raise ValueError('calendar_invalid_slot_request')
    period=args.get('period','week')
    minutes=args.get('duration_minutes',60)
    if period not in {'today','tomorrow','week'} or type(minutes) is not int or not 15<=minutes<=480:
        raise ValueError('calendar_invalid_slot_request')
    now=(now or datetime.now(ZONE)).astimezone(ZONE)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1 if period=='tomorrow' else 0)
    end=start+timedelta(days=7 if period=='week' else 1)
    day_start=_clock(args.get('day_start','09:00'),start.date())
    day_end=_clock(args.get('day_end','17:00'),start.date())
    if day_start>=day_end:
        raise ValueError('calendar_invalid_day_window')
    data=preview(store,values,'calendar',{'start':start.isoformat(),'end':end.isoformat(),'timezone':ZONE.key,'limit':50})
    # Missing pages are not evidence that the remainder of a week is free.
    if data.get('truncated') is not False:
        return {'status':'incomplete','slots':[],'text':'Je agenda bevat meer afspraken dan ik volledig kon ophalen. Ik kan de vrije momenten niet bevestigen; vraag het voor één dag.'}
    school=False
    if values.get('LEON_MAGISTER_AGENDA_ENABLED')=='1':
        from leon_control_plane.magister_agenda import preview as school_preview
        try:
            extra=school_preview(start,end)
        except ValueError:
            return {'status':'incomplete','slots':[],'text':'Je schoolagenda is nu niet bereikbaar. Ik kan vrije momenten niet bevestigen zonder je lessen; controleer Magister in Vandaag.'}
        if extra.get('truncated') is not False:
            return {'status':'incomplete','slots':[],'text':'Je schoolagenda is niet volledig opgehaald. Ik kan de vrije momenten niet bevestigen; vraag het voor één dag.'}
        data={**data,'items':data['items']+extra['items']};school=True
    events=[]
    for item in data['items']:
        if item.get('status')=='cancelled' or item.get('transparency')=='transparent':continue
        event_start,event_end=_event_time(item['start']),_event_time(item['end'])
        if event_end.astimezone(UTC)<=event_start.astimezone(UTC):
            raise ValueError('calendar_unknown_busy_time')
        events.append({'id':item['id'],'start':event_start.isoformat(),'end':event_end.isoformat()})
    # Round up, so a suggested time never starts in the past.
    horizon=max(start,now.replace(second=0,microsecond=0)+timedelta(minutes=bool(now.second or now.microsecond)))
    slots=_free_slots(events=events,horizon_start=horizon,horizon_end=end,
        workday_start=day_start,workday_end=day_end,duration=timedelta(minutes=minutes))
    sources='Google-agenda en Magister' if school else 'primaire Google-agenda'
    text=f'Volgens je {sources}, tussen {day_start:%H:%M} en {day_end:%H:%M}, voor minimaal {minutes} minuten:'
    if slots:
        text+='\n'+'\n'.join('• '+datetime.fromisoformat(s['start']).strftime('%d-%m %H:%M')+'–'+datetime.fromisoformat(s['end']).strftime('%H:%M') for s in slots)
    else:text+='\nGeen passend vrij moment gevonden.'
    return {'status':'completed','slots':slots,'text':text+('\nJe primaire Google-agenda en schoollessen zijn meegenomen; er is geen afspraak aangemaakt.' if school else '\nAlleen je primaire agenda is meegenomen; er is geen afspraak aangemaakt.')}
