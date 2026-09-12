'use client';

import { useEffect, useRef, useState } from 'react';
import { Clock3, Globe2, LockKeyhole, Play, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { buildResearchFields, buildResearchRunBody, normalizeResearch, type ResearchData } from '../../lib/research-contract';
import './research-card.css';

type Props = { token: string };

function text(value: unknown, fallback = '') { return typeof value === 'string' ? value : fallback; }

async function request(path: string, token: string, body: unknown, signal: AbortSignal) {
  const response = await fetch(path, { method: 'POST', signal, cache: 'no-store', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json() as unknown;
  if (!response.ok) throw new Error(data && typeof data === 'object' && 'error' in data ? text((data as Record<string, unknown>).error, 'Researchverzoek mislukt.') : 'Researchverzoek mislukt.');
  return normalizeResearch(data);
}

export default function ResearchCard({ token }: Props) {
  const [query, setQuery] = useState('');
  const [domains, setDomains] = useState('');
  const [maxResults, setMaxResults] = useState(3);
  const [preview, setPreview] = useState<ResearchData | null>(null);
  const [run, setRun] = useState<ResearchData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);
  const fields = () => buildResearchFields(query, domains, maxResults);
  function invalidate() { requestVersion.current += 1; setPreview(null); setRun(null); setError(''); controller.current?.abort(); }
  useEffect(() => () => controller.current?.abort(), []);
  async function previewResearch() {
    const body = fields(); if (!body.query) return;
    controller.current?.abort(); const current = new AbortController(); controller.current = current; const version = ++requestVersion.current;
    setBusy(true); setError(''); setRun(null);
    try { const result = await request('/api/research/preview', token, body, current.signal); if (!current.signal.aborted && version === requestVersion.current) setPreview(result); }
    catch (reason) { if (!current.signal.aborted && version === requestVersion.current) setError(reason instanceof Error ? reason.message : 'Preview niet beschikbaar.'); }
    finally { if (!current.signal.aborted && version === requestVersion.current) setBusy(false); }
  }
  async function runResearch() {
    if (!preview?.previewFingerprint) return;
    controller.current?.abort(); const current = new AbortController(); controller.current = current; const version = ++requestVersion.current;
    setBusy(true); setError('');
    try { const result = await request('/api/research/run', token, buildResearchRunBody(fields(), preview), current.signal); if (!current.signal.aborted && version === requestVersion.current) setRun(result); }
    catch (reason) { if (!current.signal.aborted && version === requestVersion.current) setError(reason instanceof Error ? reason.message : 'Starten niet bevestigd.'); }
    finally { if (!current.signal.aborted && version === requestVersion.current) setBusy(false); }
  }
  const shown = run ?? preview;
  return <section className="research-card" aria-label="Read-only research">
    <header className="research-card-heading"><div><span className="research-private"><LockKeyhole size={14}/> Read-only</span><h2><Search size={18}/> Research</h2></div><span>{shown?.status ?? 'klaar voor preview'}</span></header>
    <p className="research-intro">Onderzoek bronnen met een begrensde, controleerbare stap. Start pas na het bekijken van de preview.</p>
    <label className="work-field">Vraag<input value={query} onChange={(event) => { setQuery(event.target.value); invalidate(); }} placeholder="Bijv. beste lokale researchtools" /></label>
    <label className="work-field">Alleen deze domeinen <input value={domains} onChange={(event) => { setDomains(event.target.value); invalidate(); }} placeholder="github.com, openai.com (optioneel)" /></label>
    <label className="work-field">Maximaal aantal bronnen<select value={maxResults} onChange={(event) => { setMaxResults(Number(event.target.value)); invalidate(); }}>{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
    <div className="research-actions"><button className="secondary-control" type="button" onClick={() => void previewResearch()} disabled={busy || !token || !query.trim()}><RefreshCw size={15}/> {busy && !preview ? 'Preview laden…' : 'Preview'}</button><button className="trace-action" type="button" onClick={() => void runResearch()} disabled={busy || !preview?.previewFingerprint || !preview.previewId || !preview.executionAllowed}><Play size={15}/> {busy && preview ? 'Starten…' : 'Start research'}</button></div>
    {!token && <p className="work-hint">Verbind eerst met Leon om Research te gebruiken.</p>}
    {error && <p className="work-error" role="alert">{error}</p>}
    {shown && <div className="research-result" aria-live="polite"><div className="research-meta"><span><Globe2 size={14}/> {shown.provider}</span><span><ShieldCheck size={14}/> risico: {shown.risk}</span>{shown.durationMs !== undefined && <span><Clock3 size={14}/> {shown.durationMs} ms</span>}</div>{shown.error && <p className="work-error">{shown.error}</p>}<strong>{run ? 'Resultaat bevestigd' : shown.executionAllowed ? 'Preview klaar' : 'Research nog niet beschikbaar'}</strong>{shown.sources.length ? <ol>{shown.sources.map((source) => <li key={`${source.url}-${source.title}`}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>{source.domain && <small>{source.domain}</small>}</li>)}</ol> : <p className="work-hint">{shown.status === 'waiting_for_secret' ? 'Firecrawl-key ontbreekt in serverconfiguratie.' : shown.status === 'disabled' ? 'Research staat uit in serverconfiguratie.' : 'Nog geen bronnen ontvangen.'}</p>}</div>}
  </section>;
}
