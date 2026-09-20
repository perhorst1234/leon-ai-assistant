'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ArrowUp, Check, ChevronDown, MessageCircle, Plus, RefreshCw, ShieldCheck, X } from 'lucide-react';
import { previewStillMatches } from './chat-preview';
import './connected-work.css';

type ChatRequest = { id: number; content: string };
type Conversation = { id: string; title?: string | null; created_at?: number; updated_at?: number; revision?: number; messages?: ChatMessage[] };
type ChatMessage = {
  id: string; role: 'user' | 'assistant'; content: string; status?: 'pending' | 'complete' | 'error' | 'unknown';
  request_id?: string | null; error?: string | null; created_at?: number;
};
type Preview = {
  prompt: string; prompt_sha256: string; conversation_revision: number; included_messages: number | Array<unknown>;
  model: string; reserved_microusd: number; max_cost_microusd: number; execution_allowed?: false; provider_calls_made?: false;
};
type PendingRequest = {
  conversation_id: string; request_id: string; content: string; max_output_tokens: number;
  max_cost_microusd: number; preview_sha256: string;
};
type ApiPayload = {
  error?: string; conversation?: Conversation; conversations?: Conversation[]; messages?: ChatMessage[];
  next_before?: string | null; message?: ChatMessage; job?: { id: string } | null; preview?: Preview;
};

const pendingKey = 'leon.chat.pending-request.v1';
const outputTokens = 512;
const maxCostMicrousd = 10_000;

type ChatApi = (resource: string, body?: unknown, id?: string, query?: Record<string, string>) => Promise<ApiPayload>;

