import React from 'react';

export default function ReleasePanels({ computer, renderSource }) {
  const releases = computer.display_releases ?? computer.releases;
  const price = row => row.price != null ? `${row.price}${row.currency ? ' ' + row.currency : ''}` : 'Prezzo non disponibile';
  return <>
    {!releases.some(row => row.price != null) && <p className="muted">Nessun prezzo documentato presente in questa scheda. Le fonti importate possono non riportarlo; non viene stimato automaticamente.</p>}
    {releases.map(row => <section className="panel" key={row.id} aria-label={'Commercializzazione · ' + row.market}>
      <b>{row.market}</b>
      <p>{row.release_date || 'Data non disponibile'} · {price(row)}</p>
      {row.discontinuation_date && <p className="muted">Fine commercializzazione: {row.discontinuation_date}</p>}
      {row.price_type && <p className="muted">Tipo di prezzo: {row.price_type}</p>}
      {row.date_scope === 'model' && <p className="muted">Data del modello: la fonte della data non specifica il mercato.</p>}
      {row.sources.map(source => renderSource(source))}
      {row.merged && <details>
        <summary>Provenienza dei dati accorpati</summary>
        {row.original_releases.map(original => <div key={original.id}>
          <p><b>{original.market}</b> · {original.release_date || 'Data non disponibile'} · {price(original)}</p>
          {original.discontinuation_date && <p>Fine commercializzazione: {original.discontinuation_date}</p>}
          {original.price_type && <p>Tipo di prezzo: {original.price_type}</p>}
          {original.sources.map(source => renderSource(source))}
        </div>)}
      </details>}
    </section>)}
  </>;
}
