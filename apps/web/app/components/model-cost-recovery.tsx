'use client';
import { useRef, useState } from 'react';
import { approveReconciliation } from '../../lib/model-reconciliation';
import type { CostProposal, CostRequest } from '../../lib/model-reconciliation';

export default function ModelCostRecovery({ jobId, disabled, request, onSaved }: {
  jobId: string; disabled: boolean; request: CostRequest; onSaved: () => Promise<void>;
}) {
  const [proposal, setProposal] = useState<CostProposal | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const lock = useRef(false);
  async function act(action: () => Promise<void>) {
    if (disabled || lock.current) return;
    lock.current = true; setBusy(true); setMessage('');
    try { await action(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Herstel niet bevestigd.'); }
    finally { lock.current = false; setBusy(false); }
  }
  return <section className="model-request-panel model-cost-recovery" aria-label="Onzekere kosten controleren">
    <h3>Verbruik controleren</h3>
    <p>Het antwoord is niet bevestigd. Als Leon wél verbruik heeft ontvangen, kun je alleen de kosten afboeken. Zonder bewijs blijft de reservering staan.</p>
    <button type="button" className="trace-action" disabled={disabled || busy} onClick={() => void act(async () => {
      setProposal(null); setApproved(false);
      const result = await request('reconciliation', undefined, jobId);
      if (!result.reconciliation || result.reconciliation.job_id !== jobId) throw new Error('Geen passend verbruiksbewijs beschikbaar.');
      setProposal(result.reconciliation);
    })}>Bekijk verbruiksbewijs</button>
    {proposal && <div className="model-review">
      <p>{proposal.model} · {proposal.input_tokens} inputtokens · {proposal.output_tokens} outputtokens</p>
      <p>Afboeken: ${(proposal.accounted_microusd / 1e6).toFixed(6)} USD. Reservering: ${(proposal.reserved_microusd / 1e6).toFixed(6)} USD. Conservatieve verbruiksberekening, geen factuur.</p>
      <p>Deze opdracht wordt niet opnieuw verstuurd en blijft onafgerond. Andere al goedgekeurde opdrachten mogen hierna weer doorgaan binnen je budget, tenzij er nog andere blokkades zijn.</p>
      <label className="model-approval"><input type="checkbox" checked={approved} disabled={busy}
        onChange={event => setApproved(event.target.checked)} />Ik keur deze kostenafboeking en het vrijvallen van de resterende reservering goed.</label>
      <button type="button" className="trace-action" disabled={disabled || busy || !approved} onClick={() => void act(async () => {
        await approveReconciliation(jobId, proposal, approved, request);
        setProposal(null); setApproved(false); await onSaved();
      })}>Boek alleen deze kosten af</button>
    </div>}
    {message && <p className="work-error" role="status">{message}</p>}
  </section>;
}
