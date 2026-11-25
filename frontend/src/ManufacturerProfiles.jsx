import React, { useEffect, useLayoutEffect, useState } from 'react';
import { ArrowLeft, ChevronRight, ExternalLink, Factory, Search, BookOpen } from 'lucide-react';
import { api, allComputers, latestRequest } from './api.js';
import ComputerCard from './ComputerCard.jsx';
import './manufacturers.css';

const httpUrl = value => { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; } catch { return null; } };
const normalized = value => (value || '').normalize('NFKD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('it');
const sortNames = (a, b) => a.name.localeCompare(b.name, 'it', { sensitivity: 'base', numeric: true });
const years = range => range?.length === 2 ? range[0] === range[1] ? String(range[0]) : range.join('–') : null;

export function ManufacturerLogo({ manufacturer, large = false }) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [manufacturer.logo_url]);
  const src = httpUrl(manufacturer.logo_url);
  return <div className={'manufacturer-logo' + (large ? ' large' : '')}>
    {src && !broken ? <img src={src} alt={'Logo di ' + manufacturer.name} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      : <div className="manufacturer-placeholder" aria-label={'Produttore ' + manufacturer.name}><Factory size={large ? 44 : 32} /><span>{manufacturer.name.slice(0, 2).toLocaleUpperCase('it')}</span></div>}
  </div>;
}

