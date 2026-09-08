'use client';

import { useRef, useState } from 'react';
import { LockKeyhole } from 'lucide-react';
import { readPending, recoverModel, submitModel, usdToMicrousd } from '../../lib/model-submission';
import type { ModelDraft, ModelPreview, ModelRequest } from '../../lib/model-submission';

export default function ModelRequestForm({ taskId, disabled, request, onQueued }: {
  taskId: string; disabled: boolean; request: ModelRequest; onQueued: (id: string) => Promise<void>;
}) {
  const [prompt, setPrompt] = useState('');
  const [limit, setLimit] = useState('0.01');
  const [review, setReview] = useState<{ draft: ModelDraft; quote: ModelPreview } | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const version = useRef(0);
  const locked = useRef(false);
  const bytes = new TextEncoder().encode(prompt).length;
  function invalidate() { version.current++; setReview(null); setApproved(false); setMessage(''); }
  function draft(): ModelDraft {
    return { task_id: taskId, prompt, max_output_tokens: 512, max_cost_microusd: usdToMicrousd(limit) };
  }
  async function act(action: () => Promise<void>) {
    if (locked.current || disabled) return;
    locked.current = true; setBusy(true); setMessage('');
    try { await action(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Actie niet bevestigd. Controleer de aanvraag.'); }
    finally { locked.current = false; setBusy(false); }
  }
  return <section className="model-request-panel">
    <div className="sidebar-heading"><span><LockKeyhole size={16} /> Korte AI-opdracht</span></div>
    <p>Alleen deze tekst gaat na jouw goedkeuring naar OpenAI. Geen bestanden, geheugen of tools. Preview is lokaal en kost niets.</p>
    <label className="work-field">Tekst voor OpenAI<textarea rows={4} value={prompt} disabled={busy}
      onChange={event => { invalidate(); setPrompt(event.target.value); }} placeholder="Bijvoorbeeld: vat deze korte tekst samen…" /></label>
    <p>{bytes}/4096 bytes · maximaal 512 outputtokens, inclusief reasoning</p>
    <label className="work-field">Maximum per aanvraag (USD)<input inputMode="decimal" value={limit} disabled={busy}
      onChange={event => { invalidate(); setLimit(event.target.value); }} /></label>
    <button type="button" className="trace-action" disabled={disabled || busy || !taskId || bytes === 0 || bytes > 4096}
      onClick={() => void act(async () => {
        const snapshot = draft(), revision = version.current;
        const result = await request('model-preview', { prompt: snapshot.prompt, max_output_tokens: snapshot.max_output_tokens, max_cost_microusd: snapshot.max_cost_microusd });
        if (!result.preview || result.preview.execution_allowed !== false || result.preview.provider_calls_made !== false) throw new Error('Onverwachte preview; niets goedgekeurd.');
        if (revision === version.current) { setReview({ draft: snapshot, quote: result.preview }); setApproved(false); }
      })}>Bekijk tekst en kosten</button>
    {review && <div className="model-review" aria-label="Modelaanvraag beoordelen">
      <strong>{review.quote.model}</strong>
      <blockquote>{review.draft.prompt}</blockquote>
      <p>Reservering: ${(review.quote.reserved_microusd / 1e6).toFixed(6)}. Jouw plafond: ${(review.draft.max_cost_microusd / 1e6).toFixed(6)} USD. Verbruik wordt conservatief omgerekend; geen factuurgarantie.</p>
      <label className="model-approval"><input type="checkbox" checked={approved} disabled={busy}
        onChange={event => setApproved(event.target.checked)} />Ik keur het versturen van deze tekst en dit kostenplafond goed.</label>
      <button type="button" className="trace-action" disabled={disabled || busy || !approved || !taskId}
        onClick={() => void act(async () => {
          const job = await submitModel(draft(), review.draft, approved, sessionStorage, request);
          setReview(null); setApproved(false); setPrompt('');
          setMessage('Aanvraag opgeslagen. De worker moet apart zijn ingeschakeld met dag- en totaalbudget.');
          await onQueued(job.id);
        })}>Goedkeuren en in wachtrij zetten</button>
    </div>}
    <button type="button" className="trace-action" disabled={disabled || busy}
      onClick={() => void act(async () => {
        if (!readPending(sessionStorage)) { setMessage('Geen onbevestigde verzending in dit browsertabblad.'); return; }
        const job = await recoverModel(sessionStorage, request);
        if (job) { setMessage('Eerdere aanvraag teruggevonden; niet opnieuw verstuurd.'); await onQueued(job.id); }
        else setMessage('Nog niet teruggevonden. Bij opnieuw proberen blijft dezelfde aanvraag-id behouden; er wordt nu niets verstuurd.');
      })}>Controleer vorige verzending</button>
    {message && <p className="work-error" role="status">{message}</p>}
    <p>Alleen de aanvraag-id blijft tijdelijk in dit browsertabblad bewaard voor herstel. De knop schakelt OpenAI niet in en verhoogt geen dag- of totaalbudget.</p>
  </section>;
}