async function requestChat(token: string, resource: string, body?: unknown, id?: string, query?: Record<string, string>) {
  const params = new URLSearchParams({ resource });
  if (id) params.set('id', id);
  for (const [key, value] of Object.entries(query ?? {})) params.set(key, value);
  const response = await fetch(`/api/leon?${params}`, {
    method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json() as ApiPayload;
  if (!data || typeof data !== 'object') throw new Error('Onverwacht antwoord van de backend.');
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Chatverzoek mislukt.');
  return data;
}

function readPending(): PendingRequest | null {
  try {
    const raw = window.sessionStorage.getItem(pendingKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PendingRequest>;
    if (!parsed || typeof parsed !== 'object' || typeof parsed.conversation_id !== 'string' || typeof parsed.request_id !== 'string'
      || typeof parsed.content !== 'string' || typeof parsed.preview_sha256 !== 'string') throw new Error('Ongeldige bewaarde chat-aanvraag.');
    return { conversation_id: parsed.conversation_id, request_id: parsed.request_id, content: parsed.content,
      max_output_tokens: parsed.max_output_tokens ?? outputTokens, max_cost_microusd: parsed.max_cost_microusd ?? maxCostMicrousd,
      preview_sha256: parsed.preview_sha256 };
  } catch (error) {
    throw error instanceof Error ? error : new Error('Ongeldige bewaarde chat-aanvraag.');
  }
}

function writePending(value: PendingRequest) { window.sessionStorage.setItem(pendingKey, JSON.stringify(value)); }
function clearPending() { window.sessionStorage.removeItem(pendingKey); }

function messageStatus(message: ChatMessage) {
  if (message.role === 'user') return '';
  if (message.status === 'pending') return 'Gaia verwerkt dit…';
  if (message.status === 'error') return message.error || 'Antwoord kon niet worden bevestigd.';
  if (message.status === 'unknown') return 'Uitkomst onzeker. Controleer het opgeslagen werk.';
  return '';
}

function titleFor(conversation: Conversation) { return conversation.title?.trim() || 'Nieuw gesprek'; }
function includedCount(value: Preview['included_messages']) { return typeof value === 'number' ? value : value.length; }
export default function ConnectedChat({
  demo, request, draft, onDraftChange, onSubmitRequest, onClearDraft, onModeChange,
}: {
  demo: ReactNode; request: ChatRequest | null; draft: string; onDraftChange: (value: string) => void;
  onSubmitRequest: (value: string) => void; onClearDraft: () => void; onModeChange: (demo: boolean) => void;
}) {
  const [showDemo, setShowDemo] = useState(false);
  const [tokenDraft, setTokenDraft] = useState('');
  const [token, setToken] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [review, setReview] = useState<{ content: string; conversationId: string; preview: Preview } | null>(null);
  const [approved, setApproved] = useState(false);
  const [pending, setPending] = useState<PendingRequest | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const lastRequest = useRef<number | null>(null);
  const selectedRef = useRef('');
  const conversationLoadVersion = useRef(0);
  const previewVersion = useRef(0);
  const reviewRef = useRef<typeof review>(null);
  useEffect(() => { reviewRef.current = review; }, [review]);

  const api = useCallback<ChatApi>((resource, body, id, query) => requestChat(token, resource, body, id, query), [token]);

  const loadConversation = useCallback(async (id: string) => {
    if (!id) return [] as ChatMessage[];
    const version = ++conversationLoadVersion.current;
    const switchingConversation = Boolean(selectedRef.current && selectedRef.current !== id);
    setSelectedId(id);
    selectedRef.current = id;
    if (switchingConversation) { setReview(null); setApproved(false); }
    const result = await api('chat-conversation', undefined, id);
    if (version !== conversationLoadVersion.current || selectedRef.current !== id) return [] as ChatMessage[];
    const loadedMessages = result.conversation?.messages ?? [];
    setMessages(loadedMessages);
    const activeReview = reviewRef.current;
    if (activeReview && (activeReview.conversationId !== id
      || activeReview.preview.conversation_revision !== result.conversation?.revision
      || !previewStillMatches(activeReview.preview, loadedMessages))) {
      setReview(null); setApproved(false);
    }
    const stored = readPending();
    if (stored?.conversation_id === id) {
      const matched = loadedMessages.some(message => message.request_id === stored.request_id);
      if (matched) { clearPending(); setPending(null); setNotice('Eerdere verzending teruggevonden; niets opnieuw verstuurd.'); }
      else setPending(stored);
    } else setPending(null);
    return loadedMessages;
  }, [api]);

  const refreshConversations = useCallback(async (before?: string) => {
    const result = await api('chat-conversations', undefined, undefined, before ? { before, limit: '25' } : { limit: '25' });
    if (!Array.isArray(result.conversations)) throw new Error('Onverwachte gesprekkenlijst van de backend.');
    if (before) setConversations(current => [...current, ...result.conversations!]);
    else setConversations(result.conversations);
    setNextBefore(result.next_before ?? null);
    setConnected(true); setError('');
    if (!selectedRef.current && result.conversations[0]) await loadConversation(result.conversations[0].id);
  }, [api, loadConversation]);

  const connect = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = tokenDraft.trim();
    if (!value) return;
    setBusy(true); setError('');
    try { setToken(value); await requestChat(value, 'chat-conversations', undefined, undefined, { limit: '25' }); }
    catch (reason) { setToken(''); setError(reason instanceof Error ? reason.message : 'Verbinding mislukt.'); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (!token || showDemo) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        await refreshConversations();
        if (selectedRef.current) await loadConversation(selectedRef.current);
      } catch (reason) {
        if (!stopped) { setConnected(false); setError(reason instanceof Error ? reason.message : 'Verbinding onderbroken.'); }
      }
      if (!stopped) timer = setTimeout(poll, 3500);
    };
    void poll();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [loadConversation, refreshConversations, showDemo, token]);

  const ensureConversation = useCallback(async () => {
    if (selectedRef.current) return selectedRef.current;
    const id = crypto.randomUUID();
    const result = await api('chat-conversations', { request_id: id, title: 'Nieuw gesprek' });
    if (!result.conversation?.id) throw new Error('Nieuw gesprek is niet bevestigd.');
    const conversation = result.conversation;
    setConversations(current => [conversation, ...current]);
    await loadConversation(conversation.id);
    return conversation.id;
  }, [api, loadConversation]);

  const previewDraft = useCallback(async (content: string) => {
    if (!content.trim()) return;
    const version = ++previewVersion.current;
    if (new TextEncoder().encode(content).length > 2048) { setError('Gebruik maximaal 2048 bytes tekst.'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      const conversationId = await ensureConversation();
      const result = await api('chat-preview', { conversation_id: conversationId, content, max_output_tokens: outputTokens, max_cost_microusd: maxCostMicrousd });
      if (!result.preview || result.preview.execution_allowed !== false || result.preview.provider_calls_made !== false) throw new Error('Onverwachte preview; niets goedgekeurd.');
      if (version !== previewVersion.current || selectedRef.current !== conversationId) return;
      setReview({ content, conversationId, preview: result.preview }); setApproved(false);
    } catch (reason) {
      if (version === previewVersion.current) setError(reason instanceof Error ? reason.message : 'Preview niet bevestigd.');
    } finally {
      if (version === previewVersion.current) setBusy(false);
    }
  }, [api, ensureConversation]);

  useEffect(() => {
    if (!request || lastRequest.current === request.id) return;
    lastRequest.current = request.id;
    if (!showDemo && token) window.setTimeout(() => void previewDraft(request.content), 0);
  }, [previewDraft, request, showDemo, token]);

  const submitApproved = async () => {
    if (!review || review.content !== draft || !approved || busy) return;
    const matchingPending = pending && pending.conversation_id === review.conversationId && pending.content === review.content ? pending : null;
    const requestId = matchingPending?.request_id ?? crypto.randomUUID();
    const stored: PendingRequest = { conversation_id: review.conversationId, request_id: requestId, content: review.content,
      max_output_tokens: outputTokens, max_cost_microusd: review.preview.max_cost_microusd, preview_sha256: review.preview.prompt_sha256 };
    setBusy(true); setError(''); setNotice(''); writePending(stored); setPending(stored);
    try {
      const result = await api('chat-messages', {
        request_id: requestId, content: review.content, max_output_tokens: outputTokens,
        max_cost_microusd: review.preview.max_cost_microusd, preview_sha256: review.preview.prompt_sha256, approve_external_text: true,
      }, review.conversationId);
      if (!result.message || result.message.request_id !== requestId) throw new Error('Verzending niet bevestigd; bewaar dezelfde aanvraag-id voor herstel.');
      clearPending(); setPending(null); setReview(null); setApproved(false); onClearDraft();
      setNotice('Bericht opgeslagen. Het antwoord verschijnt zodra de worker klaar is.');
      await loadConversation(review.conversationId);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Verzending onzeker; controleer dezelfde aanvraag opnieuw.'); }
    finally { setBusy(false); }
  };

  const recoverPending = async () => {
    const stored = readPending();
    if (!stored) { setNotice('Geen onbevestigde chatverzending in dit browsertabblad.'); return; }
    setBusy(true); setError('');
    try {
      const loadedMessages = await loadConversation(stored.conversation_id);
      const found = loadedMessages.some(message => message.request_id === stored.request_id);
      if (found) { clearPending(); setPending(null); setNotice('Eerdere verzending teruggevonden; niets opnieuw verstuurd.'); }
      else { setPending(stored); setNotice('Nog niet bevestigd. Dezelfde aanvraag-id blijft bewaard; er is niets opnieuw verstuurd.'); }
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Herstelcontrole mislukt.'); }
    finally { setBusy(false); }
  };

  const retryPending = async () => {
    if (!pending || busy) return;
    setBusy(true); setError('');
    try {
      const result = await api('chat-messages', {
        request_id: pending.request_id, content: pending.content, max_output_tokens: pending.max_output_tokens,
        max_cost_microusd: pending.max_cost_microusd, preview_sha256: pending.preview_sha256, approve_external_text: true,
      }, pending.conversation_id);
      if (!result.message || result.message.request_id !== pending.request_id) throw new Error('Aanvraag-id niet bevestigd.');
      clearPending(); setPending(null); setNotice('Dezelfde aanvraag-id is opnieuw gecontroleerd; geen dubbele boodschap aangemaakt.');
      await loadConversation(pending.conversation_id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Herstelverzending is niet bevestigd.'); }
    finally { setBusy(false); }
  };

  const current = useMemo(() => conversations.find(item => item.id === selectedId), [conversations, selectedId]);
  const hasConversation = Boolean(selectedId);
  const activeReview = review && review.content === draft ? review : null;
  const updateDraft = (value: string) => {
    if (value !== draft) ++previewVersion.current;
    if (review && value !== review.content) { setReview(null); setApproved(false); setNotice('De tekst is gewijzigd; bekijk de tekst en kosten opnieuw.'); }
    onDraftChange(value);
  };

  if (showDemo) return <>
    <div className="work-mode-switch" aria-label="Chatmodus">
      <button type="button" aria-pressed={false} onClick={() => { setShowDemo(false); onModeChange(false); }}>Verbonden chat</button>
      <button type="button" aria-pressed>Ontwerpvoorbeeld</button>
    </div>
    <span className="work-demo-label">Voorbeelddata — geen echte modelaanvraag</span>
    {demo}
  </>;

  return <>
    <div className="work-mode-switch" aria-label="Chatmodus">
      <button type="button" aria-pressed>Verbonden chat</button>
      <button type="button" aria-pressed={false} onClick={() => { setShowDemo(true); onModeChange(true); }}>Ontwerpvoorbeeld</button>
    </div>
    <div className="space-view chat-view connected-chat">
      <div className="chat-workspace">
        <aside className="chat-conversation-list" aria-label="Opgeslagen gesprekken">
          <div className="chat-list-heading"><span><MessageCircle size={16} /> Gesprekken</span><button type="button" aria-label="Nieuw gesprek" disabled={!connected || busy} onClick={() => { selectedRef.current = ''; setSelectedId(''); setMessages([]); }}><Plus size={16} /></button></div>
          {!token && <p className="chat-muted">Verbind met Leon om je gesprekken te laden.</p>}
          {conversations.map(conversation => <button type="button" className="chat-conversation-item" data-selected={conversation.id === selectedId || undefined} key={conversation.id} onClick={() => void loadConversation(conversation.id)}>{titleFor(conversation)}<small>{conversation.updated_at ? new Date(conversation.updated_at * 1000).toLocaleString('nl-NL') : 'Opgeslagen gesprek'}</small></button>)}
          {nextBefore && <button type="button" className="chat-more" disabled={busy} onClick={() => void refreshConversations(nextBefore)}>Laad oudere gesprekken <ChevronDown size={14} /></button>}
          {connected && !conversations.length && <p className="chat-muted">Nog geen opgeslagen gesprekken. Verstuur een gedachte om te beginnen.</p>}
        </aside>
        <section className="chat-panel" aria-label="Gesprek met Gaia">
          <header className="chat-panel-heading"><div><span className="view-icon"><MessageCircle size={17} /></span><div><h1>{current ? titleFor(current) : 'Gesprek'}</h1><p>{connected ? 'Context blijft opgeslagen bij Leon.' : 'Verbind om echte gesprekken te laden.'}</p></div></div><button type="button" className="chat-refresh" disabled={!token || busy} onClick={() => void refreshConversations()} aria-label="Gesprekken verversen"><RefreshCw size={16} /></button></header>
          {!token && <form className="work-connect chat-connect" onSubmit={connect}><label htmlFor="chat-token">Leon-dashboardtoken</label><input id="chat-token" type="password" autoComplete="off" value={tokenDraft} onChange={event => setTokenDraft(event.target.value)} required /><button className="pause-control" type="submit" disabled={busy}><ShieldCheck size={15} /> Verbind</button><p>Gebruik je Leon-dashboardtoken. Het blijft alleen in het geheugen van deze weergave.</p></form>}
          {error && <p className="work-error" role="alert">{error}</p>}
          {notice && <p className="chat-notice" role="status"><Check size={14} /> {notice}</p>}
          {token && <div className="chat-connection"><span className={connected ? 'chat-online' : 'chat-offline'} />{connected ? 'Verbonden met Leon' : 'Status wordt gecontroleerd'}<button type="button" onClick={() => { setToken(''); setTokenDraft(''); setConnected(false); setConversations([]); setMessages([]); setSelectedId(''); selectedRef.current = ''; }}>Verbreek</button></div>}
          <div className="chat-messages" aria-live="polite">
            {!messages.length && hasConversation && <p className="chat-empty">Dit gesprek is nog leeg. Schrijf onderaan wat je wilt onderzoeken.</p>}
            {!hasConversation && connected && <p className="chat-empty">Kies een gesprek of begin onderaan met een nieuwe gedachte.</p>}
            {messages.map(message => <article className={`chat-message chat-message-${message.role}`} key={message.id}><span className="chat-message-label">{message.role === 'user' ? 'Per' : 'Gaia'}</span><p>{message.content}</p>{messageStatus(message) && <small className={message.status === 'error' || message.status === 'unknown' ? 'chat-message-warning' : ''}>{messageStatus(message)}</small>}</article>)}
          </div>
          {activeReview && <section className="chat-review" aria-label="Tekst en kosten goedkeuren"><div className="chat-review-heading"><span><ShieldCheck size={16} /> Tekst en context controleren</span><button type="button" aria-label="Preview sluiten" onClick={() => { setReview(null); setApproved(false); }}><X size={15} /></button></div><p className="chat-review-meta">{activeReview.preview.model} · {includedCount(activeReview.preview.included_messages)} eerdere berichten · revisie {activeReview.preview.conversation_revision}</p><blockquote>{activeReview.preview.prompt}</blockquote><p>Reservering: ${(activeReview.preview.reserved_microusd / 1e6).toFixed(6)} USD. Er is nog niets naar een model verstuurd.</p><label className="model-approval"><input type="checkbox" checked={approved} disabled={busy} onChange={event => setApproved(event.target.checked)} />Ik keur precies deze tekst, context en kostenlimiet goed.</label><button type="button" className="trace-action" disabled={!approved || busy} onClick={() => void submitApproved()}>Goedkeuren en in wachtrij zetten</button></section>}
          {pending?.conversation_id === selectedId && <section className="chat-pending" aria-label="Onzekere verzending"><strong>Verzending nog niet bevestigd</strong><p>Gaia maakt geen nieuwe aanvraag. Controleer dezelfde aanvraag-id of probeer exact die id opnieuw.</p><div><button type="button" className="secondary-control" disabled={busy} onClick={() => void recoverPending()}>Controleer status</button><button type="button" className="trace-action" disabled={busy} onClick={() => void retryPending()}>Herstel met dezelfde id</button></div></section>}
          <form className="chat-composer" onSubmit={event => { event.preventDefault(); if (draft.trim()) onSubmitRequest(draft); }}><label className="sr-only" htmlFor="connected-chat-prompt">Vraag Gaia iets</label><textarea id="connected-chat-prompt" rows={2} value={draft} onChange={event => updateDraft(event.target.value)} placeholder="Schrijf een gedachte voor Gaia…" disabled={busy} /><button type="submit" aria-label="Bekijk tekst en kosten" disabled={busy || !draft.trim()}><ArrowUp size={17} /></button></form>
          <p className="chat-footnote">Preview toont de exacte tekst en gesprekscontext. Goedkeuring staat nooit vooraf aan; wijzigen maakt de preview ongeldig.</p>
        </section>
      </div>
    </div>
  </>;
}

export type { ChatRequest };
