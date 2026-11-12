import React, { useEffect, useState } from 'react';
import { api, latestRequest } from './api.js';
import DuplicatePanel from './DuplicatePanel.jsx';
import './imports.css';

const labels = { ready: 'Pronta', imported: 'Importata', updated: 'Aggiornata', unchanged: 'Invariata',
  invalid: 'Scartata', failed: 'Fallita', ambiguous: 'Corrispondenza da scegliere', completed: 'Completata',
  partial: 'Completata con righe da controllare', skipped: 'Esclusa', pending: 'Da verificare', conflict: 'In conflitto', verified: 'Verificata', rejected: 'Fonte rifiutata per questo dato' };
const status = value => labels[value] || value;

function RowMatch({ row, disabled, onMatch }) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!query.trim()) { setOptions([]); return; }
    return latestRequest(signal => api('/computers/suggestions?q=' + encodeURIComponent(query), { signal }),
      data => { setOptions(data.items); setError(''); }, e => setError(e.message));
  }, [query]);
  return <div className="import-match">
    <label>Cerca un calcolatore esistente per la riga {row.position}
      <input disabled={disabled} value={query} onChange={e => setQuery(e.target.value)} maxLength={180} />
    </label>
    {options.map(c => <button type="button" key={c.id} disabled={disabled} onClick={() => onMatch(c.id)}>
      Associa a {c.manufacturer} {c.model_name} (ID {c.id})
    </button>)}
    {error && <p role="alert">{error}</p>}
  </div>;
}

