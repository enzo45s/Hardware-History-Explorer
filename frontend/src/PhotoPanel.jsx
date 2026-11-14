import React, { useEffect, useRef, useState } from 'react';
import { api, latestRequest } from './api.js';
import './imports.css';

const labels = { added: 'Foto associata', no_match: 'Nessuna foto utilizzabile', skipped: 'Saltata',
  search_error: 'Ricerca non valida',
  ready: 'Pronta da riprendere', paused: 'In pausa', completed: 'Completata', archived: 'Archiviata dopo svuotamento' };

export default function PhotoPanel({ onSaved }) {
  const [snapshot, setSnapshot] = useState(null);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const active = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const cancel = latestRequest(signal => api('/admin/photos', { signal }), setSnapshot, e => setError(e.message));
    return () => { mounted.current = false; active.current = false; cancel(); };
  }, []);
  useEffect(() => setQuery(snapshot?.job?.current?.query || ''), [snapshot?.job?.current?.id, snapshot?.job?.current?.query]);
  async function run() {
    if (active.current || busy) return;
    active.current = true; setRunning(true); setBusy(true); setError('');
    try {
      let job = snapshot?.job;
      if (!job || ['completed', 'archived'].includes(job.status)) job = await api('/admin/photos', { method: 'POST' });
      if (!mounted.current || !active.current) return;
      job = await api(`/admin/photos/${job.id}/resume`, { method: 'POST' });
      setSnapshot(previous => ({ ...previous, job })); setBusy(false);
      while (active.current && job.status === 'ready') {
        const deadline = Math.max(Date.parse(job.next_request_at || '') || 0, Date.parse(job.lease_until || '') || 0);
        const wait = Math.max(0, deadline - Date.now());
        // Short waits allow pause/unmount to stop the client promptly.
        if (wait > 0) {
          await new Promise(resolve => setTimeout(resolve, Math.min(wait + 100, 1000)));
          if (job.lease_until && active.current && mounted.current) {
            const updated = await api('/admin/photos');
            if (!mounted.current) return;
            setSnapshot(updated); job = updated.job;
          }
          continue;
        }
        try {
          job = await api(`/admin/photos/${job.id}/step`, { method: 'POST' });
        } catch (e) {
          if (e.status !== 429) throw e;
          // Another tab/expired connection may still own a lease. Refresh and
          // wait, instead of ending the run with a misleading Commons outage.
          const updated = await api('/admin/photos');
          if (!mounted.current) return;
          setSnapshot(updated); job = updated.job;
          await new Promise(resolve => setTimeout(resolve, 1000));
          continue;
        }
        if (!mounted.current) return;
        setSnapshot(previous => ({ ...previous, job, missing: Math.max(0, previous.missing
          - Math.max(0, (job.counts.added || 0) - (previous.job?.counts.added || 0))) }));
      }
    } catch (e) { if (mounted.current) setError(e.message); }
    finally {
      active.current = false;
      if (mounted.current) {
        setBusy(true);
        try {
          const updated = await api('/admin/photos');
          if (mounted.current) setSnapshot(updated);
        } catch { /* keep the last durable progress */ }
        if (mounted.current) { setRunning(false); setBusy(false); onSaved(); }
      }
    }
  }
  async function pause() {
    active.current = false; setBusy(true);
    try {
      const job = await api(`/admin/photos/${snapshot.job.id}/pause`, { method: 'POST' });
      if (mounted.current) setSnapshot(previous => ({ ...previous, job }));
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function changeCurrent(action) {
    const current = snapshot?.job?.current;
    if (!current || running || busy) return;
    setBusy(true); setError('');
    try {
      const job = await api(`/admin/photos/${snapshot.job.id}/${action}`, { method: 'POST',
        body: JSON.stringify({ item_id: current.id, ...(action === 'query' ? { query: query.trim() } : {}) }) });
      if (mounted.current) setSnapshot(previous => ({ ...previous, job }));
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  const job = snapshot?.job;
  const finished = !job || ['completed', 'archived'].includes(job.status);
  const pending = job?.counts.pending || 0;
  const done = job ? job.total - pending : 0;
  return <section className="imports photo-panel">
    <h2>Foto automatiche da Wikimedia Commons</h2>
    <p>Associa automaticamente il primo risultato utilizzabile ai sistemi senza foto. Cerca solo il nome del modello, una macchina alla volta, con almeno due secondi fra le richieste.</p>
    <p>Le immagini sono scelte automaticamente: potrebbero raffigurare un modello diverso. Puoi correggerle nella scheda del sistema, da <b>Gestisci fotografie</b>. Autore, licenza e pagina Commons vengono conservati; le foto già presenti restano conservate.</p>
    <p className="muted">Uso locale single-user. Le immagini restano collegamenti esterni. I risultati privi di attribuzione o licenza riconoscibile non vengono associati automaticamente.</p>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {snapshot && <p>Sistemi attualmente senza foto: <b>{snapshot.missing}</b>.</p>}
    <div className="import-actions">
      <button type="button" disabled={!snapshot || running || busy || (finished ? snapshot.missing === 0 : !pending)} onClick={run}>
        {job && !['completed', 'archived'].includes(job.status) ? 'Riprendi ricerca automatica' : 'Avvia ricerca automatica'}
      </button>
      {running && <button type="button" disabled={busy || !job} onClick={pause}>Metti in pausa</button>}
    </div>
    <p className="muted">Mantieni aperta questa sezione per proseguire. Uscendo, la richiesta già partita può terminare; il resto resta in attesa. Puoi riprendere anche dopo il riavvio dell'applicazione.</p>
    {job && <section className="panel" aria-label="Avanzamento ricerca fotografica">
      <h3>Ricerca #{job.id} · {running ? 'In corso' : labels[job.status] || job.status}</h3>
      <progress aria-label="Sistemi elaborati" value={done} max={job.total || 1} />
      <p role="status">Elaborati {done} di {job.total}. Foto associate: {job.counts.added || 0}. Senza risultato: {job.counts.no_match || 0}. Ricerche non valide: {job.counts.search_error || 0}. Saltati: {job.counts.skipped || 0}.</p>
      {job.current && <div className="photo-current">
        <h4>Modello corrente: {job.current.model_name}</h4>
        <label className="admin-field"><span>Ricerca Commons del modello corrente</span>
          <input value={query} disabled={running || busy} minLength={2} maxLength={90} onChange={e => setQuery(e.target.value)} /></label>
        {job.current.error && job.current.error !== job.error && <p className="muted">{job.current.error}</p>}
        {!running && <div className="import-actions">
          <button type="button" disabled={busy || query.trim().length < 2 || query.trim() === job.current.query} onClick={() => changeCurrent('query')}>Salva ricerca per questo modello</button>
          <button type="button" disabled={busy} onClick={() => changeCurrent('skip')}>Salta questo modello</button>
        </div>}
      </div>}
      {job.error && <p role="alert" className="inline-error">{job.error} La macchina corrente resta in attesa: puoi correggere la ricerca, saltare il modello oppure riprendere dopo la pausa richiesta.</p>}
      {!!job.recent.length && <><h4>Ultimi esiti</h4><ul>{job.recent.map((row, i) => <li key={i}>
        <b>{row.model_name}</b> · {labels[row.status]}{row.source_url && <> · <a href={row.source_url} target="_blank" rel="noopener noreferrer">Fonte Commons</a></>}
        {row.error && <p className="muted">{row.error}</p>}
      </li>)}</ul></>}
      {job.status === 'completed' && <p>Ricerca completata. Avviandone una nuova puoi ritentare i sistemi rimasti senza foto e includere nuove schede.</p>}
    </section>}
  </section>;
}
