'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Brain, Check, Database, Link2, LockKeyhole, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { buildMemoryCreatePayload, normalizeMemorySearchResponse, type MemoryListItem } from './memory-contract';
import './connected-work.css';

type Edge = { id?: string; source_memory_id?: string; subject?: string; predicate?: string; object?: string };
type Payload = { error?: string; items?: MemoryListItem[]; graph_edges?: Edge[]; id?: string; ok?: boolean; retrieval?: unknown };
type Api = (resource: string, body?: unknown, signal?: AbortSignal) => Promise<Payload>;

async function request(token: string, resource: string, body?: unknown, signal?: AbortSignal) {
  const response = await fetch(`/api/leon?resource=${encodeURIComponent(resource)}`, { method: body === undefined ? 'GET' : 'POST', signal, cache: 'no-store', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const data = await response.json() as Payload;
  if (!response.ok) throw new Error(data.error || 'Geheugenverzoek mislukt.');
  return data;
}

function label(item: MemoryListItem) { return item.content?.trim() || 'Zonder tekst'; }
function message(reason: unknown, fallback: string) { return reason instanceof Error ? reason.message : fallback; }

export default function ConnectedMemory() {
  const token = 'session';
  const [items, setItems] = useState<MemoryListItem[]>([]);
  const [snapshotItems, setSnapshotItems] = useState<MemoryListItem[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState({ content: '', source: '', confidence: '0.7', review_note: '' });
  const [editMode, setEditMode] = useState<'correct' | 'delete' | null>(null);
  const [correction, setCorrection] = useState('');
  const [deleteReason, setDeleteReason] = useState('');
  const controller = useRef<AbortController | null>(null);
  const selected = items.find(item => item.id === selectedId) ?? items[0];
  const canonicalSelected = selected ? snapshotItems.find(item => item.id === selected.id) : undefined;
  const displayedSelected = selected?.kind === 'memory' && canonicalSelected ? canonicalSelected : selected;
  const canEditSelected = Boolean(selected && selected.kind !== 'source_record' && (selected.kind !== 'memory' || canonicalSelected));
  function api(activeToken: string): Api { return (resource, body, signal) => request(activeToken, resource, body, signal); }
  const refresh = useCallback(async (activeToken = 'session'): Promise<string | null> => {
    controller.current?.abort(); setSearching(false); const next = new AbortController(); controller.current = next;
    try { const data = await request(activeToken, 'memory', undefined, next.signal); if (next.signal.aborted) return null; if (!Array.isArray(data.items)) throw new Error('Onverwacht geheugenantwoord.'); setItems(data.items); setSnapshotItems(data.items); setEdges(Array.isArray(data.graph_edges) ? data.graph_edges : []); setSelectedId(current => data.items!.some(item => item.id === current) ? current : data.items![0]?.id || ''); setQuery(''); setError(''); return null; }
    catch (reason) { if (next.signal.aborted) return null; const detail = message(reason, 'Geheugen niet bereikbaar.'); setError(detail); return detail; }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void refresh(), 0); return () => { window.clearTimeout(timer); controller.current?.abort(); }; }, [refresh]);
  async function run(action: () => Promise<void>, success: string): Promise<boolean> {
    controller.current?.abort(); setSearching(false); setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (reason) { setError(message(reason, 'Actie niet bevestigd.')); setBusy(false); return false; }
    const refreshError = await refresh();
    setError('');
    setNotice(refreshError ? `${success} De lijst kon daarna niet worden vernieuwd. Dien dezelfde wijziging niet opnieuw in; ververs eerst de lijst.` : success);
    setBusy(false);
    return true;
  }
  async function search() {
    controller.current?.abort(); const next = new AbortController(); controller.current = next;
    setSearching(true); setError(''); setEditMode(null);
    try { const data = await api(token)('memory-search', { query: query.trim(), scope: 'context', limit: 10 }, next.signal); if (next.signal.aborted || controller.current !== next) return; const results = normalizeMemorySearchResponse(data); setItems(results); setEdges([]); setSelectedId(results[0]?.id || ''); }
    catch (reason) { if (!next.signal.aborted && controller.current === next) setError(message(reason, 'Zoeken mislukt.')); }
    finally { if (controller.current === next) setSearching(false); }
  }
  async function submitCorrection() {
    if (!selected || !correction.trim()) return;
    const confirmed = await run(async () => { const data = await api(token)('memory-update', { id: selected.id, content: correction.trim(), review_note: 'Corrected by user from Gaia memory' }); if (!data.ok) throw new Error('Correctie niet bevestigd.'); }, 'Geheugen gecorrigeerd.');
    if (confirmed) { setEditMode(null); setCorrection(''); }
  }
  async function submitDelete() {
    if (!selected || !deleteReason.trim()) return;
    const confirmed = await run(async () => { const data = await api(token)('memory-delete', { id: selected.id, reason: deleteReason.trim() }); if (!data.ok) throw new Error('Verwijdering niet bevestigd.'); }, 'Geheugen verwijderd.');
    if (confirmed) { setEditMode(null); setDeleteReason(''); }
  }
  const related = useMemo(() => edges.filter(edge => edge.source_memory_id === selected?.id), [edges, selected?.id]);
  return <>
    <div className="space-view work-view connected-memory">
      <header className="work-header"><div><h1>Levend geheugen.</h1><p>Opgeslagen context met bron, vertrouwen en controle over wat Gaia mag onthouden.</p></div><div className="work-actions">{token && <button className="secondary-control" type="button" onClick={() => void refresh()} disabled={busy}><RefreshCw size={15}/> Ververs</button>}</div></header>
      {error && <p className="work-error" role="alert">{error}</p>}{notice && <p className="work-hint" role="status">{notice}</p>}
      {token && <div className="memory-layout"><section className="memory-list-panel"><form className="memory-search" onSubmit={event => { event.preventDefault(); void search(); }}><Search size={16}/><input aria-label="Zoek in geheugen" placeholder="Zoek opgeslagen context" value={query} onChange={event => setQuery(event.target.value)} required/><button type="submit" disabled={searching}>{searching ? 'Zoeken…' : 'Zoek'}</button></form><div className="memory-list" aria-label="Opgeslagen geheugen">{items.map(item => <button type="button" className="memory-list-item" data-selected={item.id === selected?.id || undefined} key={`${item.kind || 'memory'}-${item.id}`} onClick={() => { setSelectedId(item.id); setEditMode(null); }}><span className="memory-list-icon"><Brain size={15}/></span><span><strong>{label(item)}</strong><small>{item.memory_type || 'context'} · {Math.round((item.confidence ?? 0) * 100)}% vertrouwen</small></span></button>)}{!items.length && <p className="work-hint">{query ? 'Geen passende zoekresultaten gevonden.' : 'Nog geen opgeslagen geheugen. Voeg hieronder het eerste stukje context toe.'}</p>}</div><form className="memory-create" onSubmit={event => { event.preventDefault(); void run(async () => { const data = await api(token)('memory-create', buildMemoryCreatePayload(form)); if (!data.ok || !data.id) throw new Error('Geheugenaanmaak niet bevestigd.'); setForm({ content: '', source: '', confidence: '0.7', review_note: '' }); }, 'Geheugen opgeslagen en klaar voor controle.'); }}><div className="sidebar-heading"><span><Plus size={16}/> Nieuw geheugen</span></div><label htmlFor="memory-content">Wat moet Gaia onthouden?</label><textarea id="memory-content" required value={form.content} onChange={event => setForm({ ...form, content: event.target.value })}/><div className="memory-form-grid"><label htmlFor="memory-source">Bron<input id="memory-source" required value={form.source} onChange={event => setForm({ ...form, source: event.target.value })}/></label><label htmlFor="memory-confidence">Vertrouwen<input id="memory-confidence" type="number" min="0" max="1" step="0.05" value={form.confidence} onChange={event => setForm({ ...form, confidence: event.target.value })}/></label></div><button className="trace-action" type="submit" disabled={busy}><Plus size={15}/> Opslaan</button></form></section>
      <aside className="memory-inspector connected-memory-inspector" aria-label="Geheugendetail">{displayedSelected ? <><div className="inspector-topline"><span className="memory-type"><Database size={14}/> {displayedSelected.memory_type || 'context'}</span><span>{displayedSelected.status || 'active'}</span></div><h2>{label(displayedSelected)}</h2><p>{displayedSelected.review_note || 'Gaia gebruikt dit wanneer het je huidige taak duidelijk beter maakt.'}</p><dl className="memory-meta"><div><dt>Bron</dt><dd>{displayedSelected.source || 'Onbekend'}</dd></div><div><dt>Vertrouwen</dt><dd>{Math.round((displayedSelected.confidence ?? 0) * 100)}%</dd></div><div><dt>ID</dt><dd>{displayedSelected.id}</dd></div></dl>{related.length > 0 && <div className="memory-related"><strong><Link2 size={14}/> Verbindingen</strong>{related.map((edge, index) => <span key={edge.id || index}>{edge.subject || 'Geheugen'} → {edge.predicate || 'gerelateerd aan'} → {edge.object || 'onbekend'}</span>)}</div>}{canEditSelected && editMode === null && <div className="memory-inspector-actions"><button className="secondary-control" type="button" disabled={busy} onClick={() => { setCorrection(displayedSelected.content || ''); setEditMode('correct'); }}><Check size={15}/> Corrigeer</button><button className="secondary-control danger-control" type="button" disabled={busy} onClick={() => { setDeleteReason(''); setEditMode('delete'); }}><Trash2 size={15}/> Verwijder</button></div>}{selected?.kind === 'memory' && !canonicalSelected && <p className="work-hint">Dit zoekresultaat toont een samenvatting en kan hier niet veilig worden gewijzigd.</p>}{editMode === 'correct' && <form className="memory-create" onSubmit={event => { event.preventDefault(); void submitCorrection(); }}><label htmlFor="memory-correction">Gecorrigeerde geheugentekst</label><textarea id="memory-correction" required value={correction} onChange={event => setCorrection(event.target.value)}/><div className="memory-inspector-actions"><button className="trace-action" type="submit" disabled={busy}><Check size={15}/> Correctie opslaan</button><button className="secondary-control" type="button" disabled={busy} onClick={() => setEditMode(null)}>Annuleer</button></div></form>}{editMode === 'delete' && <form className="memory-create" onSubmit={event => { event.preventDefault(); void submitDelete(); }}><label htmlFor="memory-delete-reason">Reden voor verwijderen</label><textarea id="memory-delete-reason" required value={deleteReason} onChange={event => setDeleteReason(event.target.value)}/><div className="memory-inspector-actions"><button className="secondary-control danger-control" type="submit" disabled={busy}><Trash2 size={15}/> Definitief verwijderen</button><button className="secondary-control" type="button" disabled={busy} onClick={() => setEditMode(null)}>Annuleer</button></div></form>}{canEditSelected && <p className="memory-privacy"><LockKeyhole size={14}/> Verwijderen vraagt altijd om een reden.</p>}</> : <div className="memory-empty"><Brain size={24}/><h2>Geen geheugen geselecteerd</h2><p>{token ? 'Kies een item of zoek opnieuw.' : 'Verbind met Leon om opgeslagen context te laden.'}</p></div>}</aside></div>}
    </div>
  </>;
}
