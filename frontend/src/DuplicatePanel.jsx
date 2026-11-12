import React, { useState } from 'react';
import { api } from './api.js';

const entityLabel = entity => entity === 'computer' ? 'Calcolatore' : 'Produttore';
const countLabels = { configurations: 'configurazioni', specifications: 'specifiche', releases: 'commercializzazioni',
  computer_images: 'fotografie', sources: 'fonti', computers: 'calcolatori' };
const fieldLabels = { model_name: 'Nome', name: 'Nome', description: 'Descrizione', announcement_date: 'Annuncio',
  announcement_precision: 'Precisione annuncio', image_url: 'Immagine', country: 'Paese', founded: 'Fondazione', website: 'Sito web' };

export default function DuplicatePanel({ onSaved }) {
  const [groups, setGroups] = useState(null);
  const [history, setHistory] = useState([]);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState('');
  async function refresh() {
    const [duplicates, audits] = await Promise.all([api('/admin/imports/reconciliation/duplicates'), api('/admin/imports/reconciliation/history')]);
    setGroups(duplicates); setHistory(audits);
  }
  async function action(work) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  function prepare(entity, source, target) {
    setPreview(null); setNote(''); setConfirmed(false);
    action(async () => setPreview(await api('/admin/imports/reconciliation/preview', {
      method: 'POST', body: JSON.stringify({ entity, source_id: source, target_id: target }) })));
  }
  return <section className="panel import-duplicates">
    <h3>Duplicati già importati</h3>
    <p>Controlla gli alias riconosciuti e scegli quale scheda mantenere. IBM System/360 (famiglia) e System/360 Model 50 (modello specifico) restano distinti.</p>
    <button type="button" disabled={busy} onClick={() => action(async () => { setPreview(null); await refresh(); })}>Controlla duplicati e produttori</button>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {message && <p role="status" className="inline-success">{message}</p>}
    {groups?.length === 0 && <p>Nessun duplicato con alias riconosciuti.</p>}
    {groups?.map(group => <article className="import-row" key={group.entity + group.items[0].id}>
      <h4>{entityLabel(group.entity)}: schede equivalenti da controllare</h4>
      {group.items.map(target => <div key={target.id}><b>{target.label} (ID {target.id})</b>
        {group.items.filter(item => item.id !== target.id).map(source => <button type="button" key={source.id} disabled={busy}
          onClick={() => prepare(group.entity, source.id, target.id)}>Anteprima: unisci {source.label} in {target.label} (mantieni ID {target.id})</button>)}
      </div>)}
    </article>)}
    {preview && <section className="import-row" aria-label="Anteprima riconciliazione">
      <h4>Da {preview.source_label} a {preview.target_label}</h4>
      <p>Resta la scheda ID {preview.target_id}; la scheda duplicata ID {preview.source_id} viene rimossa dopo il trasferimento dei dati. Il nome scelto e i dati già presenti restano conservati; i campi mancanti vengono completati.</p>
      <p>Configurazioni, specifiche, fotografie, commercializzazioni, prezzi e citazioni vengono trasferiti mantenendo gli identificativi. Le configurazioni con lo stesso nome rimangono separate. Per i produttori vengono riassegnate le schede collegate.</p>
      <p>Conteggi complessivi delle due schede: {Object.entries(preview.counts).map(([name, count]) => `${countLabels[name] || name}: ${count}`).join(' · ')}</p>
      <dl className="import-values">{preview.differences.map(d => <React.Fragment key={d.field}>
        <dt>{fieldLabels[d.field] || d.field}</dt><dd>Da unire: {d.source ?? 'Non indicato'}<br />Scheda mantenuta: {d.target ?? 'Non indicato'}</dd>
      </React.Fragment>)}</dl>
      <p>Gli originali e i riferimenti prima dell'unione vengono conservati nello storico scaricabile. Nessuna fonte diventa verificata automaticamente.</p>
      <label>Motivazione della riconciliazione<textarea disabled={busy} rows={2} value={note} maxLength={2000} onChange={e => setNote(e.target.value)} /></label>
      <label className="import-rights"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Ho controllato che si tratta dello stesso elemento e confermo la scheda da mantenere.</label>
      <button type="button" disabled={busy || !confirmed || note.trim().length < 5} onClick={() => action(async () => {
        await api('/admin/imports/reconciliation/apply', { method: 'POST', body: JSON.stringify({ entity: preview.entity,
          source_id: preview.source_id, target_id: preview.target_id, token: preview.token, note }) });
        setPreview(null); await refresh(); onSaved(); setMessage('Riconciliazione completata. Dati trasferiti e originali conservati nello storico.');
      })}>Applica la riconciliazione controllata</button>
    </section>}
    {!!history.length && <details><summary>Storico delle riconciliazioni</summary>{history.map(item => <p key={item.id}>
      {entityLabel(item.entity)}: ID {item.source_id} → {item.target_id}. {item.note} · <a href={`/api/admin/imports/reconciliation/history/${item.id}`} download>Scarica originali</a>
    </p>)}</details>}
  </section>;
}
