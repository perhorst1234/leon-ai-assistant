'use client';
import { useCallback, useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { buildCalendarPreviewPayload, defaultCalendarDraft, formatGoogleDate, normalizeCalendarPreview, normalizeMailPreview, type CalendarPreviewItem, type MailPreviewItem, type GoogleStatus } from './google-contract';

export default function ConnectedGoogle({ status }: { token: string; status: GoogleStatus }) {
  const [events,setEvents]=useState<CalendarPreviewItem[]|null>(null);const [mail,setMail]=useState<MailPreviewItem[]|null>(null);const [error,setError]=useState('');
  const load=useCallback(async(kind:'calendar'|'mail',signal:AbortSignal)=>{try{const r=await fetch(`/api/leon?resource=google-${kind}-preview`,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(kind==='calendar'?buildCalendarPreviewPayload(defaultCalendarDraft()):{limit:5})});const d=await r.json() as {error?:string};if(!r.ok)throw new Error(d.error||'Google niet bereikbaar');if(kind==='calendar')setEvents(normalizeCalendarPreview(d));else setMail(normalizeMailPreview(d));setError('');}catch(e){if(!signal.aborted)setError(e instanceof Error?e.message:'Google niet bereikbaar');}},[]);
  useEffect(()=>{if(!status.configured||!status.scopes.calendar)return;const c=new AbortController();const timer=setTimeout(()=>void load('calendar',c.signal),0);return()=>{clearTimeout(timer);c.abort();};},[load,status.configured,status.scopes.calendar]);
  return <section className="today-focus-card"><h2><CalendarDays size={17}/> Je agenda</h2>
    {!status.configured||!status.scopes.calendar?<><p>Verbind Google één keer. Daarna toont Leon hier je komende afspraken en kun je er in de chat naar vragen.</p><a className="google-connect" href="/api/google/oauth/start">Google verbinden</a></>:events===null?<p>{error?'Agenda tijdelijk niet beschikbaar.':'Afspraken ophalen…'}</p>:events.length?<ul className="agenda-list">{events.slice(0,3).map(e=><li key={e.id}><strong>{e.summary}</strong><small>{formatGoogleDate(e.start,e.allDay)}{e.allDay?' · hele dag':''}</small></li>)}</ul>:<p>Geen afspraken in de komende dagen.</p>}
    {events&&events.length>3&&<details className="google-mail-details"><summary>{events.length-3} overige afspraken</summary><ul className="agenda-list">{events.slice(3).map(e=><li key={e.id}><strong>{e.summary}</strong><small>{formatGoogleDate(e.start,e.allDay)}</small></li>)}</ul></details>}
    {status.configured&&status.scopes.mail&&<details className="google-mail-details" onToggle={e=>{if(e.currentTarget.open&&mail===null)void load('mail',new AbortController().signal);}}><summary>Recente mail</summary>{mail?.map(m=><p key={m.id}>{m.subject}<br/><small>{m.from}</small></p>)}</details>}
    {error&&<p role="alert" className="today-error">Google ophalen is niet gelukt. <a href="/api/google/oauth/start">Opnieuw verbinden</a></p>}
  </section>;
}
