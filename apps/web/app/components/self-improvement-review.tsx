'use client';

import { useRef, useState } from 'react';
import { LockKeyhole } from 'lucide-react';
import {
  MAX_UI_PATCH_BYTES, assertSameSelfImprovementBinding, buildSelfImprovementApprove,
  buildSelfImprovementDraft, buildSelfImprovementRun, normalizeSelfImprovementApproval,
  normalizeSelfImprovementPreview, normalizeSelfImprovementRun, type SelfImprovementDraft,
  type SelfImprovementPreview, type SelfImprovementProfile, type SelfImprovementRun,
} from '../../lib/self-improvement-contract';

type Request = (path: 'preview' | 'approve' | 'run', body: unknown) => Promise<unknown>;

export default function SelfImprovementReview({ disabled, request }: { disabled: boolean; request: Request }) {
  const [patch, setPatch] = useState('');
  const [filesText, setFilesText] = useState('');
  const [profile, setProfile] = useState<SelfImprovementProfile>('git_diff_check');
  const [review, setReview] = useState<{ draft: SelfImprovementDraft; preview: SelfImprovementPreview } | null>(null);
  const [result, setResult] = useState<SelfImprovementRun | null>(null);
  const [approved, setApproved] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  const locked = useRef(false);
  const bytes = new TextEncoder().encode(patch).length;
  const invalidate = () => { revision.current++; setReview(null); setResult(null); setApproved(false); setMessage(''); };
  async function act(fn: () => Promise<void>) {
    if (locked.current || disabled) return;
    locked.current = true; setBusy(true); setMessage('');
    try { await fn(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Actie niet bevestigd. Er wordt niets aangenomen.'); }
    finally { locked.current = false; setBusy(false); }
  }
  return <details className="self-improvement-card">
    <summary><span><LockKeyhole size={16} /> Geavanceerde codecontrole</span><small>ingeklapt · alleen review</small></summary>
    <div className="self-improvement-body">
      <p>Controleer een bestaand patchvoorstel. Leon past niets toe, voert gewijzigde code niet uit en publiceert niets. Approval en reviewuitkomst worden wel in auditgeschiedenis vastgelegd.</p>
      <label className="work-field">Patch<textarea value={patch} disabled={busy} onChange={event => { invalidate(); setPatch(event.target.value); }} placeholder="Plak een unified diff" /></label>
      <p className="self-improvement-note">{bytes}/{MAX_UI_PATCH_BYTES} bytes</p>
      <label className="work-field">Bestaande bestanden<textarea value={filesText} disabled={busy} onChange={event => { invalidate(); setFilesText(event.target.value); }} placeholder="src/map/bestand.py, gescheiden door komma's" /></label>
      <label className="work-field">Validatieprofiel<select value={profile} disabled={busy} onChange={event => { invalidate(); setProfile(event.target.value as SelfImprovementProfile); }}><option value="git_diff_check">Alleen diffcontrole</option><option value="python_syntax">Python-syntax</option></select></label>
      <button type="button" className="trace-action" disabled={disabled || busy || !patch || !filesText || bytes > MAX_UI_PATCH_BYTES} onClick={() => void act(async () => {
        const snapshot = buildSelfImprovementDraft(patch, filesText, profile); const current = revision.current;
        const preview = normalizeSelfImprovementPreview(await request('preview', snapshot));
        if (JSON.stringify(preview.allowed_files) !== JSON.stringify(snapshot.allowed_files) || preview.validation_profile !== snapshot.validation_profile) throw new Error('Preview wijkt af van ingevoerde bestanden of validatie.');
        if (current === revision.current) { setReview({ draft: snapshot, preview }); setApproved(false); setResult(null); }
      })}>Preview maken</button>
      {review && <div className="self-improvement-review" aria-label="Codevoorstel beoordelen">
        <strong>Preview klaar — approval vereist</strong>
        <p>Bestanden: {review.preview.allowed_files.join(', ')} · profiel: {review.preview.validation_profile}</p>
        <p>Vingerafdruk: <code>{review.preview.patch_digest.slice(0, 16)}…</code></p>
        <details><summary>Volledige vingerafdruk</summary><code>{review.preview.patch_digest}</code></details>
        <p>Er is nog niets gewijzigd, uitgevoerd of gepubliceerd.</p>
        <label className="model-approval"><input type="checkbox" checked={approved} disabled={busy} onChange={event => setApproved(event.target.checked)} />Ik keur precies deze patch, bestanden en statische validatie goed.</label>
        <button type="button" className="trace-action" disabled={disabled || busy || !approved} onClick={() => void act(async () => {
          const approval = normalizeSelfImprovementApproval(await request('approve', buildSelfImprovementApprove(review.preview.approval_id)));
          assertSameSelfImprovementBinding(review.preview, approval);
          let rawResult: unknown;
          try { rawResult = await request('run', buildSelfImprovementRun(review.preview.approval_id, review.draft.patch)); }
          catch { throw new Error('Approval is geregistreerd, maar reviewuitkomst is onbekend. Patch wordt niet automatisch opnieuw verstuurd.'); }
          const normalized = normalizeSelfImprovementRun(rawResult);
          if (normalized.patch_digest !== review.preview.patch_digest || JSON.stringify(normalized.allowed_files) !== JSON.stringify(review.preview.allowed_files)) throw new Error('Reviewuitkomst hoort niet bij goedgekeurde preview.');
          setReview(null); setApproved(false); setResult(normalized);
          setMessage(normalized.status === 'review_required' && normalized.validation.passed
            ? 'Statische controle geslaagd. Menselijke review blijft vereist; broncode is niet toegepast of uitgevoerd.'
            : `Reviewstatus: ${normalized.status || 'onbekend'}. Er wordt geen succes aangenomen.`);
        })}>Goedkeuren en review uitvoeren</button>
      </div>}
      {result && <div className="self-improvement-review" aria-live="polite"><strong>Reviewbewijs</strong><p>Validatie: {result.validation.passed ? 'geslaagd' : 'niet geslaagd'} · tijdelijke map: {result.temporary_repository_deleted ? 'opgeruimd' : 'opruiming niet bevestigd'}</p></div>}
      {message && <p className="work-error" role="status">{message}</p>}
      <p className="self-improvement-note">Timeout of onbekende uitkomst blijft onbekend; geen automatische retry. Patch blijft alleen in dit browsertabblad zolang formulier openstaat.</p>
    </div>
  </details>;
}
