import React, { useState } from 'react';
import { api } from './api.js';

const labels = { clarify: 'Unità chiarita', correct: 'Quantità corretta', annotate: 'Indicazione non quantificabile' };
const quantity = value => `${value.numeric_value ?? value.text_value ?? ''}${value.unit ? ` ${value.unit}` : ''}`;

export default function UnitReviewPanel({ onSaved }) {
  const [plan, setPlan] = useState(null);
  const [filter, setFilter] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function inspect() { setPlan(await api('/admin/catalog-quality/units')); }
  async function action(work) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const visible = plan?.changes.filter(row => row.model.toLocaleLowerCase('it').includes(filter.toLocaleLowerCase('it'))) || [];
  return <section className="panel" aria-label="Revisione delle unità di memoria">
    <h3>Unità di memoria</h3>
    <p>Controlla le decisioni documentate per modello e configurazione. Le indicazioni non quantificabili restano annotazioni consultabili. Originali e stati di verifica sono conservati.</p>
    <button disabled={busy} onClick={() => action(inspect)}>Controlla unità di memoria</button>
    {plan && <>
      <p>{plan.summary.documented_corrections} modifiche su {plan.summary.affected_computers} sistemi: {plan.summary.units_clarified} chiarimenti delle unità, {plan.summary.quantities_corrected} correzioni delle quantità e {plan.summary.annotations_proposed} annotazioni.</p>
      <p>{plan.summary.remaining_entries} specifiche ancora ambigue dopo le modifiche proposte. {plan.summary.unquantified_entries} indicazioni non quantificabili, elencate separatamente.</p>
      <p>{plan.summary.partially_quantified_entries} specifiche con una parte documentata e una parte ancora da approfondire.</p>
      <a href="/api/admin/catalog-quality/units/report" download>Scarica il resoconto con originali e fonti</a>
      {plan.changes.length > 0 && <>
        <label>Filtra le proposte per modello <input value={filter} onChange={event => setFilter(event.target.value)} /></label>
        <details><summary>Valori prima e dopo ({visible.length})</summary>
          {visible.map(row => <section className="panel" key={row.id}>
            <h4>{row.model} · {row.before.component_type}</h4>
            <p>{labels[row.action]}: {quantity(row.before)} → {quantity(row.after)}</p>
            <p>{typeof row.interpretation === 'string' ? row.interpretation : JSON.stringify(row.interpretation)}</p>
            <ul>{row.sources.map((source, index) => <li key={`${source.url}-${index}`}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></li>)}</ul>
          </section>)}
        </details>
        <button disabled={busy} onClick={() => action(async () => {
          const result = await api('/admin/catalog-quality/units/apply', { method: 'POST', body: JSON.stringify({ token: plan.token }) });
          await inspect(); onSaved(); setMessage(`Revisione applicata a ${result.updated} specifiche. Stati di verifica conservati.`);
        })}>Applica la revisione documentata delle unità</button>
      </>}
      {plan.unquantified.length > 0 && <details><summary>Indicazioni non quantificabili ({plan.unquantified.length})</summary>
        <ul>{plan.unquantified.map(row => <li key={row.id}><b>{row.model}</b>: {row.annotation} {row.reason}</li>)}</ul>
      </details>}
      {plan.partially_quantified.length > 0 && <details><summary>Quantità documentate solo in parte ({plan.partially_quantified.length})</summary>
        <ul>{plan.partially_quantified.map(row => <li key={row.id}><b>{row.model}</b>: {row.value}</li>)}</ul>
      </details>}
      {plan.remaining.length > 0 && <details><summary>Ambiguità ancora da esaminare ({plan.remaining.length})</summary>
        <ul>{plan.remaining.map(row => <li key={row.id}>{row.manufacturer} · {row.model}: {quantity(row.values)} — {row.reason}</li>)}</ul>
      </details>}
    </>}
    {error && <p role="alert" className="inline-error">{error}</p>}
    {message && <p role="status" className="inline-success">{message}</p>}
  </section>;
}