function Claim({ claim, disabled, onReview }) {
  const [note, setNote] = useState('');
  const reviewable = ['pending', 'conflict'].includes(claim.status);
  const display = claim.display;
  return <section className={'import-claim ' + (claim.status === 'conflict' ? 'import-conflict' : '')}>
    <b>{display?.field_label || claim.field}</b>
    {display?.context && <p className="import-context">{display.context}</p>}
    <p>{status(claim.status)}{claim.estimated ? ' · Stima' : ''}</p>
    <dl className="import-values"><dt>Valore proposto dalla fonte</dt><dd>{display?.proposed || JSON.stringify(claim.value)}</dd>
      {claim.status === 'conflict' && <><dt>Valore attuale nell'archivio</dt><dd>{display?.current || JSON.stringify(claim.previous)}</dd></>}
    </dl>
    {claim.status === 'conflict' && <p>Il valore attuale resta conservato finché non accetti la proposta.</p>}
    {reviewable && display?.stale && <p className="inline-error" role="alert">Il dato è cambiato dopo questa importazione. Prepara una nuova anteprima prima di verificarlo.</p>}
    <p>Fonte a supporto: {claim.source.url ? <a href={claim.source.url} target="_blank" rel="noopener noreferrer">{claim.source.title}</a> : claim.source.title}</p>
    {claim.evidence && <details><summary>Passaggio, licenza e metadati</summary><pre>{claim.evidence}</pre></details>}
    <details><summary>Identificativi e valori originali</summary><pre>{JSON.stringify({ entity: claim.entity, target_id: claim.target_id, field: claim.field, value: claim.value, previous: claim.previous }, null, 2)}</pre></details>
    {claim.review_note && <p>Nota di verifica: {claim.review_note}</p>}
    {reviewable && <div className="import-review">
      <label>Motivazione della decisione
        <textarea rows={2} disabled={disabled} value={note} onChange={e => setNote(e.target.value)} maxLength={2000} />
      </label>
      <button type="button" disabled={disabled || display?.stale || note.trim().length < 5} onClick={() => onReview(claim.id, 'accept', note)}>
        {claim.status === 'conflict' ? 'Accetta il valore della fonte e verifica' : 'Conferma verifica della fonte'}
      </button>
      <button type="button" disabled={disabled || note.trim().length < 5} onClick={() => onReview(claim.id, 'reject', note)}>{claim.status === 'conflict' ? 'Mantieni il dato attuale' : 'Rifiuta questa asserzione'}</button>
      <p className="muted">La decisione riguarda questa asserzione, non l'intera fonte. Rifiutarla non elimina valori già importati: per correggerli usa l'editor del calcolatore.</p>
    </div>}
  </section>;
}

export default function ImportPanel({ onSaved }) {
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState('manual');
  const [file, setFile] = useState(null);
  const [rights, setRights] = useState(false);
  const [ids, setIds] = useState('');
  const [jobs, setJobs] = useState([]);
  const [job, setJob] = useState(null);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => latestRequest(signal => Promise.all([api('/admin/imports/providers', { signal }), api('/admin/imports', { signal })]),
    ([p, j]) => { setProviders(p); setJobs(j); }, e => setError(e.message)), []);
  async function open(id, nextOffset = 0) {
    setBusy(true); setError('');
    try { const detail = await api(`/admin/imports/${id}?offset=${nextOffset}`); setJob(detail); setOffset(nextOffset); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function action(work, saved = false) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await work();
      const id = result?.id || job?.id;
      if (id) { setJob(await api(`/admin/imports/${id}`)); setOffset(0); }
      setJobs(await api('/admin/imports'));
      if (saved) onSaved();
      setMessage('Operazione completata. Controlla esito e righe prima di proseguire.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  function upload(event) {
    event.preventDefault();
    const form = new FormData(); form.append('file', file); form.append('provider', provider); form.append('rights_confirmed', String(rights));
    action(() => api('/admin/imports/upload', { method: 'POST', body: form }));
  }
  async function review(id, decision, note) {
    await action(async () => { await api(`/admin/imports/claims/${id}/review`, { method: 'POST', body: JSON.stringify({ decision, note }) }); return { id: job.id }; }, true);
  }
  const selected = providers.find(p => p.id === provider);
  return <div className="imports">
    <h2>Importazione dati storici</h2>
    <p>Carica un lotto, controlla l'anteprima e poi applicalo all'archivio. I dati importati restano da verificare; i conflitti conservano il valore esistente.</p>
    <p className="muted">Uso locale single-user. Non pubblicare queste funzioni su Internet senza autenticazione e protezioni adeguate.</p>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p className="inline-success" role="status">{message}</p>}
    <DuplicatePanel onSaved={() => { setJob(null); api('/admin/imports').then(setJobs).catch(e => setError(e.message)); onSaved(); }} />
    <section className="panel">
      <label className="admin-field"><span>Fonte dati</span><select value={provider} disabled={busy} onChange={e => { setProvider(e.target.value); setRights(false); }}>
        {providers.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}
      </select></label>
      <p>{selected?.license}</p>
      {selected?.url && <p><a href={selected.url} target="_blank" rel="noopener noreferrer">Consulta la fonte</a></p>}
      {selected?.mode === 'manual' && <p>Fonte solo manuale: verifica termini e autorizzazione prima di trascrivere o caricare dati. Nessuno scraping automatico.</p>}
      <form onSubmit={upload}>
        <label className="admin-field"><span>Dataset CSV o JSON (UTF-8, massimo 8 MB e 1000 righe)</span>
          <input type="file" accept=".csv,.json" disabled={busy} required onChange={e => setFile(e.target.files[0] || null)} /></label>
        <label className="import-rights"><input type="checkbox" checked={rights} disabled={busy} required onChange={e => setRights(e.target.checked)} />Ho verificato il diritto di importare questo dataset e conservarne l'attribuzione.</label>
        <button type="submit" disabled={busy || !file || !rights}>Prepara anteprima dal file</button>
      </form>
      {selected?.mode === 'api' && <div className="import-remote">
        {provider === 'wikidata' && <label className="admin-field"><span>Identificativi Wikidata (da 1 a 20, separati da spazi o virgole)</span><input disabled={busy} value={ids} onChange={e => setIds(e.target.value)} maxLength={300} placeholder="Q…" /></label>}
        <button type="button" disabled={busy || (provider === 'wikidata' && !ids.trim())} onClick={() => action(() => api('/admin/imports/remote', {
          method: 'POST', body: JSON.stringify({ provider, ids: ids.trim().split(/[\s,]+/).filter(Boolean) })
        }))}>Recupera dalla fonte e prepara anteprima</button>
        <p className="muted">Richieste limitate alle API/esportazioni ufficiali. Una rete bloccata produce un lavoro fallito, conservato e ripetibile.</p>
      </div>}
    </section>
    <div className="import-layout"><section className="panel">
      <h3>Ultime importazioni</h3>
      {!jobs.length && <p>Nessuna importazione.</p>}
      {jobs.map(j => <button className="import-job" key={j.id} disabled={busy} onClick={() => open(j.id)}>
        <b>#{j.id} · {j.provider}</b><span>{j.filename}</span><small>{status(j.status)} · {j.total} righe</small>
      </button>)}
    </section><section className="panel import-detail" aria-busy={busy}>
      {busy && <p role="status">Operazione in corso…</p>}
      {!job ? <p>Scegli un'importazione per vedere originali, dati normalizzati, corrispondenze e verifiche.</p> : <>
        <h3>Importazione #{job.id} · {status(job.status)}</h3>
        {job.error && <p className="inline-error">{job.error}</p>}
        <p>Totale: {job.total} righe. {Object.entries(job.counts).map(([k, n]) => `${status(k)}: ${n}`).join(' · ')}</p>
        {job.data_coverage && <p>Record con fonte nel file: {job.data_coverage.records_with_source}. Prezzi presenti nel file: {job.data_coverage.prices}.
          {!job.data_coverage.prices && ' Il dataset non contiene prezzi: il caricamento non ne aggiunge e conserva quelli già archiviati.'}</p>}
        <p>Asserzioni: {Object.entries(job.verification_counts || {}).map(([k, n]) => `${status(k)}: ${n}`).join(' · ') || 'non ancora applicate'}</p>
        {job.retry_of && <p>Nuovo tentativo dell'importazione #{job.retry_of}.</p>}
        <details><summary>Impronta del file</summary><code>{job.checksum}</code></details>
        <div className="import-actions">
          {job.status === 'ready' && <button type="button" disabled={busy} onClick={() => action(() => api(`/admin/imports/${job.id}/apply`, { method: 'POST' }), true)}>Applica le righe pronte all'archivio</button>}
          <button type="button" disabled={busy} onClick={() => action(() => api(`/admin/imports/${job.id}/retry`, { method: 'POST' }))}>Riprova con una nuova anteprima</button>
          <a href={`/api/admin/imports/${job.id}/original`} download>Scarica originale conservato</a>
        </div>
        {job.rows.map(row => <article className="import-row" key={row.id}>
          <h4>Riga {row.position}: {row.normalized?.model_name || 'Dati non validi'} · {status(row.status)}</h4>
          {row.computer_id && <p>Calcolatore associato: {row.computer_label || 'ID ' + row.computer_id}</p>}
          {!!row.candidates.length && <p>Corrispondenze individuate: {(row.candidate_labels || row.candidates).join(' · ')}</p>}
          {row.error && <p className="inline-error">{row.error}</p>}
          {job.status === 'ready' && row.status !== 'skipped' && <button type="button" disabled={busy} onClick={() => action(async () => {
            await api(`/admin/imports/${job.id}/rows/${row.id}/skip`, { method: 'POST' }); return { id: job.id };
          })}>Escludi la riga {row.position} da questa importazione</button>}
          <details><summary>Dati originali e normalizzati</summary><h5>Originali</h5><pre>{JSON.stringify(row.raw, null, 2)}</pre><h5>Normalizzati</h5><pre>{JSON.stringify(row.normalized, null, 2)}</pre></details>
          {job.status === 'ready' && ['ready', 'ambiguous'].includes(row.status) && <RowMatch row={row} disabled={busy} onMatch={id => action(async () => {
            await api(`/admin/imports/${job.id}/rows/${row.id}/match`, { method: 'POST', body: JSON.stringify({ computer_id: id }) }); return { id: job.id };
          })} />}
          {!!row.claims.length && <details><summary>Fonti e verifiche ({row.claims.length} asserzioni; {row.claims.filter(c => c.status === 'conflict').length} conflitti)</summary>
            {[...row.claims].sort((a, b) => Number(b.status === 'conflict') - Number(a.status === 'conflict')).map(c => <Claim key={c.id} claim={c} disabled={busy} onReview={review} />)}
          </details>}
        </article>)}
        <div className="import-actions"><button disabled={busy || !offset} onClick={() => open(job.id, Math.max(0, offset - 25))}>Righe precedenti</button>
          <span>{job.total ? offset + 1 : 0}–{Math.min(offset + 25, job.total)} di {job.total}</span>
          <button disabled={busy || offset + 25 >= job.total} onClick={() => open(job.id, offset + 25)}>Righe successive</button></div>
      </>}
    </section></div>
  </div>;
}
