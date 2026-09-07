'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Check, Cpu, Database, LockKeyhole, Pause, Play, RefreshCw, X } from 'lucide-react';
import './connected-work.css';

type Task = { id: string; title: string };
type Result = { ok: boolean; step: string; source_sha256?: string; files_checked?: number; reason?: string; failures?: { path: string; line: number | null }[] };
type Job = {
  id: string; task_id: string; status: 'queued' | 'running' | 'paused' | 'succeeded' | 'failed' | 'cancelled';
  completed_steps: number; total_steps: number; results: Result[]; updated_at: number; error: string;
};
type ApiPayload = { error?: string; jobs?: Job[]; tasks?: Task[]; job?: Job; id?: string };
const labels: Record<Job['status'], string> = {
  queued: 'In de wachtrij', running: 'Controleert broncode', paused: 'Gepauzeerd',
  succeeded: 'Controle afgerond', failed: 'Controle mislukt', cancelled: 'Geannuleerd',
};
const stepNames = ['Bronbestanden vastleggen', 'Python-syntax controleren', 'Resultaat en bronversie bevestigen'];

async function api(resource: string, token: string, body?: unknown, signal?: AbortSignal) {
  const response = await fetch(`/api/leon?resource=${resource}`, {
    method: body === undefined ? 'GET' : 'POST', signal, cache: 'no-store',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json() as ApiPayload;
  if (!data || typeof data !== 'object') throw new Error('Onverwacht antwoord van de backend.');
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Verzoek mislukt.');
  return data;
}

export default function ConnectedWork({ demo }: { demo: ReactNode }) {
  const [showDemo, setShowDemo] = useState(false);
  const [draftToken, setDraftToken] = useState('');
  const [token, setToken] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const pendingRequest = useRef<{ taskId: string; requestId: string } | null>(null);
  const refreshController = useRef<AbortController | null>(null);
  const job = jobs.find(item => item.id === selectedId) ?? jobs[0];

  const refresh = useCallback(async () => {
    refreshController.current?.abort();
    const controller = new AbortController();
    refreshController.current = controller;
    try {
      const [work, available] = await Promise.all([
        api('jobs', token, undefined, controller.signal), api('tasks', token, undefined, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      if (!Array.isArray(work.jobs) || !Array.isArray(available.tasks)) throw new Error('Onverwacht antwoord van de backend.');
      setJobs(work.jobs); setTasks(available.tasks); setConnected(true); setConnectionError('');
    } catch (reason) {
      if (controller.signal.aborted) return;
      setConnected(false); setConnectionError(reason instanceof Error ? reason.message : 'Verbinding onderbroken.');
    }
  }, [token]);

  useEffect(() => {
    if (!token || showDemo) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await refresh();
      if (!stopped) timer = setTimeout(poll, 3000);
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); refreshController.current?.abort(); };
  }, [refresh, token, showDemo]);

  async function mutate(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Actie niet bevestigd. Ververs de status.'); }
    finally { setBusy(false); }
  }

  const activeTask = taskId || tasks[0]?.id || '';
  const controlsDisabled = busy || !connected;
  return <>
    <div className="work-mode-switch" aria-label="Werkmodus">
      <button type="button" aria-pressed={!showDemo} onClick={() => setShowDemo(false)}>Echte taken</button>
      <button type="button" aria-pressed={showDemo} onClick={() => setShowDemo(true)}>Ontwerpvoorbeeld</button>
    </div>
    {showDemo ? <><span className="work-demo-label">Voorbeelddata — geen echte agentuitvoering</span>{demo}</> :
      <div className="space-view work-view connected-work">
        <header className="work-header"><div><h1>Werk dat bewaard blijft.</h1><p>Echte lokale controles met opgeslagen voortgang. Geen gesimuleerde agents.</p></div></header>
        <div className="work-layout">
          <section className="mission-console" aria-label="Echte taakvoortgang">
            <div className="console-status"><span>{connected ? 'Verbonden met Leon' : 'Niet verbonden — status niet live'}</span><span>Lokale CPU · geen API-kosten</span></div>
            {!token && <form className="work-connect" onSubmit={event => { event.preventDefault(); setToken(draftToken.trim()); setDraftToken(''); }}>
              <label htmlFor="work-token">Leon-dashboardtoken</label>
              <input id="work-token" type="password" autoComplete="off" value={draftToken} onChange={event => setDraftToken(event.target.value)} required />
              <button className="pause-control" type="submit"><LockKeyhole size={15} /> Verbind</button>
              <p>Niet je OpenAI-sleutel. Het token blijft alleen in het geheugen van deze weergave.</p>
            </form>}
            {error && <p className="work-error" role="alert">{error}</p>}
            {connectionError && <p className="work-error" role="alert">{connectionError}</p>}
            {token && <div className="work-actions"><button className="secondary-control" type="button" onClick={() => void refresh()} disabled={busy}><RefreshCw size={15} /> Ververs</button><button className="secondary-control" type="button" onClick={() => { refreshController.current?.abort(); setToken(''); setJobs([]); setTasks([]); setConnected(false); setError(''); }}>Verbreek verbinding</button></div>}
            <div className="console-goal"><div><h2>Python-projectcontrole</h2><p>Leg bestandshashes vast, controleer de syntax en bewaar het gemeten resultaat. Dit wijzigt geen broncode.</p></div><span className="console-eta"><small>verwachte duur</small><strong>—</strong><em>nog niet gemeten</em></span></div>
            {job ? <>
              <label className="work-field">Opgeslagen controle<select value={job.id} onChange={event => setSelectedId(event.target.value)}>{jobs.map(item => <option key={item.id} value={item.id}>{labels[item.status]} · {item.id.slice(-8)}</option>)}</select></label>
              <p className="work-current-status" role="status">{labels[job.status]}{!connected && ' · laatst bekende status'}</p>
              <div className="console-progress-row"><span><strong>{job.completed_steps}/{job.total_steps}</strong><small>checkpoints</small></span><progress max={job.total_steps} value={job.completed_steps} aria-label="Voltooide checkpoints" /></div>
              <ol className="mission-timeline">{stepNames.map((name, index) => <li key={name} data-state={index < job.completed_steps ? 'done' : 'planned'}><span className="timeline-marker">{index < job.completed_steps ? <Check size={14} /> : index + 1}</span><span><strong>{name}</strong><small>{job.results[index]?.ok ? 'Resultaat opgeslagen' : job.results[index] ? 'Afwijking gevonden' : 'Nog niet uitgevoerd'}</small></span></li>)}</ol>
              <div className="work-actions">
                {['queued', 'running', 'paused'].includes(job.status) && <><button type="button" className="pause-control" disabled={controlsDisabled} onClick={() => void mutate(async () => { await api('control', token, { id: job.id, action: job.status === 'paused' ? 'resume' : 'pause' }); })}>{job.status === 'paused' ? <Play size={15} /> : <Pause size={15} />}{job.status === 'paused' ? 'Hervat' : 'Pauzeer'}</button><button type="button" className="secondary-control" disabled={controlsDisabled} onClick={() => void mutate(async () => { await api('control', token, { id: job.id, action: 'cancel' }); })}><X size={15} /> Annuleer</button></>}
              </div>
              <details className="work-evidence"><summary>Bekijk opgeslagen bewijs</summary><pre>{JSON.stringify(job.results, null, 2)}</pre></details>
              {job.status === 'queued' && <p className="work-hint">De worker verwerkt deze wachtrij. Blijft de taak wachten? Start de worker op de backendserver.</p>}
            </> : <p className="work-hint">{connected ? 'Nog geen echte controles. Kies een taak en start de eerste controle.' : 'Verbind om opgeslagen taken en resultaten te laden.'}</p>}
          </section>
          <aside className="work-sidebar" aria-label="Controle starten">
            <section className="agent-ensemble"><div className="sidebar-heading"><span><Cpu size={16} /> Nieuwe lokale controle</span></div>
              <label className="work-field">Koppel aan taak<select value={activeTask} disabled={!connected} onChange={event => { setTaskId(event.target.value); pendingRequest.current = null; }}><option value="" disabled>Kies een taak</option>{tasks.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
              <button type="button" className="trace-action" disabled={controlsDisabled || !activeTask} onClick={() => void mutate(async () => {
                if (!pendingRequest.current || pendingRequest.current.taskId !== activeTask) pendingRequest.current = { taskId: activeTask, requestId: crypto.randomUUID() };
                const result = await api('jobs', token, { task_id: activeTask, request_id: pendingRequest.current.requestId });
                if (!result.job?.id) throw new Error('Taakaanmaak niet bevestigd. Ververs de status voordat je opnieuw probeert.');
                setSelectedId(result.job.id); pendingRequest.current = null;
              })}><Play size={15} /> Start echte controle</button>
              <button type="button" className="trace-action" disabled={controlsDisabled} onClick={() => void mutate(async () => {
                const result = await api('tasks', token, { title: 'Lokale Python-projectcontrole', goal: 'Controleer de Python-syntax van deze Leon-bronversie zonder bronwijzigingen.', risk_level: 'low' });
                if (!result.id) throw new Error('Taakaanmaak niet bevestigd. Ververs de takenlijst.');
                setTaskId(result.id); pendingRequest.current = null;
              })}>Maak een controletaak</button>
            </section>
            <section className="approval-gate"><div className="sidebar-heading"><span><LockKeyhole size={16} /> Begrensde uitvoering</span></div><p>Alleen lokale syntaxcontrole. Geen betalingen, shellopdrachten, installs of modelcalls. Een geslaagde check keurt de bovenliggende taak niet automatisch goed.</p></section>
            <section className="resilience-log"><div className="sidebar-heading"><span><Database size={16} /> Opgeslagen in SQLite</span></div><p>Checkpoints blijven na browser- en workerherstart bestaan. Een onderbroken leesstap kan opnieuw worden gecontroleerd.</p><code>PYTHONPATH=src python3 -m leon_control_plane.local_worker</code></section>
          </aside>
        </div>
      </div>}
  </>;
}
