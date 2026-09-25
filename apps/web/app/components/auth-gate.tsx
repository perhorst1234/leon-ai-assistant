'use client';

import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import './auth-gate.css';

type Status = 'loading' | 'register' | 'login' | 'ready' | 'error';

export default function AuthGate({ children }: { children: (logout: () => void) => ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch('/api/auth', { cache: 'no-store' })
      .then(async response => { if (!response.ok) throw new Error('Inlogstatus niet beschikbaar.'); return response.json(); })
      .then(data => { const result = data as { authenticated?: boolean; registered?: boolean }; if (mounted) setStatus(result.authenticated ? 'ready' : result.registered ? 'login' : 'register'); })
      .catch(reason => { if (mounted) { setStatus('error'); setError(reason instanceof Error ? reason.message : 'Inlogstatus niet beschikbaar.'); } });
    return () => { mounted = false; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === 'register' && password !== confirm) { setError('De wachtwoorden komen niet overeen.'); return; }
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/auth', {
        method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: status, password, ...(status === 'register' ? { code } : {}) }),
      });
      const data = await response.json() as { error?: string };
      if (!response.ok) throw new Error(data.error || 'Inloggen mislukt.');
      setPassword(''); setConfirm(''); setCode(''); setStatus('ready');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Inloggen mislukt.'); }
    finally { setBusy(false); }
  }

  async function logout() {
    await fetch('/api/auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'logout' }) });
    setStatus('login');
  }

  if (status === 'ready') return <>{children(logout)}</>;
  return <main className="auth-screen"><div className="auth-panel">
    <span className="auth-mark">✦</span><p className="auth-eyebrow">Leon AI Assistant</p>
    <h1>{status === 'register' ? 'Maak je account aan' : status === 'login' ? 'Welkom terug' : 'Leon wordt geladen'}</h1>
    <p className="auth-intro">{status === 'register' ? 'Kies je eigen wachtwoord. De instelcode is alleen nodig bij het aanmaken van je account.' : 'Log in met je wachtwoord om je assistent te openen.'}</p>
    {(status === 'register' || status === 'login') && <form onSubmit={event => void submit(event)}>
      {status === 'register' && <label>Eenmalige instelcode<input type="text" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)} required /></label>}
      <label>Wachtwoord<input type="password" autoComplete={status === 'register' ? 'new-password' : 'current-password'} minLength={status === 'register' ? 12 : undefined} value={password} onChange={event => setPassword(event.target.value)} required /></label>
      {status === 'register' && <label>Herhaal wachtwoord<input type="password" autoComplete="new-password" minLength={12} value={confirm} onChange={event => setConfirm(event.target.value)} required /></label>}
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Even wachten…' : status === 'register' ? 'Account aanmaken' : 'Inloggen'}</button>
    </form>}
    {status === 'error' && <p className="auth-error" role="alert">{error}</p>}
  </div></main>;
}
