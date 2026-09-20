'use client';

import { useEffect, useRef, useState } from 'react';
import { CalendarDays, LockKeyhole, Mail, Search } from 'lucide-react';
import {
  GOOGLE_PREVIEW_LIMIT, GOOGLE_TIMEZONE, buildCalendarPreviewPayload, defaultCalendarDraft, formatGoogleDate,
  normalizeCalendarPreview, normalizeMailPreview, type CalendarPreviewItem, type GoogleStatus,
  type MailPreviewItem,
} from './google-contract';

type Payload = { error?: string } & Record<string, unknown>;

async function request(token: string, resource: string, body: unknown, signal: AbortSignal): Promise<Payload> {
  const response = await fetch(`/api/leon?resource=${encodeURIComponent(resource)}`, {
    method: 'POST', signal, cache: 'no-store', body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  const data = await response.json() as Payload;
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Google-voorbeeld niet bereikbaar.');
  return data;
}

export default function ConnectedGoogle({ token, status }: { token: string; status: GoogleStatus }) {
  const [calendarDraft, setCalendarDraft] = useState(() => defaultCalendarDraft());
  const [events, setEvents] = useState<CalendarPreviewItem[] | null>(null);
  const [mail, setMail] = useState<MailPreviewItem[] | null>(null);
  const [loading, setLoading] = useState<'calendar' | 'mail' | null>(null);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function preview(kind: 'calendar' | 'mail') {
    let body: unknown;
    try { body = kind === 'calendar' ? buildCalendarPreviewPayload(calendarDraft) : { limit: GOOGLE_PREVIEW_LIMIT }; }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Controleer de gekozen periode.'); return; }
    controller.current?.abort(); const next = new AbortController(); controller.current = next;
    setLoading(kind); setError('');
    if (kind === 'calendar') setEvents(null); else setMail(null);
    try {
      const data = await request(token, kind === 'calendar' ? 'google-calendar-preview' : 'google-mail-preview', body, next.signal);
      if (next.signal.aborted || controller.current !== next) return;
      if (kind === 'calendar') setEvents(normalizeCalendarPreview(data)); else setMail(normalizeMailPreview(data));
    } catch (reason) {
      if (!next.signal.aborted && controller.current === next) setError(reason instanceof Error ? reason.message : 'Google-voorbeeld niet bereikbaar.');
    } finally {
      if (controller.current === next) setLoading(null);
    }
  }

  const ready = status.enabled && status.configured;
  return <section className="google-preview" aria-label="Google privévoorbeelden">
    <header><div><span className="google-private"><LockKeyhole size={14}/> Privégegevens</span><h2>Google Agenda en Gmail</h2></div><span>{status.enabled ? status.configured ? 'Geconfigureerd' : 'Niet geconfigureerd' : 'Uitgeschakeld'}</span></header>
    <p>Gaia haalt alleen na jouw klik een klein leesvoorbeeld op. Deze voorbeelden worden niet opgeslagen.</p>
    <div className="google-scopes" aria-label="Google toegangsstatus"><span data-ready={status.scopes.calendar || undefined}>Agenda {status.scopes.calendar ? 'toegestaan' : 'geen toegang'}</span><span data-ready={status.scopes.mail || undefined}>Gmail {status.scopes.mail ? 'toegestaan' : 'geen toegang'}</span></div>
    {!status.enabled && <p className="work-hint">Google read-only staat uit op de Leon-server.</p>}
    {status.enabled && !status.configured && <p className="work-hint">Google is nog niet server-side geconfigureerd. Er worden hier geen Google-tokens gevraagd.</p>}
    {ready && <div className="google-preview-grid">
      <section>
        <div className="sidebar-heading"><span><CalendarDays size={16}/> Agenda</span><small>maximaal {GOOGLE_PREVIEW_LIMIT}</small></div>
        {status.scopes.calendar ? <form onSubmit={event => { event.preventDefault(); void preview('calendar'); }}>
          <label htmlFor="google-calendar-start">Vanaf<input id="google-calendar-start" name="google-calendar-start" type="datetime-local" required value={calendarDraft.start} onChange={event => setCalendarDraft({ ...calendarDraft, start: event.target.value })}/></label>
          <label htmlFor="google-calendar-end">Tot en met<input id="google-calendar-end" name="google-calendar-end" type="datetime-local" required value={calendarDraft.end} onChange={event => setCalendarDraft({ ...calendarDraft, end: event.target.value })}/></label>
          <small>Tijdzone: {GOOGLE_TIMEZONE} · maximaal zeven dagen</small>
          <button className="secondary-control" type="submit" disabled={loading !== null}><Search size={15}/> {loading === 'calendar' ? 'Agenda ophalen…' : 'Toon agenda'}</button>
        </form> : <p className="work-hint">De Agenda-scope ontbreekt.</p>}
        {events && <div className="google-result-list" aria-live="polite">{events.length ? events.map(item => <article key={item.id}><strong>{item.summary}</strong><span>{item.allDay ? `${formatGoogleDate(item.start, true)} · hele dag` : `${formatGoogleDate(item.start)} – ${formatGoogleDate(item.end)}`}</span><small>{item.sourceRef}</small></article>) : <p className="work-hint">Geen afspraken in deze periode.</p>}</div>}
      </section>
      <section>
        <div className="sidebar-heading"><span><Mail size={16}/> Gmail</span><small>maximaal {GOOGLE_PREVIEW_LIMIT}</small></div>
        {status.scopes.mail ? <button className="secondary-control" type="button" disabled={loading !== null} onClick={() => void preview('mail')}><Mail size={15}/> {loading === 'mail' ? 'Mail ophalen…' : 'Toon recente mail'}</button> : <p className="work-hint">De Gmail metadata-scope ontbreekt.</p>}
        {mail && <div className="google-result-list" aria-live="polite">{mail.length ? mail.map(item => <article key={item.id}><strong>{item.subject}</strong><span>Van: {item.from}</span><span>{item.date || 'Datum onbekend'}</span><small>{item.sourceRef}</small></article>) : <p className="work-hint">Geen recente mail gevonden.</p>}</div>}
      </section>
    </div>}
    {error && <p className="work-error" role="alert">{error}</p>}
  </section>;
}
