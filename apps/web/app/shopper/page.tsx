'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { createRequestId } from '../lib/request-id';
import './shopper.css';

type Match = { url: string; title: string; asking_price_cents: number | null; capacity_gb: number | null; notes: string[] };
type Run = { status: string; started_at: number; finished_at: number | null; result: { matches: Match[]; reason?: string; listings_checked?: number; agent?: { status: string; reason?: string; model?: string; offer_cents?: number; conversation_url?: string } } | null };
type Watch = { id: string; platform: string; query: string; max_total_cents: number; enabled: boolean; next_run: number; latest_run: Run | null; held_contacts?: number; min_ram_gb?: number; fallback_after?: number; fallback_min_ram_gb?: number; replies?: { status: string; due_at: number; conversation_url: string }[] };
type ShopperState = { browser_connected: boolean; watches: Watch[] };
const money = (cents: number) => new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(cents / 100);
const date = (seconds: number) => new Date(seconds * 1000).toLocaleString('nl-NL');
const labels: Record<string, string> = { running: 'Zoeken…', complete: 'Zoekronde klaar', disconnected: 'Browser niet bereikbaar', needs_owner: 'Controleer de website in Chrome', interrupted: 'Zoekronde onderbroken' };

async function api(resource: string, body?: unknown) {
  const response = await fetch(`/api/leon?resource=${resource}`, {
    method: body === undefined ? 'GET' : 'POST', cache: 'no-store', signal: AbortSignal.timeout(9000),
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  });
  const result = await response.json() as ShopperState & { error?: string; watch?: { id: string } };
  if (!response.ok) throw new Error(typeof result.error === 'string' ? result.error : 'Shopper niet bereikbaar');
  return result;
}

