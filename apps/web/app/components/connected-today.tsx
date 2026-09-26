'use client';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { MessageCircle, ArrowUpRight } from 'lucide-react';
import ConnectedGoogle from './connected-google';
import { normalizeGoogleStatus, type GoogleStatus } from './google-contract';
import ServerStatusCard from './server-status-card';
import WeatherCard from './weather-card';
import AutonomyCard from './autonomy-card';
import { normalizeAutonomyOverview } from '../../lib/autonomy-contract';
import './agent-work.css';
import './connected-work.css';

type Overview={work?:{job_count?:number;status_counts?:Record<string,number>};memory?:{item_count?:number}};
export default function ConnectedToday({ onOpenChat,onOpenWork,onOpenMemory }: { demo?:ReactNode;onOpenChat:()=>void;onOpenWork:()=>void;onOpenMemory:()=>void }) {
  const [overview,setOverview]=useState<Overview|null>(null);const [google,setGoogle]=useState<GoogleStatus|null>(null);const [watches,setWatches]=useState(0);const [error,setError]=useState('');const [details,setDetails]=useState(false);const [googleError,setGoogleError]=useState(false);
  const refresh=useCallback(async(signal:AbortSignal)=>{const r=await Promise.allSettled(['overview','google-status','shopper-state'].map(async(resource)=>{const response=await fetch(`/api/leon?resource=${resource}`,{signal,cache:'no-store'});const d=await response.json() as Overview & {error?:string;watches?:{enabled:boolean}[]};if(!response.ok)throw new Error(d.error||'Status niet bereikbaar');return d;}));if(signal.aborted)return;if(r[0].status==='fulfilled')setOverview(r[0].value);if(r[1].status==='fulfilled')setGoogle(normalizeGoogleStatus(r[1].value));if(r[2].status==='fulfilled')setWatches((r[2].value.watches||[]).filter((w:{enabled:boolean})=>w.enabled).length);setError(r.some(x=>x.status==='rejected')?'Een deel van de status is tijdelijk niet bereikbaar.':'');},[]);
  useEffect(()=>{const c=new AbortController();const timer=setTimeout(()=>{setGoogleError(new URLSearchParams(window.location.search).get('google')==='error');void refresh(c.signal);},0);return()=>{clearTimeout(timer);c.abort();};},[refresh]);
  return <div className="space-view today-focus"><header className="agent-page-header"><div><span className="agent-eyebrow">{new Date().toLocaleDateString('nl-NL',{timeZone:'Europe/Amsterdam',weekday:'long',day:'numeric',month:'long'})}</span><h1>Vandaag.</h1><p>Je agenda, je opdrachten en een gesprek met Leon.</p></div><button className="agent-primary" onClick={onOpenChat}><MessageCircle size={16}/> Praat met Leon</button></header>
    {googleError&&<p role="alert" className="today-error">Google verbinden is niet gelukt. Controleer de callback in Google Cloud en probeer opnieuw.</p>}{error&&<p className="today-error" role="alert">{error}</p>}
    <div className="today-focus-grid">{google?<ConnectedGoogle token="session" status={google}/>:<section className="today-focus-card"><h2>Je agenda</h2><p>Google-toegang controleren…</p></section>}
      <section className="today-focus-card"><h2>Wat Leon voor je doet</h2><p>Alle agents en opdrachten staan samen in Werk. Klap een taak open voor leads en voortgang.</p><div className="today-focus-stats"><span><strong>{watches}</strong>zoekopdrachten</span><span><strong>{overview?.work?.status_counts?.running??0}</strong>in uitvoering</span></div><button className="agent-quiet" onClick={onOpenWork}>Bekijk Werk <ArrowUpRight size={14}/></button></section>
    </div>
    <details className="today-more" onToggle={e=>setDetails(e.currentTarget.open)}><summary>Meer van vandaag</summary>{details&&<div className="today-more-body"><WeatherCard token="session" refreshId={0}/>{overview&&<AutonomyCard overview={normalizeAutonomyOverview(overview)} token="session" onRefresh={()=>refresh(new AbortController().signal)}/>}<ServerStatusCard token="session" refreshId={0}/><button className="agent-quiet" onClick={onOpenMemory}>Je geheugen · {overview?.memory?.item_count??0} items</button></div>}</details>
  </div>;
}
