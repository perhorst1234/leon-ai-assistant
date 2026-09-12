'use client';
import { useEffect, useRef, useState } from 'react';
import { AUTONOMY_RUN_BODY, type AutonomyOverview } from '../../lib/autonomy-contract';
export const RUN_BODY = AUTONOMY_RUN_BODY;
export default function AutonomyCard({ overview, token, onRefresh }: { overview: AutonomyOverview; token?: string; onRefresh: () => Promise<void> | void }) {
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const mounted = useRef(true); const request = useRef<AbortController | null>(null); const requestId = useRef(0);
  useEffect(() => () => { mounted.current = false; request.current?.abort(); }, []);
  const start = async () => {
    if (!token?.trim() || busy) { if (mounted.current && !token?.trim()) setMessage('Verbind eerst met Leon.'); return; }
    request.current?.abort(); const controller = new AbortController(); request.current = controller; const id = ++requestId.current;
    setBusy(true); setMessage('');
    try {
      const response = await fetch('/api/leon?resource=autonomy-run', { method: 'POST', signal: controller.signal, cache: 'no-store', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token.trim()}` }, body: JSON.stringify(RUN_BODY) });
      const data = await response.json() as { error?: string };
      if (!response.ok) throw new Error(data.error || 'Nachtcyclus kon niet starten.');
      if (!mounted.current || controller.signal.aborted || request.current !== controller || requestId.current !== id) return;
      setMessage('Lokale broncontrole gestart.');
      await onRefresh();
    } catch (error) {
      if (controller.signal.aborted || !mounted.current || request.current !== controller || requestId.current !== id) return;
      setMessage(error instanceof Error ? error.message : 'Nachtcyclus kon niet starten.');
    } finally {
      if (mounted.current && request.current === controller && requestId.current === id) { request.current = null; setBusy(false); }
    }
  };
  const latest = overview.latest_run;
  const partial = overview.morning_brief?.partial_failure_disclosure;
  return <section className="autonomy-card" aria-label="Gaia autonomie"><div><p className="eyebrow">Lokale autonomie</p><h2>{latest ? `Laatste nachtcyclus: ${latest.status}` : 'Geen nachtcyclus uitgevoerd'}</h2><p>Alleen een veilige lokale broncontrole en voorbereiding voor vannacht. Geen provider-, netwerk-, geheugen-, taak- of cachewijzigingen.</p>{latest && <p>{latest.action_count} acties · {latest.failure_count} fouten · {latest.proposal_count} voorstellen · {latest.source_count} bronnen</p>}</div><button className="pause-control" type="button" onClick={() => void start()} disabled={busy || !token?.trim()}>{busy ? 'Starten…' : 'Start veilige bronscan'}</button>{message && <p role="status">{message}</p>}{overview.morning_brief && <div className="autonomy-brief"><strong>Ochtendbrief</strong>{partial?.visible_to_user && <>{partial.has_partial_failure && <p>{partial.failure_count} onderdeel{partial.failure_count === 1 ? '' : 'en'} konden niet volledig worden verwerkt{partial.status ? ` (${partial.status}).` : '.'}</p>}{partial.recovery_suggestions.map(suggestion => <p key={`${suggestion.action}:${suggestion.summary}`}>{suggestion.action}: {suggestion.summary}</p>)}</>}{overview.morning_brief.sections.map(section => <div key={section.id}><strong>{section.title}</strong><p>{section.summary}</p>{section.id === 'proposals' && section.items.length > 0 && <p>{section.items.length} voorstel(en) wachten op jouw beoordeling.</p>}{section.id === 'risks_and_attention' && section.items.length > 0 && <p>{section.items.length} aandachtspunt(en).</p>}</div>)}</div>}</section>;
}