export default function ShopperPage() {
  const [state, setState] = useState<ShopperState | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('DDR3 RAM');
  const [platform, setPlatform] = useState('marktplaats');
  const [budget, setBudget] = useState('49.99');
  const [minimum, setMinimum] = useState('128');
  const [preferred, setPreferred] = useState('128');
  const [slots, setSlots] = useState('4');
  const [automaticMessages, setAutomaticMessages] = useState(true);
  const refresh = useCallback(async () => {
    try {
      const result = await api('shopper-state');
      if (!Array.isArray(result.watches) || typeof result.browser_connected !== 'boolean') throw new Error('Ongeldige shopperstatus');
      setState(result); setError('');
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Shopper niet bereikbaar'); }
  }, []);
  useEffect(() => {
    const initial = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 10000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [refresh]);

  async function mutate(resource: string, body: unknown) {
    setBusy(true); setError('');
    try { const result = await api(resource, body); await refresh(); return result; }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Actie mislukt'); }
    finally { setBusy(false); }
  }

  return <main className="shopper-shell">
    <header><Link href="/">← Leon</Link><span>Shopper</span></header>
    <h1>Laat Leon aanbiedingen volgen.</h1>
    <p className="shopper-intro">Je zoekopdrachten blijven actief. Iedere week volgt een nieuwe zoekronde; resultaten en volgende controles staan hier.</p>
    <p className="shopper-connection" role="status">{state ? state.browser_connected ? 'Leons serverbrowser draait' : 'Leons serverbrowser is niet bereikbaar' : 'Verbinding controleren…'}</p>
    <p className="shopper-muted">Nieuwe berichten wekken Leon via de serverbrowser. Hij wacht 15–45 minuten en reageert tussen 08:00 en 23:00 Nederlandse tijd. Nachtelijke reacties wachten tot de ochtend.</p>
    {error && <p className="shopper-error" role="alert">{error} <Link href="/">Naar Leon / inloggen</Link></p>}
    <section className="shopper-panel"><h2>Nieuwe zoekopdracht</h2>
      <form onSubmit={event => { event.preventDefault(); void mutate('shopper-watches', {
        request_id: createRequestId(), platform, query, max_total_cents: Math.round(Number(budget) * 100),
        min_ram_gb: Number(minimum), preferred_ram_gb: Number(preferred), max_ram_sticks: Number(slots),
        automatic_messages: platform === 'marktplaats' && automaticMessages,
        required_terms: /ddr3/i.test(query) ? ['ddr3'] : [], excluded_terms: /ddr3/i.test(query) ? ['ddr4', 'sodimm', 'so-dimm'] : [],
      }).then(result => { if (result?.watch?.id) void mutate('shopper-run', { watch_id: result.watch.id }); }); }}>
        <label>Zoeken naar<input value={query} onChange={event => setQuery(event.target.value)} required maxLength={160}/></label>
        <label>Platform<select value={platform} onChange={event => setPlatform(event.target.value)}><option value="marktplaats">Marktplaats</option><option value="vinted">Vinted</option></select></label>
        <label>Maximale totaalprijs (€)<input value={budget} onChange={event => setBudget(event.target.value)} type="number" min="0.01" max="10000" step="0.01" required/></label>
        <label>Minimaal RAM (GB, 0 = geen eis)<input value={minimum} onChange={event => setMinimum(event.target.value)} type="number" min="0" max="1024" required/></label>
        <label>Voorkeur RAM (GB, 0 = geen voorkeur)<input value={preferred} onChange={event => setPreferred(event.target.value)} type="number" min="0" max="1024" required/></label>
        <label>Geheugenslots (0 = geen eis)<input value={slots} onChange={event => setSlots(event.target.value)} type="number" min="0" max="32" required/></label>
        {platform === 'marktplaats' && <label><span><input type="checkbox" checked={automaticMessages} onChange={event => setAutomaticMessages(event.target.checked)} style={{ width: 'auto', marginRight: 8 }}/>Leon mag zelf naar prijs en beschikbaarheid vragen</span><small>Lokale M40-agent, maximaal één contact per zoekronde en twee per dag. Kopen blijft jouw beslissing.</small></label>}
        <button disabled={busy || !state} type="submit">{busy ? 'Opslaan…' : 'Volgen en zoeken'}</button>
      </form>
    </section>
    <div className="shopper-watches">{state?.watches.map(watch => <section className="shopper-panel" key={watch.id}>
      <div className="shopper-watch-heading"><div><small>{watch.platform} · maximaal {money(watch.max_total_cents)}</small><h2>{watch.query}</h2></div><span>{watch.enabled ? 'Actief' : 'Gepauzeerd'}</span></div>
      <p>{watch.latest_run ? labels[watch.latest_run.status] || watch.latest_run.status : 'Nog geen zoekronde'}{watch.latest_run?.finished_at ? ` · ${date(watch.latest_run.finished_at)}` : ''}</p>
      {watch.enabled && <p className="shopper-muted">Volgende controle: {date(watch.next_run)}</p>}
      <div className="shopper-actions"><button disabled={busy || !watch.enabled || watch.latest_run?.status === 'running'} onClick={() => void mutate('shopper-run', { watch_id: watch.id })}>Nu zoeken</button><button disabled={busy} onClick={() => void mutate('shopper-control', { watch_id: watch.id, enabled: !watch.enabled })}>{watch.enabled ? 'Pauzeren' : 'Hervatten'}</button></div>
      {!!watch.held_contacts && <p>Reserveoptie: {watch.held_contacts} gesprek op pauze. Leon reageert daar niet automatisch op.</p>}
      {!!watch.fallback_after && <p>Tot {date(watch.fallback_after)} zoeken naar {watch.min_ram_gb} GB. Daarna mag {watch.fallback_min_ram_gb} GB als reserveoptie meewegen.</p>}
      {watch.replies?.map(reply => <p key={reply.conversation_url + reply.due_at}>{reply.status === 'ready_for_owner' ? 'Aanbod klaar om zelf te beoordelen en te kopen' : reply.status === 'pending' ? `Reactie gepland: ${date(reply.due_at)}` : reply.status === 'attempted' || reply.status === 'unknown' ? 'Verzendstatus onzeker; Leon stuurt niet opnieuw' : reply.status === 'clicked' ? 'Reactie verstuurd; bezorging nog niet bevestigd' : 'Gesprek bijgewerkt'} · <a href={reply.conversation_url} target="_blank" rel="noreferrer">Bekijk gesprek</a></p>)}
      {watch.latest_run?.result?.reason && <p>{watch.latest_run.result.reason}</p>}
      {watch.latest_run?.result?.agent && <div className="shopper-connection"><strong>Leon shopper: {watch.latest_run.result.agent.status === 'confirmed' ? 'Bericht bevestigd' : watch.latest_run.result.agent.status === 'clicked' ? 'Verzenden aangeklikt, bevestiging ontbreekt' : watch.latest_run.result.agent.status === 'needs_owner' ? 'Koppeling vereist aandacht' : 'Wachten'}</strong><p>{watch.latest_run.result.agent.reason}</p>{watch.latest_run.result.agent.model && <small>M40 · {watch.latest_run.result.agent.model}</small>}{watch.latest_run.result.agent.conversation_url && <p><a href={watch.latest_run.result.agent.conversation_url} target="_blank" rel="noreferrer">Bekijk gesprek</a></p>}</div>}
      {watch.latest_run?.status === 'complete' && !watch.latest_run.result?.matches.length && <p>Geen passende aanbiedingen in deze zoekronde. De watch blijft actief.</p>}
      {watch.latest_run?.result?.matches.map(match => <article className="shopper-deal" key={match.url}><div><a href={match.url} target="_blank" rel="noreferrer">{match.title}</a><strong>{match.asking_price_cents === null ? 'Prijs navragen' : `${money(match.asking_price_cents)} vraagprijs`}</strong></div>{match.capacity_gb && <p>{match.capacity_gb} GB genoemd in de advertentie</p>}<ul>{match.notes.map(note => <li key={note}>{note}</li>)}</ul></article>)}
    </section>)}</div>
    <p className="shopper-muted">Prijzen zijn vraagprijzen. Verzendkosten, setomvang en compatibiliteit moeten bevestigd zijn voordat je koopt. Aankopen worden niet automatisch uitgevoerd.</p>
  </main>;
}
