import React, { useEffect, useRef, useState } from 'react';
import { api, latestRequest } from './api.js';
import { Claim } from './ImportPanel.jsx';
import './imports.css';

const labels = { ready: 'Pronta', paused: 'In pausa', completed: 'Completata', archived: 'Archiviata',
  pending: 'In attesa', updated: 'Descrizione aggiornata', preserved: 'Descrizione esistente conservata',
  no_match: 'Testo italiano pertinente non trovato', ambiguous: 'Abbinamento ambiguo',
  search_error: 'Ricerca rifiutata dalla fonte', changed: 'Scheda modificata o rimossa', skipped: 'Saltata' };

export default function HistoryPanel({ onSaved }) {
  const [snapshot, setSnapshot] = useState(null);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [inspection, setInspection] = useState(null);
  const active = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const cancel = latestRequest(signal => api('/admin/history', { signal }), setSnapshot, e => setError(e.message));
    return () => { mounted.current = false; active.current = false; cancel(); };
  }, []);
  async function run({ retryUnresolved = false, onlyImproved = false } = {}) {
    if (active.current || busy) return;
    active.current = true; setRunning(true); setBusy(true); setError('');
    try {
      let job = snapshot?.job;
      if (retryUnresolved) job = await api(`/admin/history/${job.id}/retry-unresolved`, { method: 'POST',
        ...(onlyImproved ? { body: JSON.stringify({ only_improved: true }) } : {}) });
      else if (!job || ['completed', 'archived'].includes(job.status)) job = await api('/admin/history', { method: 'POST' });
      if (!mounted.current || !active.current) return;
      job = await api(`/admin/history/${job.id}/resume`, { method: 'POST' });
      setSnapshot(previous => ({ ...previous, job })); setBusy(false);
      while (active.current && job.status === 'ready') {
        const deadline = Math.max(Date.parse(job.next_request_at || '') || 0, Date.parse(job.lease_until || '') || 0);
        if (deadline > Date.now()) {
          await new Promise(resolve => setTimeout(resolve, Math.min(1000, deadline - Date.now() + 100)));
          if (job.lease_until && active.current && mounted.current) {
            const updated = await api('/admin/history');
            if (!mounted.current) return;
            setSnapshot(updated); job = updated.job;
          }
          continue;
        }
        try { job = await api(`/admin/history/${job.id}/step`, { method: 'POST' }); }
        catch (e) {
          if (e.status !== 429) throw e;
          const updated = await api('/admin/history');
          if (!mounted.current) return;
          setSnapshot(updated); job = updated.job;
          await new Promise(resolve => setTimeout(resolve, 1000));
          continue;
        }
        if (!mounted.current) return;
        setSnapshot(previous => ({ ...previous, job }));
      }
    } catch (e) { if (mounted.current) setError(e.message); }
    finally {
      active.current = false;
      if (mounted.current) {
        try { setSnapshot(await api('/admin/history')); } catch { /* retain durable progress */ }
        if (mounted.current) { setRunning(false); setBusy(false); onSaved(); }
      }
    }
  }
  async function action(name) {
    if (!snapshot?.job) return;
    if (name === 'pause') active.current = false;
    setBusy(true); setError('');
    try {
      const job = await api(`/admin/history/${snapshot.job.id}/${name}`, { method: 'POST',
        ...(name === 'skip' ? { body: JSON.stringify({ item_id: snapshot.job.current.id }) } : {}) });
      if (mounted.current) setSnapshot(previous => ({ ...previous, job }));
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function inspect(id) {
    setBusy(true); setError('');
    try {
      const data = await api(`/admin/imports/${id}`);
      if (mounted.current) setInspection(data);
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function review(id, decision, note) {
    setBusy(true); setError('');
    try {
      await api(`/admin/imports/claims/${id}/review`, { method: 'POST', body: JSON.stringify({ decision, note }) });
      if (mounted.current) await inspect(inspection.id);
      onSaved();
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  const job = snapshot?.job;
  const finished = !job || ['completed', 'archived'].includes(job.status);
  const counts = job?.counts || {};
  return <section className="imports history-panel">
    <h2>Cenni storici in italiano</h2>
    <p>Cerca il contesto storico dei sistemi su Wikipedia in italiano. Sostituisce le descrizioni vuote o preimpostate con testi documentati, conservando le descrizioni già curate.</p>
    <p>Nessuna chiave AI e nessun costo API. I casi senza un testo italiano adatto o con un abbinamento incerto vengono segnalati, senza inventare descrizioni. La presenza della fonte non equivale a una verifica umana.</p>
    <p>Se il nome esatto non basta, prova anche le parole chiave marca e modello e cerca i passaggi dedicati al modello nelle pagine della sua famiglia.</p>
    <p className="muted">Una richiesta alla volta, con almeno due secondi di pausa. Lascia aperto questo pannello durante la ricerca; puoi chiuderlo e riprendere in seguito senza perdere i risultati. Le note, le fonti, i prezzi e le fotografie esistenti restano conservati.</p>
    {snapshot && <p>Descrizioni vuote o preimpostate da approfondire: <b>{snapshot.eligible}</b>.</p>}
    <div className="import-actions">
      {!running && <button disabled={busy || !snapshot} onClick={run}>{finished ? 'Cerca cenni storici' : 'Riprendi ricerca storica'}</button>}
      {!running && job && ['paused', 'completed'].includes(job.status) && ((counts.no_match || 0) + (counts.search_error || 0) > 0) &&
        <button disabled={busy} onClick={() => run({ retryUnresolved: true })}>Riprova i sistemi senza testo</button>}
      {!running && job?.status === 'completed' && job.retry_suggested > 0 &&
        <button disabled={busy} onClick={() => run({ retryUnresolved: true, onlyImproved: true })}>Riprova gli abbinamenti migliorati ({job.retry_suggested})</button>}
      {running && <button disabled={busy} onClick={() => action('pause')}>Metti in pausa</button>}
      {job?.status === 'paused' && !running && <button disabled={busy || !job.current} onClick={() => action('skip')}>Salta il sistema corrente</button>}
      {job && <a className="source" href={`/api/admin/history/${job.id}/report`} download>Scarica resoconto completo</a>}
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {job && <section className="panel" aria-label="Avanzamento ricerca storica">
      <h3>Ricerca #{job.id} · {running ? 'In corso' : labels[job.status]}</h3>
      <p>Elaborati {job.total - (counts.pending || 0)} di {job.total}. Descrizioni aggiornate: {counts.updated || 0}. Già curate: {counts.preserved || 0}. Senza testo adatto: {counts.no_match || 0}. Ambigue: {counts.ambiguous || 0}. Saltate: {counts.skipped || 0}. Modificate o rimosse: {counts.changed || 0}. Query rifiutate: {counts.search_error || 0}.</p>
      {job.current && <p>In attesa: <b>{job.current.manufacturer} · {job.current.model_name}</b></p>}
      {job.current?.next_query && <p className="muted">Tentativo {job.current.attempt} · Ricerca: {job.current.next_query}</p>}
      {job.error && <p className="inline-error" role="alert">{job.error}</p>}
      <h4>Ultimi esiti</h4>
      <ul>{job.recent.map(item => <li key={item.id}><b>{item.model_name}</b> · {labels[item.status]}
        {item.description && <p>{item.description}</p>}
        {item.url && <a className="source" href={item.url} target="_blank" rel="noopener noreferrer">Fonte in italiano</a>}
        {item.import_job_id && <button disabled={busy || running} onClick={() => inspect(item.import_job_id)}>Fonti e verifica · {item.model_name}</button>}
        {item.error && <p className="muted">{item.error}</p>}
      </li>)}</ul>
    </section>}
    {inspection && <section className="panel" aria-label="Verifica della descrizione storica">
      <h3>Fonte e testo storico</h3>
      <a className="source" href={`/api/admin/imports/${inspection.id}/original`} download>Scarica risposta originale della fonte</a>
      {inspection.rows.flatMap(row => row.claims).map(claim => <Claim key={claim.id} claim={claim} disabled={busy || running} onReview={review} />)}
      <button disabled={busy} onClick={() => setInspection(null)}>Chiudi verifica</button>
    </section>}
  </section>;
}
