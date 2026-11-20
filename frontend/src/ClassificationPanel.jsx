import React, { useEffect, useState } from 'react';
import { api, latestRequest } from './api.js';
import './imports.css';

export default function ClassificationPanel({ onSaved, onEditComputer }) {
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => latestRequest(signal => api('/admin/classification/preview', { signal }), setPreview, e => setError(e.message)), []);
  async function refresh() {
    setBusy(true); setError(''); setMessage('');
    try { setPreview(await api('/admin/classification/preview')); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function apply() {
    setBusy(true); setError(''); setMessage('');
    let updated = 0, cleaned = 0;
    try {
      let current = preview;
      while (current.total || current.cleanup_count) {
        const result = await api('/admin/classification/apply', { method: 'POST', body: JSON.stringify({ token: current.token }) });
        updated += result.updated; cleaned += result.cleaned;
        setMessage(`Categorie assegnate a ${updated} sistemi; etichetta generica rimossa da ${cleaned} schede già classificate.`);
        current = await api('/admin/classification/preview'); setPreview(current);
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); onSaved(); }
  }
  const matches = record => `${record.manufacturer} ${record.model_name}`.toLocaleLowerCase('it').includes(query.toLocaleLowerCase('it'));
  const proposals = preview?.proposals.filter(matches) || [];
  const unresolved = preview?.unresolved_records.filter(matches) || [];
  return <section className="panel classification-panel" aria-label="Categorie del catalogo">
    <h2>Categorie del catalogo</h2>
    <p>Le schede generiche vengono classificate all’avvio e dopo le importazioni quando il modello o i dati disponibili permettono di riconoscerne la famiglia. Le categorie specifiche già presenti vengono conservate.</p>
    <p>Le assegnazioni sono editoriali e non costituiscono una verifica storica. «Calcolatore» viene rimosso quando è ridondante.</p>
    <button disabled={busy} onClick={refresh}>Aggiorna analisi categorie</button>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!preview && !error && <p>Analisi delle categorie…</p>}
    {preview && <>
      <section aria-label="Riepilogo categorie">
        <p>{preview.catalog_total} sistemi in catalogo. {preview.generic_only} senza una categoria specifica.</p>
        <p>{preview.total} assegnazioni proposte; {preview.unresolved} sistemi da esaminare; {preview.cleanup_count} etichette generiche ridondanti.</p>
        <ul>{Object.entries(preview.current_categories).sort(([a], [b]) => a.localeCompare(b)).map(([name, count]) => <li key={name}>{name}: {count}</li>)}</ul>
      </section>
      <label className="admin-field"><span>Filtra i sistemi da classificare</span><input value={query} onChange={e => setQuery(e.target.value)} /></label>
      <h3>Assegnazioni proposte</h3>
      <p>{proposals.length} risultati. Sono mostrati i primi 50.</p>
      <ul>{proposals.slice(0, 50).map(p => <li key={p.id}><b>{p.manufacturer} · {p.model_name} → {p.category}</b><p>{p.method}. {p.excerpt || p.rule}</p>
        {p.reference_url && <a href={p.reference_url} target="_blank" rel="noreferrer">Riferimento tecnico già associato</a>}</li>)}</ul>
      <button disabled={busy || !(preview.total || preview.cleanup_count)} onClick={apply}>Applica la classificazione al catalogo</button>
      <p>Il pulsante applica tutte le proposte, anche quelle escluse dal filtro. Fotografie, prezzi, descrizioni e specifiche restano conservati.</p>
      <section aria-label="Sistemi da esaminare"><h3>Sistemi da esaminare</h3>
        <p>{unresolved.length} risultati. Sono mostrati i primi 50. Per questi sistemi serve una scelta manuale supportata dalle fonti.</p>
        <ul>{unresolved.slice(0, 50).map(p => <li key={p.id}><b>{p.manufacturer} · {p.model_name}</b>{' '}
          <button disabled={busy} onClick={() => onEditComputer(p.id)}>Modifica categorie · {p.model_name}</button></li>)}</ul>
      </section>
    </>}
  </section>;
}
