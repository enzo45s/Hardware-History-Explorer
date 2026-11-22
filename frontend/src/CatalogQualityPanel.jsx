import React, { useState } from 'react';
import { api } from './api.js';
import UnitReviewPanel from './UnitReviewPanel.jsx';
import './imports.css';

export default function CatalogQualityPanel({ onSaved }) {
  const [ram, setRam] = useState(null);
  const [variants, setVariants] = useState(null);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function action(work) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function inspectRam() { setRam(await api('/admin/catalog-quality/ram')); }
  async function inspectVariants() {
    const data = await api('/admin/catalog-quality/variants');
    setVariants(data); setSelected(data.groups.map(group => group.target_id));
  }
  async function applyVariants() {
    const pending = new Set(selected);
    let plan = variants, removed = 0, renamed = 0;
    while (pending.size) {
      const chunk = plan.groups.filter(group => pending.has(group.target_id)).slice(0, 100).map(group => group.target_id);
      if (!chunk.length) throw new Error('Alcune schede sono cambiate: analizza nuovamente i nomi rimanenti.');
      const result = await api('/admin/catalog-quality/variants/apply', { method: 'POST', body: JSON.stringify({ token: plan.token, target_ids: chunk }) });
      removed += result.removed; renamed += result.renamed;
      chunk.forEach(id => pending.delete(id));
      plan = await api('/admin/catalog-quality/variants');
      setVariants(plan); setSelected([...pending]); setRam(null); onSaved();
      setMessage(`Accorpate ${removed} schede. Aggiornati ${renamed} nomi. Configurazioni e dati originali conservati.`);
    }
  }
  return <section className="imports">
    <h2>RAM e varianti dei modelli</h2>
    <UnitReviewPanel onSaved={onSaved} />
    <section className="panel" aria-label="Controllo RAM">
      <h3>Quantità di memoria mancanti</h3>
      <p>Controlla le quantità RAM presenti e recupera i dati disponibili da fonti documentate o da importazioni già applicate. Opzioni, limiti massimi, intervalli e unità ambigue restano distinti dalla dotazione di base.</p>
      <button disabled={busy} onClick={() => action(inspectRam)}>Controlla RAM mancanti</button>
      {ram && <>
        <p>{ram.total} sistemi. Senza quantità RAM: <b>{ram.without_ram}</b>. Recuperabili: <b>{ram.proposals.length}</b>. Ancora senza un dato utilizzabile: <b>{ram.unresolved}</b>.</p>
        {ram.proposals.length > 0 && <>
          <ul>{ram.proposals.map((row, index) => <li key={index}><b>{row.model_name}</b> · {row.configuration}: {row.value} · <a href={row.source.url} target="_blank" rel="noopener noreferrer">{row.source.title}</a></li>)}</ul>
          <button disabled={busy} onClick={() => action(async () => {
            const result = await api('/admin/catalog-quality/ram/apply', { method: 'POST', body: JSON.stringify({ token: ram.token }) });
            await inspectRam(); onSaved(); setMessage(`RAM aggiunta a ${result.updated} sistemi. I dati restano da verificare.`);
          })}>Completa RAM documentata</button>
        </>}
        {ram.examples.length > 0 && <details><summary>Sistemi ancora da approfondire</summary><ul>{ram.examples.map(row => <li key={row.id}>{row.manufacturer} · {row.model_name}</li>)}</ul><p>Primi {ram.examples.length} casi. Non viene attribuita RAM dalla sola appartenenza a una famiglia.</p></details>}
      </>}
    </section>
    <section className="panel" aria-label="Accorpamento varianti">
      <h3>Una scheda, più configurazioni</h3>
      <p>Unifica i modelli con attributi tra parentesi, sigle tra parentesi quadre e varianti PAL/NTSC o 50/60 Hz. La regola vale per tutto il catalogo. I dati originali e le configurazioni hardware restano conservati.</p>
      <p>Foto, specifiche, fonti e prezzi sono conservati. I prezzi rimangono associati alla variante originale. Gli alias impediscono di ricreare le stesse schede nei successivi import.</p>
      <button disabled={busy} onClick={() => action(inspectVariants)}>Analizza varianti da accorpare</button>
      {variants && <>
        <p>{variants.groups.length} nomi da sistemare; {variants.removed} schede duplicate da accorpare. Sono inclusi i nomi con attributi presenti in una sola scheda.</p>
        {variants.groups.map(group => <section key={group.target_id} className="panel">
          <label><input type="checkbox" disabled={busy} checked={selected.includes(group.target_id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, group.target_id] : ids.filter(id => id !== group.target_id))} /> {group.manufacturer} · <b>{group.name}</b></label>
          <p>{group.reason}</p><ul>{group.variants.map(name => <li key={name}>{name}</li>)}</ul>
        </section>)}
        {variants.groups.length > 0 && <button disabled={busy || !selected.length} onClick={() => action(applyVariants)}>Accorpa i gruppi selezionati</button>}
      </>}
    </section>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {message && <p role="status" className="inline-success">{message}</p>}
  </section>;
}
