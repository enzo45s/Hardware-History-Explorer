import React from 'react';
import { commercializationSource } from './computer-sources.js';
import { releaseGroups } from './release-groups.js';

export default function ReleasePanels({ computer, renderSource }) {
  const releases = computer.display_releases ?? computer.releases;
  const price = row => row.price != null ? `${row.price}${row.currency ? ' ' + row.currency : ''}` : 'Prezzo non disponibile';
  return <>
    {!releases.some(row => row.price != null) && <p className="muted">Nessun prezzo documentato presente in questa scheda. Le fonti importate possono non riportarlo; non viene stimato automaticamente.</p>}
    {releaseGroups(releases).map(group => <section className="panel" key={group.id} aria-label={'Commercializzazione · ' + group.market}>
      <b>{group.market}</b>
      {group.releases.map(row => {
        const source = commercializationSource(row);
        const countries = (row.price != null ? row.price_countries : row.countries)?.filter(country => country !== 'Europa');
        return <div key={row.id}>
          {row.model_variant && <p className="muted">Configurazione: {row.display_model_variant ?? row.model_variant}</p>}
          {group.releases.length > 1 && countries?.length > 0 && <p className="muted">{countries.join(', ')}</p>}
          <p>{row.release_date || 'Data non disponibile'} · {price(row)}</p>
          {row.discontinuation_date && <p className="muted">Fine commercializzazione: {row.discontinuation_date}</p>}
          {row.price_type && <p className="muted">Tipo di prezzo: {row.price_type}</p>}
          {source && renderSource(source)}
        </div>;
      })}
    </section>)}
  </>;
}
