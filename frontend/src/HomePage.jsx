import React, { useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, BookOpen, Clock3, Database, Factory, GitCompareArrows, Bot } from 'lucide-react';
import { api, latestRequest } from './api.js';
import { displayDescription } from './catalog-display.js';
import './home.css';

const httpUrl = value => {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
};
const number = value => value == null ? '—' : value.toLocaleString('it-IT');

function TextCredit({ attribution }) {
  if (!attribution) return null;
  return <p className="home-text-credit">Testo: {httpUrl(attribution.url)
    ? <a href={httpUrl(attribution.url)} target="_blank" rel="noopener noreferrer">{attribution.title} · Collaboratori di Wikipedia</a>
    : attribution.title}{httpUrl(attribution.license_url) && <> · <a href={httpUrl(attribution.license_url)} target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a></>}</p>;
}

export default function HomePage({ revision, manufacturers, onNavigate, onOpenComputer, onOpenManufacturer, Cover }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setError(''); setData(null);
    return latestRequest(signal => api('/home', { signal }), result => setData(result), e => setError(e.message));
  }, [revision, attempt]);
  const featured = data?.featured || [], hero = data?.spotlight, cover = hero?.cover;
  const display = featured;
  // Existing identities only; these are direct profile links, not a synthetic roster.
  const preferred = ['olivetti', 'apple', 'ibm', 'commodore', 'digital equipment corporation', 'sun microsystems'];
  const makers = [...manufacturers].sort((a, b) => {
    const rank = name => { const i = preferred.indexOf(name.toLocaleLowerCase('it')); return i < 0 ? Infinity : i; };
    return rank(a.name) - rank(b.name) || a.name.localeCompare(b.name, 'it');
  }).slice(0, 6);
  return <div className="home-page">
    <section className="home-hero" aria-labelledby="home-title">
      <div className="home-introduction"><p className="eyebrow"><span className="home-dot" />BENVENUTO NEL MUSEO DIGITALE</p>
        <h1 id="home-title">Ogni computer,<br /><em>una storia.</em></h1>
        <p className="home-intro">Le macchine, le persone e le idee che hanno trasformato il nostro mondo. Esplora la storia dell’informatica, un sistema alla volta.</p>
        <div className="home-actions"><button className="home-button primary" onClick={() => onNavigate('catalog')}>Entra nel catalogo <ArrowRight size={16} /></button>
          <button className="home-button" onClick={() => onNavigate('timeline')}><Clock3 size={16} />Percorri la timeline</button></div>
        <p className="home-micro-note"><BookOpen size={13} />Un archivio da esplorare, con le fonti da consultare.</p>
      </div>
      <div className="home-featured">
        {hero ? <><article className="home-showcase" aria-label={'In vetrina: ' + hero.model_name}>
          <div className="home-showcase-image"><span className="home-museum-label">IN VETRINA{hero.categories[0] ? ' / ' + hero.categories[0].toLocaleUpperCase('it') : ''}</span>
            {hero.year && <span className="home-exhibit-year" aria-hidden="true">{hero.year}</span>}
            <Cover src={hero.image_url} name={hero.model_name} year={hero.year} className="home-hero-cover" /></div>
          <div className="home-showcase-caption"><div><h2>{hero.model_name}</h2><p>{[hero.manufacturer, hero.first_release || 'Data non disponibile'].join(' · ')}</p></div>
            <button onClick={() => onOpenComputer(hero.id)} aria-label={'Scopri ' + hero.model_name}><ArrowUpRight size={19} /></button></div>
        </article>{cover && <p className="home-photo-credit">{cover.author ? 'Foto: ' + cover.author : 'Autore non indicato'} · {cover.license_name || 'Licenza non indicata'}
          {httpUrl(cover.source_url) && <> · <a href={httpUrl(cover.source_url)} target="_blank" rel="noopener noreferrer">Fonte della foto</a></>}
          {httpUrl(cover.license_url) && <> · <a href={httpUrl(cover.license_url)} target="_blank" rel="noopener noreferrer">Licenza</a></>}</p>}</>
          : <div className="home-empty-showcase"><BookOpen size={35} /><h2>La collezione comincia da qui.</h2><p>{error ? 'La vetrina non è disponibile al momento.' : data ? 'Esplora il catalogo o aggiungi i primi sistemi dall’amministrazione.' : 'Caricamento della collezione…'}</p></div>}
      </div>
    </section>
    {error && <p className="error" role="alert">{error} <button onClick={() => setAttempt(v => v + 1)}>Riprova</button></p>}
    <section className="home-stats" aria-label="La collezione in numeri" aria-busy={!data && !error}>
      <div className="home-stat"><strong>{number(data?.summary.systems)}</strong><span>sistemi<br />da scoprire</span></div>
      <div className="home-stat"><strong>{number(data?.summary.manufacturers)}</strong><span>produttori<br />e protagonisti</span></div>
      <div className="home-stat home-source-stat"><BookOpen size={22} /><span><b>La storia, attraverso le fonti</b>Documenti, immagini e testimonianze.</span></div>
    </section>
    <section className="home-paths-section" aria-labelledby="home-paths-title"><div className="home-section-heading"><div><p className="eyebrow">IL TUO PERCORSO COMINCIA QUI</p><h2 id="home-paths-title">Da dove vuoi iniziare?</h2></div><p>Tre modi per attraversare la collezione.</p></div>
      <div className="home-paths">{[
        ['timeline', Clock3, 'Attraversa le epoche', 'Dalle grandi macchine ai computer sulle nostre scrivanie.', 'Esplora la timeline'],
        ['catalog', Database, 'Scopri le macchine', 'Modelli, caratteristiche e fotografie: entra nella collezione.', 'Visita il catalogo'],
        ['manufacturers', Factory, 'Conosci i protagonisti', 'Le aziende e i progetti che hanno dato forma all’informatica.', 'Esplora i produttori']
      ].map(([target, Icon, title, text, action], index) => <button className="home-path" key={target} onClick={() => onNavigate(target)}>
        <span className="home-path-top"><Icon size={20} /><span>0{index + 1}</span></span><h3>{title}</h3><p>{text}</p><span className="home-path-foot">{action}<ArrowRight size={16} /></span>
      </button>)}</div>
    </section>
    {!!featured.length && <section className="home-collection" aria-labelledby="home-collection-title"><div className="home-section-heading"><div><p className="eyebrow">DALLA COLLEZIONE</p><h2 id="home-collection-title">Macchine che raccontano.</h2></div><button className="home-link" onClick={() => onNavigate('catalog')}>Il catalogo completo <ArrowRight size={15} /></button></div>
      <div className="home-exhibits">{display.map(c => <article className="home-exhibit" key={c.id}>
        <div className="home-exhibit-image"><Cover src={c.image_url} name={c.model_name} year={c.year} className="home-card-cover" /><span className="home-date">{c.first_release || 'Data non disponibile'}</span></div>
        <div className="home-exhibit-info"><p className="home-category">{c.categories[0] || 'CALCOLATORE'}</p><h3>{c.model_name}</h3><p className="home-card-caption">{displayDescription(c) || 'Esplora le informazioni disponibili nella scheda del sistema.'}</p><TextCredit attribution={c.description_attribution} />
          <button className="home-exhibit-open" onClick={() => onOpenComputer(c.id)} aria-label={'Scopri la storia di ' + c.model_name}>Scopri la storia <ArrowRight size={15} /></button></div>
      </article>)}</div></section>}
    <section className="home-timeline" aria-labelledby="home-time-title"><div className="home-section-heading"><div><p className="eyebrow">UN’INVENZIONE DOPO L’ALTRA</p><h2 id="home-time-title">Un viaggio lungo decenni.</h2><p>Ogni epoca ha cambiato il nostro modo di immaginare il computer.</p></div><button className="home-link" onClick={() => onNavigate('timeline')}>Inizia a esplorare <ArrowRight size={15} /></button></div>
      <div className="home-eras">{[
        ['1950–1969', 'Le grandi macchine e il calcolo da tavolo', '1950', '1969'],
        ['1970–1979', 'La rivoluzione dei microcomputer', '1970', '1979'],
        ['1980–1989', 'L’informatica entra nelle case', '1980', '1989'],
        ['1990 e oltre', 'Workstation, portatili e nuove connessioni', '1990', '']
      ].map(([label, text, from, to]) => <button className="home-era" key={label} onClick={() => onNavigate('timeline', { year_from: from, year_to: to })} aria-label={'Esplora il periodo ' + label}><strong>{label}</strong><span>{text}</span></button>)}</div>
    </section>
    <section className="home-makers"><div><p className="eyebrow">LE AZIENDE DIETRO LE MACCHINE</p><h2>Persone, visioni, imprese.</h2><p>Dai pionieri alle aziende che tutti conosciamo: scopri chi ha immaginato e costruito questi sistemi.</p></div><div className="home-maker-names">{makers.map(m => <button key={m.id} onClick={() => onOpenManufacturer(m.id)} aria-label={'Scopri il produttore ' + m.name}>{m.name}</button>)}<button className="home-link" onClick={() => onNavigate('manufacturers')}>Tutti i produttori <ArrowRight size={15} /></button></div></section>
    <section className="home-tools"><p>Vuoi guardare più da vicino?</p><div><button className="home-link" onClick={() => onNavigate('compare')}><GitCompareArrows size={16} />Confronta i sistemi <ArrowUpRight size={14} /></button><button className="home-link" onClick={() => onNavigate('assistant')}><Bot size={16} />Interroga l’archivio <ArrowUpRight size={14} /></button></div></section>
    <footer className="home-footer">HHE · Hardware History Explorer<span>Un archivio per la memoria dell’informatica.</span></footer>
  </div>;
}
