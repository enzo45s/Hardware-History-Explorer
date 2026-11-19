import React, { useEffect, useState } from 'react';
import { api, latestRequest } from './api.js';
import ArchivePanel from './ArchivePanel.jsx';
import Bulk1000bitPanel from './Bulk1000bitPanel.jsx';
import './imports.css';

const labels = { ready: 'Pronta', imported: 'Importata', updated: 'Aggiornata', unchanged: 'Invariata',
  invalid: 'Scartata', failed: 'Fallita', ambiguous: 'Corrispondenza da scegliere', completed: 'Completata',
  partial: 'Completata con righe da controllare', skipped: 'Esclusa', archived: 'Archiviata dopo svuotamento', pending: 'Da verificare', conflict: 'In conflitto', verified: 'Verificata', rejected: 'Fonte rifiutata per questo dato' };
const status = value => labels[value] || value;
const descriptionActions = {
  fill: 'Descrizione mancante: verrà inserita.',
  replace_template: 'Testo preimpostato: verrà sostituito.',
  unchanged: 'Testo già presente.',
  conflict: 'Descrizione già curata: resta conservata, la proposta richiede una decisione in Fonti e verifiche.',
  unmatched: 'Nessun abbinamento: associa un calcolatore esistente oppure la riga sarà esclusa.',
  ambiguous: 'Più corrispondenze: scegli il calcolatore prima di applicare la riga.',
};

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

