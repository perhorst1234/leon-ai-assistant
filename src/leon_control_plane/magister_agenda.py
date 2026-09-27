"""Read the owner's real school appointments using the existing browser session."""
from datetime import datetime,timedelta
import json
from zoneinfo import ZoneInfo

from leon_control_plane.magister_auth import browser,config
from leon_control_plane.secret_scanner import assert_no_secrets

ZONE=ZoneInfo('Europe/Amsterdam')


def preview(start=None,end=None,*,run=browser,values=None):
    values=config() if values is None else values
    if values.get('LEON_MAGISTER_SERVER')!='vova.magister.net' or not values.get('LEON_MAGISTER_USERNAME'):
        raise ValueError('magister_not_configured')
    start=start or datetime.now(ZONE).replace(hour=0,minute=0,second=0,microsecond=0)
    end=end or start+timedelta(days=7)
    if start.tzinfo is None or end.tzinfo is None or not timedelta(0)<end-start<=timedelta(days=7):
        raise ValueError('magister_invalid_period')
    first=start.astimezone(ZONE).date().isoformat()
    last=(end.astimezone(ZONE)-timedelta(microseconds=1)).date().isoformat()
    script=('(async()=>{if(location.hostname!=="vova.magister.net"||!window.angular)throw new Error("school_session_missing");'
        'const h=angular.element(document.body).injector().get("$http");'
        'const a=(await h.get("/api/account")).data;const id=a.Persoon?.Id;'
        'if(!Number.isInteger(id)||id<=0)throw new Error("school_identity_missing");'
        'const p=(await h.get("/api/leerlingen/"+id)).data;'
        'if(String(p.stamnummer)!=='+json.dumps(values['LEON_MAGISTER_USERNAME'])+')throw new Error("school_account_mismatch");'
        'const r=await h.get("/api/personen/"+id+"/afspraken",{params:{status:1,van:'+json.dumps(first)+',tot:'+json.dumps(last)+'}});'
        'if(r.status!==200||!Array.isArray(r.data.Items)||!Number.isInteger(r.data.TotalCount))throw new Error("school_calendar_missing");'
        'return JSON.stringify({total:r.data.TotalCount,items:r.data.Items.slice(0,50).map(e=>({id:e.Id,start:e.Start,end:e.Einde,summary:typeof e.Omschrijving==="string"?e.Omschrijving.slice(0,200):null,location:typeof e.Lokatie==="string"?e.Lokatie.slice(0,160):null}))});})()')
    data=run(script)
    if not isinstance(data,dict) or type(data.get('total')) is not int or data['total']<0 or not isinstance(data.get('items'),list) or len(data['items'])>50 or data['total']<len(data['items']):
        raise ValueError('magister_invalid_calendar')
    items=[]
    for e in data['items']:
        try:
            a=datetime.fromisoformat(e['start'].replace('Z','+00:00'));b=datetime.fromisoformat(e['end'].replace('Z','+00:00'))
            if not a.tzinfo or not b.tzinfo or b<=a or type(e['id']) is not int or not isinstance(e['summary'],str):raise ValueError()
            if b<=start or a>=end:continue
            items.append({'id':'magister-'+str(e['id']),'summary':e['summary'][:200],
                'start':{'date_time':a.isoformat()},'end':{'date_time':b.isoformat()},
                'location':str(e.get('location') or '')[:160],'source':'Magister','status':'confirmed'})
        except (KeyError,TypeError,ValueError):raise ValueError('magister_invalid_calendar') from None
    assert_no_secrets('School agenda',items)
    return {'items':items,'truncated':data['total']>len(data['items']),'calendar_connected':True,'source':'Magister','timezone':ZONE.key}
