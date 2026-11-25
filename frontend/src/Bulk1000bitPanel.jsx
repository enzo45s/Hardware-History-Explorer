import React, { useEffect, useRef, useState } from 'react';
import { api, latestRequest } from './api.js';

const endpoint = '/admin/1000bit/bulk';
const labels = { ready: 'Pronta da riprendere', paused: 'In pausa', limited: 'Limite richieste raggiunto',
  completed: 'Visita terminata', cancelled: 'Sessione terminata', archived: 'Archiviata dopo svuotamento',
  updated: 'Aggiornato', unchanged: 'Invariato', indexed: 'Indice letto', unmatched: 'Nessuna corrispondenza trovata',
  blocked: 'Escluso da robots.txt', review: 'Da controllare', skipped: 'Saltato', redirect: 'Reindirizzamento',
  not_found: 'Non abbinato nelle pagine visitate', ambiguous: 'Corrispondenza da controllare', stale: 'Scheda modificata', removed: 'Scheda rimossa' };

export default function Bulk1000bitPanel({ onSaved, onOpenImport, revision }) {
  const [snapshot, setSnapshot] = useState(null);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [interval, setIntervalSeconds] = useState(5);
  const [limit, setLimit] = useState(20000);
  const active = useRef(false), mounted = useRef(true);
  const setJob = job => setSnapshot(previous => ({ ...previous, job }));
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; active.current = false; };
  }, []);
  useEffect(() => {
    if (running) return;
    return latestRequest(async signal => {
      const current = await api(endpoint, { signal });
      if (current.job) current.job = await api(`${endpoint}/${current.job.id}/refresh`, { method: 'POST', signal });
      return current;
    }, setSnapshot, e => setError(e.message));
  }, [revision, running]);

  async function run() {
    if (active.current || busy) return;
    active.current = true; setRunning(true); setBusy(true); setError('');
    try {
      let job = snapshot?.job;
      if (!job || ['completed', 'cancelled', 'archived'].includes(job.status)) {
        job = await api(endpoint, { method: 'POST', body: JSON.stringify({ interval_seconds: Number(interval), max_requests: Number(limit) }) });
      } else {
        job = await api(`${endpoint}/${job.id}/resume`, { method: 'POST', body: JSON.stringify({ max_requests: Math.max(Number(limit), job.max_requests) }) });
      }
      if (!mounted.current) return;
      setJob(job); setBusy(false);
      while (active.current && job.status === 'ready') {
        const deadline = Math.max(Date.parse(job.next_request_at || '') || 0, Date.parse(job.lease_until || '') || 0);
        if (deadline > Date.now()) {
          await new Promise(resolve => setTimeout(resolve, Math.min(deadline - Date.now() + 100, 1000)));
          continue;
        }
        job = await api(`${endpoint}/${job.id}/step`, { method: 'POST' });
        if (!mounted.current) return;
        setJob(job);
      }
    } catch (e) { if (mounted.current) setError(e.message); }
    finally {
      active.current = false;
      if (mounted.current) { setRunning(false); setBusy(false); onSaved(); }
    }
  }
  async function action(name) {
    active.current = false; setBusy(true); setError('');
    try { setJob(await api(`${endpoint}/${snapshot.job.id}/${name}`, { method: 'POST',
      ...(name === 'retry-unmatched' ? { body: JSON.stringify({ max_requests: Math.max(Number(limit), snapshot.job.max_requests) }) } : {}) })); }
    catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) { setBusy(false); onSaved(); } }
  }
  const job = snapshot?.job;
  const finished = !job || ['completed', 'cancelled', 'archived'].includes(job.status);
  const matched = (job?.counts.updated || 0) + (job?.counts.unchanged || 0);
  return <section className="panel bulk-1000bit" aria-label="Arricchimento automatico del catalogo da 1000bit">
    <h3>Arricchisci tutto il catalogo da 1000bit</h3>
    <p>Avvia una sola raccolta: visita l'indice e segue i collegamenti alle schede, abbinandole ai calcolatori del tuo archivio. Aggiorna automaticamente solo le corrispondenze univoche, senza creare nuovi modelli o sostituire dati discordanti.</p>
    <p>Non occorre salvare gli HTML o inserire un URL per ogni computer. Le fonti e gli originali delle schede abbinate vengono conservati. Le informazioni restano da verificare.</p>
    <div className="admin-grid">
      <label className="admin-field"><span>Pausa minima fra richieste (secondi)</span><input type="number" min={5} max={3600} value={interval} disabled={busy || running || !finished} onChange={e => setIntervalSeconds(e.target.value)} /></label>
      <label className="admin-field"><span>Limite richieste della raccolta</span><input type="number" min={1} max={50000} value={limit} disabled={busy || running} onChange={e => setLimit(e.target.value)} /></label>
    </div>
    <div className="import-actions">
      <button type="button" disabled={!snapshot || busy || running || (finished && !snapshot.catalog_total)} onClick={run}>
        {finished ? 'Avvia arricchimento di tutto il catalogo' : 'Riprendi arricchimento del catalogo'}
      </button>
      {running && <button type="button" disabled={busy} onClick={() => action('pause')}>Metti in pausa la raccolta</button>}
      {!finished && !running && <button type="button" disabled={busy} onClick={() => action('cancel')}>Termina questa sessione</button>}
      {job?.status === 'paused' && !running && <button type="button" disabled={busy} onClick={() => action('skip')}>Salta la pagina corrente</button>}
      {!!job?.pages.unmatched && !running && !['cancelled', 'archived'].includes(job.status) && <button type="button" disabled={busy} onClick={() => action('retry-unmatched')}>Riprova le pagine non abbinate</button>}
    </div>
    <p className="muted">Mantieni aperta questa sezione per proseguire. Può durare ore: puoi mettere in pausa e riprendere anche dopo un riavvio, senza riscaricare le pagine già elaborate. Sono rispettati robots.txt e le pause richieste dal sito. Se nessuna scheda è abbinabile, il sistema resta invariato.</p>
    {!!job?.pages.unmatched && <p className="muted">Puoi rimettere in coda le sole pagine non abbinate e poi premere Riprendi. Gli aggiornamenti già riusciti restano conservati. Per gli abbinamenti sono considerate insieme marca e modello, ignorando spazi/trattini equivalenti e le indicazioni geografiche riconosciute della marca.</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {job && <section aria-label="Avanzamento arricchimento 1000bit">
      <h4>Sessione #{job.id} · {running ? 'In corso' : labels[job.status]}</h4>
      <p role="status">Catalogo iniziale: {job.total} sistemi. Abbinati: {matched}; aggiornati: {job.counts.updated || 0}; invariati: {job.counts.unchanged || 0}; da controllare: {job.counts.ambiguous || 0}.</p>
      <p>Richieste effettuate: {job.requests} di {job.max_requests}. Pagine in coda: {job.pages.pending || 0}; indici letti: {job.pages.indexed || 0}. Pausa effettiva: {job.interval_seconds} secondi.</p>
      <p>Pagine escluse da robots.txt: {job.pages.blocked || 0}; saltate dall'operatore: {job.pages.skipped || 0}.</p>
      <p>Differenze conservate in revisione: {job.conflicts}. I valori attuali restano intatti; non occorre confermare ogni computer per proseguire la raccolta.</p>
      <p><a href={`/api${endpoint}/${job.id}/report`} download>Scarica il resoconto completo dei sistemi e delle pagine (JSON)</a></p>
      {job.error && <p className="inline-error" role="alert">{job.error} La coda resta conservata: risolto il problema, usa Riprendi.</p>}
      {job.status === 'limited' && <p>Aumenta il limite richieste e premi Riprendi per continuare la stessa coda.</p>}
      {job.status === 'completed' && <p>Terminati i collegamenti raggiungibili. Sistemi non abbinati nelle pagine visitate: {job.counts.not_found || 0}. La fonte potrebbe non contenere tutti i computer del catalogo; pagine saltate o escluse possono limitare la copertura.</p>}
      {!!job.reviews.length && <details><summary>Corrispondenze da controllare ({job.pages.review || 0})</summary>{job.reviews.map(p => <p key={p.import_job_id}>
        <b>{p.model_name}</b> · <a href={p.url} target="_blank" rel="noopener noreferrer">Scheda fonte</a>{' '}
        <button type="button" onClick={() => onOpenImport(p.import_job_id)}>Apri anteprima da controllare</button>
      </p>)}</details>}
      {!!job.not_found.length && <details><summary>Esempi di sistemi non abbinati o da controllare</summary><ul>{job.not_found.map(t => <li key={t.id ?? t.model_name}>{t.manufacturer} · {t.model_name}: {labels[t.status]}</li>)}</ul></details>}
      {!!job.recent.length && <details><summary>Ultime pagine elaborate</summary><ul>{job.recent.map(p => <li key={p.url}>
        <a href={p.url} target="_blank" rel="noopener noreferrer">{p.manufacturer && p.model_name ? `${p.manufacturer} · ${p.model_name}` : p.model_name || p.url}</a>: {labels[p.status] || p.status}
        {p.import_job_id && <> <button type="button" onClick={() => onOpenImport(p.import_job_id)}>Controlla fonti e dati</button></>}
        {p.error && <p className="muted">{p.error}</p>}
      </li>)}</ul></details>}
    </section>}
  </section>;
}