export function Claim({ claim, disabled, onReview }) {
  const [note, setNote] = useState('');
  const reviewable = claim.computer_id != null && ['pending', 'conflict'].includes(claim.status);
  const display = claim.display;
  return <section className={'import-claim ' + (claim.status === 'conflict' ? 'import-conflict' : '')}>
    <b>{display?.field_label || claim.field}</b>
    {claim.model_variant && <p className="import-context">Configurazione: {claim.model_variant}</p>}
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

export default function ImportPanel({ onSaved, onArchiveReset = onSaved }) {
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState('manual');
  const [file, setFile] = useState(null);
  const [rights, setRights] = useState(false);
  const [ids, setIds] = useState('');
  const [urls, setUrls] = useState('');
  const [existingOnly, setExistingOnly] = useState(true);
  const [sourceUrl, setSourceUrl] = useState('');
  const [bulkRevision, setBulkRevision] = useState(0);
  const [job, setJob] = useState(null);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [priceRecoveries, setPriceRecoveries] = useState([]);
  useEffect(() => latestRequest(signal => api('/admin/imports/providers', { signal }),
    setProviders, e => setError(e.message)), []);
  useEffect(() => {
    if (provider !== 'historical_prices') return;
    return latestRequest(signal => api('/admin/imports/price-context-recovery', { signal }),
      setPriceRecoveries, e => setError(e.message));
  }, [provider, bulkRevision]);
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
      if (saved) { setBulkRevision(value => value + 1); onSaved(); }
      setMessage('Operazione completata. Controlla esito e righe prima di proseguire.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  function upload(event) {
    event.preventDefault();
    const form = new FormData(); form.append('file', file); form.append('provider', provider); form.append('rights_confirmed', String(rights));
    if (provider === '1000bit') {
      form.append('existing_only', String(existingOnly));
      if (sourceUrl.trim()) form.append('source_url', sourceUrl.trim());
    }
    if (['historical_prices', 'historical_descriptions'].includes(provider)) form.append('existing_only', 'true');
    action(() => api('/admin/imports/upload', { method: 'POST', body: form }));
  }
  async function review(id, decision, note) {
    await action(async () => { await api(`/admin/imports/claims/${id}/review`, { method: 'POST', body: JSON.stringify({ decision, note }) }); return { id: job.id }; }, true);
  }
  const selected = providers.find(p => p.id === provider);
  const priceRecovery = priceRecoveries.find(job => job.verification_counts?.conflict || job.counts?.failed) || priceRecoveries[0];
  const singleImport = <>
      {provider === 'historical_descriptions' && <>
        <p>Carica il JSON delle descrizioni: un elenco di oggetti con manufacturer, model_name, description e source (title, url e source_type). Sono accettati anche elenchi racchiusi in records.</p>
        <p>Associa soltanto computer già censiti, riconoscendo marche brevi, nomi equivalenti e alias approvati. I testi vuoti o preimpostati vengono completati; le descrizioni già curate restano conservate e le proposte diverse diventano conflitti da esaminare.</p>
        <p className="muted">Il caricamento non crea sistemi e non cambia nomi, specifiche, foto o prezzi. Testi e URL provengono dal file e restano da verificare; nessuna ricerca online e nessun costo API.</p>
      </>}
      {provider === 'historical_prices' && <>
        <p>Carica l'Excel con il foglio «Prezzi per modello», oppure un CSV/JSON canonico. Aggiorna soltanto i sistemi già presenti, abbinandoli per produttore e modello: gli ID del foglio non sono ID del catalogo.</p>
        <p className="muted">Gli URL e l'affidabilità dichiarata restano da verificare. Prezzi, valuta, mercato, configurazione e note vengono conservati; l'anno della ricerca non viene trasformato in una data di lancio. Le indicazioni riferite a famiglie o varianti diverse restano note.</p>
        {priceRecovery && <section className="panel" aria-label="Recupero prezzi dalle note">
          <p>Recupero automatico dei prezzi dalle note · Operazione #{priceRecovery.id}. {Object.entries(priceRecovery.counts).map(([key, value]) => `${status(key)}: ${value}`).join(' · ')}.</p>
          <p>Conflitti da controllare: {priceRecovery.verification_counts?.conflict || 0}. Le note e le fonti originali restano conservate.</p>
          <button type="button" disabled={busy} onClick={() => open(priceRecovery.id)}>Controlla prezzi recuperati</button>
        </section>}
      </>}
      {provider === '1000bit' && <>
        <p>Carica una scheda HTML salvata dal browser, un JSON del raccoglitore oppure un dataset CSV/JSON. Controlla l'anteprima prima di applicare i dati.</p>
        <label className="import-rights"><input type="checkbox" checked={existingOnly} disabled={busy} onChange={e => setExistingOnly(e.target.checked)} />Aggiorna solo calcolatori già presenti</label>
        <p className="muted">Con questa opzione attiva, associa le righe senza corrispondenza a una scheda esistente; quelle non associate saranno escluse senza creare nuovi calcolatori.</p>
      </>}
      <form onSubmit={upload}>
        <label className="admin-field"><span>{provider === 'historical_descriptions' ? 'JSON delle descrizioni (UTF-8, massimo 8 MB e 1000 righe)' : provider === 'historical_prices' ? 'Excel dei prezzi o dataset CSV/JSON (massimo 8 MB)' : provider === '1000bit' ? 'Scheda HTML o dataset CSV/JSON 1000bit (massimo 8 MB)' : 'Dataset CSV o JSON (UTF-8, massimo 8 MB e 1000 righe)'}</span>
          <input type="file" accept={provider === 'historical_descriptions' ? '.json' : provider === 'historical_prices' ? '.xlsx,.csv,.json' : provider === '1000bit' ? '.html,.htm,.csv,.json' : '.csv,.json'} disabled={busy} required onChange={e => setFile(e.target.files[0] || null)} /></label>
        {provider === '1000bit' && <label className="admin-field"><span>URL originale della scheda HTML (facoltativo se presente nel file)</span>
          <input type="url" value={sourceUrl} maxLength={800} disabled={busy} placeholder="https://www.1000bit.it/scheda.asp?id=…" onChange={e => setSourceUrl(e.target.value)} /></label>}
        <label className="import-rights"><input type="checkbox" checked={rights} disabled={busy} required onChange={e => setRights(e.target.checked)} />Ho verificato il diritto di importare questo dataset e conservarne l'attribuzione.</label>
        <button type="submit" disabled={busy || !file || !rights}>Prepara anteprima dal file</button>
      </form>
      {['api', 'sheets'].includes(selected?.mode) && <div className="import-remote">
        {provider === 'wikidata' && <label className="admin-field"><span>Identificativi Wikidata (da 1 a 20, separati da spazi o virgole)</span><input disabled={busy} value={ids} onChange={e => setIds(e.target.value)} maxLength={300} placeholder="Q…" /></label>}
        {provider === '1000bit' && <label className="admin-field"><span>URL delle schede 1000bit (da 1 a 5, uno per riga)</span>
          <textarea rows={3} disabled={busy} value={urls} maxLength={4004} onChange={e => setUrls(e.target.value)} placeholder="https://www.1000bit.it/scheda.asp?id=282" /></label>}
        <button type="button" disabled={busy || (provider === 'wikidata' && !ids.trim()) || (provider === '1000bit' && !urls.trim())} onClick={() => action(() => api('/admin/imports/remote', {
          method: 'POST', body: JSON.stringify(provider === '1000bit' ? { provider, urls: urls.trim().split(/\s+/).filter(Boolean), existing_only: existingOnly } : { provider, ids: ids.trim().split(/[\s,]+/).filter(Boolean) })
        }))}>Recupera dalla fonte e prepara anteprima</button>
        <p className="muted">{provider === '1000bit' ? 'Schede selezionate, una richiesta alla volta, con almeno 5 secondi di pausa e rispetto di robots.txt. Nessuna scansione del catalogo. Se la rete è bloccata, carica le pagine salvate dal browser.' : 'Richieste limitate alle API/esportazioni ufficiali. Una rete bloccata produce un lavoro fallito, conservato e ripetibile.'}</p>
      </div>}
  </>;
  return <div className="imports">
    <h2>Importazione dati storici</h2>
    <p>{provider === '1000bit' ? 'Avvia l’arricchimento automatico del catalogo. Il caricamento delle singole schede resta disponibile come opzione facoltativa.' : 'Carica un lotto, controlla l’anteprima e poi applicalo all’archivio.'} I dati importati restano da verificare; i conflitti conservano il valore esistente.</p>
    <p className="muted">Uso locale single-user. Non pubblicare queste funzioni su Internet senza autenticazione e protezioni adeguate.</p>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p className="inline-success" role="status">{message}</p>}
    <section className="panel">
      <label className="admin-field"><span>Fonte dati</span><select aria-label="Fonte dati" value={provider} disabled={busy} onChange={e => { setProvider(e.target.value); setRights(false); }}>
        {providers.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}
      </select></label>
      <p>{selected?.license}</p>
      {selected?.url && <p><a href={selected.url} target="_blank" rel="noopener noreferrer">Consulta la fonte</a></p>}
      {selected?.mode === 'manual' && <p>Fonte solo manuale: verifica termini e autorizzazione prima di trascrivere o caricare dati. Nessuno scraping automatico.</p>}
    </section>
    {provider === '1000bit' && <Bulk1000bitPanel onSaved={onSaved} onOpenImport={open} revision={bulkRevision} />}
    {provider === '1000bit' ? <details className="panel">
      <summary>Importa singole schede o file (facoltativo)</summary>
      {singleImport}
    </details> : <section className="panel">{singleImport}</section>}
    {(job || busy) && <section className="panel import-detail" aria-busy={busy}>
      {busy && <p role="status">Operazione in corso…</p>}
      {job && <>
        <h3>Importazione #{job.id} · {status(job.status)}</h3>
        {job.status === 'archived' && <p>Esiti storici precedenti allo svuotamento. Le schede associate sono state rimosse. Usa una nuova anteprima per importare nuovamente questi dati.</p>}
        {job.error && <p className="inline-error">{job.error}</p>}
        <p>Totale: {job.total} righe. {Object.entries(job.counts).map(([k, n]) => `${status(k)}: ${n}`).join(' · ')}</p>
        {job.existing_only && <p className="muted">Solo aggiornamenti a calcolatori esistenti. Nessuna nuova scheda verrà creata.</p>}
        {job.price_workbook_report && <div className="panel" role="region" aria-label="Controllo Excel dei prezzi">
          <p>Excel: {job.price_workbook_report.models} sistemi; {job.price_workbook_report.without_price} senza importo esclusi. Prezzi numerici: {job.price_workbook_report.price_records}; sole note: {job.price_workbook_report.context_only_records}.</p>
          <p>Righe con colonne fonte riallineate: {job.price_workbook_report.source_columns_repaired}. Righe non valide: {job.price_workbook_report.invalid_records}.</p>
          <p className="muted">Viene letto soltanto «Prezzi per modello», per evitare doppioni fra i fogli. Riporta qui eventuali nuovi risultati prima di importare un Excel aggiornato. URL e giudizi di affidabilità provengono dal file e restano da verificare.</p>
        </div>}
        {job.provider !== 'historical_descriptions' && job.data_coverage && <p>Record con fonte nel file: {job.data_coverage.records_with_source}. Prezzi presenti nel file: {job.data_coverage.prices}.
          {!job.data_coverage.prices && (job.provider === 'historical_prices'
            ? ' Il file contiene sole note: i campi originali delle righe Excel vengono recuperati automaticamente quando completi e compatibili.'
            : ' Il dataset non contiene prezzi: il caricamento non ne aggiunge e conserva quelli già archiviati.')}</p>}
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
          {job.existing_only && job.status === 'ready' && !row.computer_id && row.status === 'ready' && <p>Associa questa riga a un calcolatore esistente prima di applicarla, altrimenti sarà esclusa.</p>}
          {!!row.candidates.length && <p>Corrispondenze individuate: {(row.candidate_labels || row.candidates).join(' · ')}</p>}
          {row.error && <p className="inline-error">{row.error}</p>}
          {row.description_preview && <section className="panel" aria-label={`Anteprima descrizione riga ${row.position}`}>
            <p><b>{descriptionActions[row.description_preview.action]}</b></p>
            {row.description_preview.current && <><h5>Testo attuale</h5><p className="import-description-text">{row.description_preview.current}</p></>}
            <h5>Testo nel file</h5><p className="import-description-text">{row.description_preview.proposed}</p>
            <p>Fonte dichiarata: <a href={row.description_preview.source.url} target="_blank" rel="noopener noreferrer">{row.description_preview.source.title}</a></p>
          </section>}
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
    </section>}
    <ArchivePanel onReset={() => { setJob(null); setOffset(0); onArchiveReset(); }} />
  </div>;
}