export default function ManufacturerProfiles({ id, onOpen, onBack, onOpenComputer, revision, Cover }) {
  const [manufacturers, setManufacturers] = useState([]);
  const [profile, setProfile] = useState(null), [computers, setComputers] = useState([]);
  const [query, setQuery] = useState(''), [country, setCountry] = useState(''), [sort, setSort] = useState('name');
  const [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setLoading(true); setError(''); setProfile(null); setComputers([]);
    return latestRequest(signal => id == null ? api('/manufacturers', { signal }) : Promise.all([
      api('/manufacturers/' + id + '/profile', { signal }), allComputers(new URLSearchParams({ manufacturer_id: String(id), sort: 'year' }), signal)
    ]), data => { if (id == null) setManufacturers(data); else { setProfile(data[0]); setComputers(data[1]); } setLoading(false); }, e => { setError(e.message); setLoading(false); });
  }, [id, revision, attempt]);
  useLayoutEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); }, [id]);
  if (error) return <>{id != null && <button className="back" onClick={onBack}><ArrowLeft size={16} />Tutti i produttori</button>}<p role="alert" className="error">{error} <button onClick={() => setAttempt(value => value + 1)}>Riprova</button></p></>;
  if (id != null) {
    if (loading || !profile) return <p role="status">Caricamento del produttore…</p>;
    const facts = [['Denominazione', profile.legal_name], ['Paese', profile.country], ['Sede storica', profile.headquarters],
      ['Fondazione', profile.founded], ['Cessazione', profile.ceased], ['Fondatori', profile.founders]].filter(([, value]) => value);
    return <>
      <button className="back" onClick={onBack}><ArrowLeft size={16} />Tutti i produttori</button>
      <div className="manufacturer-heading"><ManufacturerLogo manufacturer={profile} large /><div><div className="eyebrow">STORIA DEI PRODUTTORI</div><h1>{profile.name}</h1><p className="lead">{profile.computer_count} sistemi nell’archivio{years(profile.catalog_year_range) ? ' · ' + years(profile.catalog_year_range) : ''}</p></div></div>
      <div className="manufacturer-profile-grid"><section className="panel manufacturer-story" aria-label="Profilo dell’azienda"><h2>Profilo storico</h2>
        {profile.description ? <p className="manufacturer-description">{profile.description}</p> : <p className="muted">Il profilo storico è ancora da completare. Qui puoi già esplorare i sistemi presenti nell’archivio.</p>}
        {profile.description_author && <p className="muted">Testo basato su {httpUrl(profile.description_source_url) ? <a href={httpUrl(profile.description_source_url)} target="_blank" rel="noopener noreferrer">{profile.description_author}</a> : profile.description_author}{httpUrl(profile.description_license_url) && <> · <a href={httpUrl(profile.description_license_url)} target="_blank" rel="noopener noreferrer">Licenza del testo</a></>}</p>}
        {!!facts.length && <dl className="manufacturer-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
        {httpUrl(profile.website) && <a className="source" href={httpUrl(profile.website)} target="_blank" rel="noopener noreferrer">Sito web <ExternalLink size={14} /></a>}
      </section><section className="panel manufacturer-attribution" aria-label="Fonti del produttore"><h2>Fonti</h2>
        {profile.sources.length ? profile.sources.map(s => httpUrl(s.url) ? <a className="source" key={s.id} href={httpUrl(s.url)} target="_blank" rel="noopener noreferrer"><BookOpen size={14} />{s.title}<ExternalLink size={13} /></a> : <p className="source" key={s.id}><BookOpen size={14} />{s.title}</p>) : <p className="muted">Nessuna fonte aziendale ancora associata.</p>}
        {profile.logo_url && <div className="manufacturer-logo-credits"><h3>Logo</h3>{profile.logo_author && <p>{profile.logo_author}</p>}{profile.logo_license && <p>{profile.logo_license}</p>}
          {httpUrl(profile.logo_source_url) && <a className="source" href={httpUrl(profile.logo_source_url)} target="_blank" rel="noopener noreferrer">Fonte del logo <ExternalLink size={13} /></a>}
          {httpUrl(profile.logo_license_url) && <a className="source" href={httpUrl(profile.logo_license_url)} target="_blank" rel="noopener noreferrer">Condizioni di utilizzo <ExternalLink size={13} /></a>}
        </div>}
      </section></div>
      <div className="section-title">Sistemi nell’archivio <span>{computers.length} sistemi</span></div><p className="muted">Ordinati per prima commercializzazione. Il catalogo censito può rappresentare solo una parte della produzione dell’azienda.</p>
      {computers.length ? <div className="catalog-grid">{computers.map(c => <ComputerCard key={c.id} computer={c} Cover={Cover} onOpen={onOpenComputer} />)}</div> : <p className="empty">Non ci sono ancora sistemi associati a questo produttore.</p>}
    </>;
  }
  const countries = [...new Set(manufacturers.map(m => m.country).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'));
  const visible = manufacturers.filter(m => normalized(m.name + ' ' + (m.legal_name || '')).includes(normalized(query)) && (!country || m.country === country))
    .sort(sort === 'count' ? (a, b) => b.computer_count - a.computer_count || sortNames(a, b) : sortNames);
  return <><div className="eyebrow">LE AZIENDE CHE HANNO COSTRUITO L’INFORMATICA</div><h1>Produttori</h1><p className="lead">Esplora le aziende e scopri i loro sistemi, dalle origini dell’informatica ai personal computer.</p>
    <div className="filters"><div className="search"><Search size={17} /><input aria-label="Cerca un produttore" placeholder="Cerca un produttore…" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <select aria-label="Paese del produttore" value={country} onChange={e => setCountry(e.target.value)}><option value="">Tutti i paesi</option>{countries.map(c => <option key={c}>{c}</option>)}</select>
      <select aria-label="Ordina produttori" value={sort} onChange={e => setSort(e.target.value)}><option value="name">Nome A–Z</option><option value="count">Numero di sistemi</option></select>
    </div><p className="muted" role="status">{loading ? 'Caricamento produttori…' : visible.length + ' produttori visualizzati su ' + manufacturers.length}</p>
    {!loading && !visible.length && <p className="empty">Nessun produttore corrisponde alla ricerca.</p>}
    <div className="manufacturer-grid">{visible.map(m => <article className="panel manufacturer-card" key={m.id}><ManufacturerLogo manufacturer={m} /><h2>{m.name}</h2>
      {(m.country || m.founded) && <p className="muted">{[m.country, m.founded && 'Dal ' + m.founded].filter(Boolean).join(' · ')}</p>}
      {m.description && <p className="manufacturer-card-intro">{m.description}</p>}{m.description_author && <small className="muted">{httpUrl(m.description_source_url) ? <a href={httpUrl(m.description_source_url)} target="_blank" rel="noopener noreferrer">{m.description_author}</a> : m.description_author}{httpUrl(m.description_license_url) && <> · <a href={httpUrl(m.description_license_url)} target="_blank" rel="noopener noreferrer">Licenza</a></>}</small>}<div className="card-foot"><span>{m.computer_count} sistemi</span><button onClick={() => onOpen(m.id)} aria-label={'Esplora ' + m.name}>Esplora <ChevronRight size={15} /></button></div>
    </article>)}</div>
  </>;
}
