import React, { useEffect, useId, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { latestRequest } from './api.js';
import { comparisonSuggestions } from './comparison-api.js';
import './comparison-picker.css';

export default function ComparisonPicker({ selected, onSelect, onRemove }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [response, setResponse] = useState(null);
  const [active, setActive] = useState(-1);
  const [attempt, setAttempt] = useState(0);
  const input = useRef(null);
  const listId = useId();
  const selectedKey = selected.map(c => c.id).join(',');
  const term = query.trim();
  const full = selected.length >= 5;
  const requestKey = JSON.stringify([term, selectedKey, attempt]);
  const current = response?.key === requestKey ? response : null;
  const results = current?.items || [];
  const loading = Boolean(term) && !full && !current;
  const expanded = open && Boolean(term) && !full;

  useEffect(() => {
    setActive(-1);
    if (!term || full) return;
    let cancel = () => {};
    const timer = setTimeout(() => {
      cancel = latestRequest(signal => comparisonSuggestions(term, selectedKey ? selectedKey.split(',') : [], signal),
        data => { setResponse({ ...data, key: requestKey }); setActive(data.items.length ? 0 : -1); },
        error => setResponse({ items: [], key: requestKey, error: error.message }));
    }, 200);
    return () => { clearTimeout(timer); cancel(); };
  }, [requestKey]);

  useEffect(() => {
    if (active >= 0) document.getElementById(listId + '-' + active)?.scrollIntoView({ block: 'nearest' });
  }, [active, listId]);

  function choose(computer) {
    if (full || selected.some(c => c.id === computer.id)) return;
    onSelect(computer);
    setQuery(''); setOpen(false); setActive(-1);
    input.current?.focus();
  }
  function onKeyDown(event) {
    if (event.nativeEvent.isComposing) return;
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); setOpen(true);
      if (results.length) setActive(index => event.key === 'ArrowDown'
        ? (index + 1) % results.length : (index <= 0 ? results.length - 1 : index - 1));
    }
    if (event.key === 'Enter' && expanded && results[active]) {
      event.preventDefault(); choose(results[active]);
    }
  }
  const metadata = computer => [computer.manufacturer, computer.year].filter(v => v != null && v !== '').join(' · ');
  return <section className="panel comparison-picker" aria-label="Selezione sistemi da confrontare">
    <div className="comparison-search-title"><label htmlFor={listId + '-input'}>Cerca un sistema da aggiungere</label><span>{selected.length}/5 selezionati</span></div>
    <div className="comparison-autocomplete" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <div className="comparison-search-box"><Search size={19} aria-hidden="true" />
        <input id={listId + '-input'} ref={input} role="combobox" aria-autocomplete="list" aria-expanded={expanded}
          aria-controls={listId} aria-activedescendant={expanded && results[active] ? listId + '-' + active : undefined}
          aria-describedby={listId + '-help'} placeholder="Nome del modello o produttore…" autoComplete="off" maxLength={180}
          value={query} disabled={full} onChange={event => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)} onKeyDown={onKeyDown} />
        {query && <button type="button" aria-label="Cancella ricerca" onClick={() => { setQuery(''); setActive(-1); input.current?.focus(); }}><X size={17} /></button>}
      </div>
      {expanded && <div className="comparison-dropdown">
        {loading && <p role="status">Ricerca in corso…</p>}
        {current?.error && <div className="comparison-search-error"><p role="alert">{current.error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Riprova</button></div>}
        <ul id={listId} role="listbox" aria-label="Sistemi trovati" aria-busy={loading}>
          {results.map((computer, index) => <li key={computer.id} id={listId + '-' + index} role="option" aria-selected={active === index}
            className={active === index ? 'active' : ''} onPointerDown={event => event.preventDefault()}
            onMouseMove={() => setActive(index)} onClick={() => choose(computer)}>
            <b>{computer.model_name}</b><span>{metadata(computer)}</span>
          </li>)}
        </ul>
        {!loading && !current?.error && !results.length && <p role="status">Nessun sistema disponibile per questa ricerca.</p>}
        {current?.has_more && <p className="comparison-more">Mostrati i primi {results.length} risultati. Affina la ricerca per trovare gli altri.</p>}
      </div>}
    </div>
    <p id={listId + '-help'} className="comparison-help" role="status">{full
      ? 'Hai raggiunto il limite di 5 sistemi. Rimuovine uno per aggiungerne un altro.'
      : 'Scrivi per cercare nell’archivio. Seleziona un suggerimento con un clic oppure con le frecce e Invio.'}</p>
    {!!selected.length && <ul className="comparison-selected" aria-label="Sistemi selezionati">
      {selected.map(computer => <li key={computer.id}>
        <div><b>{computer.model_name}</b><small>{metadata(computer)}</small></div>
        <button type="button" aria-label={'Rimuovi ' + computer.model_name + ' dal confronto'} onClick={() => onRemove(computer.id)}><X size={16} /></button>
      </li>)}
    </ul>}
  </section>;
}
