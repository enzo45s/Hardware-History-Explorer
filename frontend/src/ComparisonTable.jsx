import React, { useEffect, useId, useState } from 'react';
import { api, latestRequest } from './api.js';
import { comparisonSpecifications, selectedConfiguration } from './comparison-specs.js';
import { displayDescription, displayConfigurationName } from './catalog-display.js';
import './comparison-table.css';

export default function ComparisonTable({ ids, configurations, onConfigurationChange, Cover }) {
  const [response, setResponse] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const idsKey = ids.join(',');
  const requestKey = idsKey + ':' + attempt;
  const tableId = useId();
  useEffect(() => latestRequest(signal => api('/compare?ids=' + idsKey, { signal }),
    data => setResponse({ key: requestKey, data }), error => setResponse({ key: requestKey, error: error.message })), [requestKey]);
  if (response?.key !== requestKey) return <div className="panel" role="status">Caricamento del confronto…</div>;
  if (response.error) return <div className="panel comparison-table-error"><p role="alert">{response.error}</p><button onClick={() => setAttempt(value => value + 1)}>Riprova confronto</button></div>;
  const data = response.data;
  const specifications = data.map(computer => comparisonSpecifications(computer, configurations[computer.id]));
  const rows = new Map(specifications.flatMap(specs => [...specs].map(([key, spec]) => [key, spec.label])));
  const aggregated = data.some(computer => computer.configurations.length > 1 && !selectedConfiguration(computer, configurations[computer.id]));
  return <section className="comparison-results">
    {aggregated && <p className="comparison-variant-help" role="note">I valori raggruppati appartengono a configurazioni diverse. Scegli una variante per confrontare una combinazione precisa; i dati mancanti non vengono dedotti dalle altre configurazioni.</p>}
    <div className="panel compare-scroll"><table className="comparison"><caption className="comparison-caption">Confronto dei sistemi e delle configurazioni selezionate</caption>
      <thead><tr><th scope="col">Caratteristica</th>{data.map(computer => <th scope="col" key={computer.id}>
        <div className="comparison-system-name">{computer.model_name}</div>
        <label className="comparison-config-label" htmlFor={tableId + '-' + computer.id}>Configurazione</label>
        <select id={tableId + '-' + computer.id} className="comparison-config-select" aria-label={'Configurazione di ' + computer.model_name}
          disabled={!computer.configurations.length} value={selectedConfiguration(computer, configurations[computer.id])?.id ?? 'all'}
          onChange={event => onConfigurationChange(computer.id, event.target.value)}>
          <option value="all">{computer.configurations.length ? `Tutte le configurazioni (${computer.configurations.length})` : 'Nessuna configurazione disponibile'}</option>
          {computer.configurations.map(config => <option key={config.id} value={config.id}>{displayConfigurationName(config)}</option>)}
        </select>
        {selectedConfiguration(computer, configurations[computer.id]) && displayDescription(selectedConfiguration(computer, configurations[computer.id])) && <p className="comparison-config-description">{displayDescription(selectedConfiguration(computer, configurations[computer.id]))}</p>}
      </th>)}</tr></thead>
      <tbody>
        <tr><th scope="row">Fotografia</th>{data.map(c => <td key={c.id}><Cover src={c.image_url} name={c.model_name} year={c.year} className="compare-photo" /></td>)}</tr>
        <tr><th scope="row">Produttore</th>{data.map(c => <td key={c.id}>{c.manufacturer}</td>)}</tr>
        <tr><th scope="row">Prima commercializzazione</th>{data.map(c => <td key={c.id}>{c.first_release || '—'}</td>)}</tr>
        <tr><th scope="row">Categoria</th>{data.map(c => <td key={c.id}>{c.categories.join(', ') || '—'}</td>)}</tr>
        {[...rows].map(([key, label]) => <tr key={key}><th scope="row">{label}</th>{data.map((computer, index) => {
          const value = specifications[index].get(key);
          return <td key={computer.id}><span className="comparison-spec-value">{value?.text ?? '—'}</span>
            {value?.partial && <small className="comparison-partial">Dato presente in {value.coverage} di {value.total} configurazioni</small>}
          </td>;
        })}</tr>)}
      </tbody>
    </table></div>
  </section>;
}
