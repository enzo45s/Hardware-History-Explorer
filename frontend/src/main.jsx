import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Search, Clock3, Database, BarChart3, GitCompareArrows, Bot, ChevronRight, ArrowLeft,
  ExternalLink, Monitor, BookOpen, Image as ImageIcon, Upload, Link as LinkIcon,
  Star, Trash2, Plus, X, RefreshCw, Camera, Info, Check, Images, Pencil
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import './style.css';
import ThemeSwitcher from './ThemeSwitcher.jsx';
import { api, allComputers, latestRequest } from './api.js';
import AdminPanel from './AdminPanel.jsx';
import ComparisonPicker from './ComparisonPicker.jsx';
import ComparisonTable from './ComparisonTable.jsx';
import { comparisonSummary } from './comparison-api.js';

const nav = [
  ['timeline', 'Timeline', Clock3], ['catalog', 'Catalogo', Database],
  ['analysis', 'Analisi', BarChart3], ['compare', 'Confronta', GitCompareArrows],
  ['assistant', 'Assistente AI', Bot], ['admin', 'Amministrazione', Pencil]
];

function SystemCover({ src, name, year, className = '' }) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [src]);
  return <div className={'system-cover ' + className}>
    {src && !broken ? <img src={src} alt={'Fotografia di ' + name} loading="lazy" onError={() => setBroken(true)} />
      : <div className="system-placeholder"><Monitor size={34} /><span>{year || 'FOTO'}</span></div>}
  </div>;
}

function Source({ s }) {
  return s.url
    ? <a className="source" href={s.url} target="_blank" rel="noopener noreferrer"><BookOpen size={14} />{s.title}<ExternalLink size={13} /></a>
    : <div className="source"><BookOpen size={14} />{s.title}</div>;
}

function Gallery({ computer }) {
  const images = computer.images || [];
  const [activeId, setActiveId] = useState(null);
  useEffect(() => setActiveId(null), [computer.id]);
  const active = images.find(i => i.id === activeId) || images[0];
  if (!images.length) return <div className="gallery-empty"><ImageIcon size={30} /><b>Nessuna fotografia ancora associata</b><span>Puoi aggiungere una foto dal dispositivo, tramite URL oppure cercarla su Wikimedia Commons.</span></div>;
  return <div className="gallery-box">
    <div className="gallery-feature">
      <img src={active.url} alt={active.caption || 'Fotografia di ' + computer.model_name} />
      {active.is_primary && <span className="cover-flag"><Star size={12} fill="currentColor" /> Copertina</span>}
    </div>
    {images.length > 1 && <div className="gallery-strip">{images.map(i =>
      <button type="button" key={i.id} className={'gallery-thumb ' + (active.id === i.id ? 'selected' : '')} onClick={() => setActiveId(i.id)} title={i.caption || 'Fotografia'}>
        <img src={i.thumbnail_url || i.url} alt={i.caption || 'Miniatura'} loading="lazy" />
      </button>)}</div>}
    <div className="gallery-credit">
      <b>{active.caption || 'Fotografia del sistema'}</b>
      <span>{[active.author && 'Autore: ' + active.author, active.license_name && 'Licenza: ' + active.license_name].filter(Boolean).join(' · ') || 'Autore e licenza non specificati'}</span>
      <div className="photo-links">
        {active.source_url && <a href={active.source_url} target="_blank" rel="noopener noreferrer">Fonte originale <ExternalLink size={12} /></a>}
        {active.license_url && <a href={active.license_url} target="_blank" rel="noopener noreferrer">Dettagli licenza <ExternalLink size={12} /></a>}
        <a href={active.url} target="_blank" rel="noopener noreferrer">Apri fotografia <ExternalLink size={12} /></a>
      </div>
    </div>
  </div>;
}

function ImageManager({ computer, onChanged }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('commons');
  const [query, setQuery] = useState(computer.manufacturer + ' ' + computer.model_name);
  const [results, setResults] = useState([]);
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [caption, setCaption] = useState('');
  const [author, setAuthor] = useState('');
  const [licenseName, setLicenseName] = useState('');
  const [licenseUrl, setLicenseUrl] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setQuery(computer.manufacturer + ' ' + computer.model_name); setResults([]); setMessage(''); }, [computer.id]);

  async function perform(action, success) {
    setBusy(true); setError(''); setMessage('');
    try { await action(); await onChanged(); setMessage(success); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function searchCommons(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage(''); setResults([]);
    try { const response = await api('/images/search?q=' + encodeURIComponent(query)); setResults(response.items); if (!response.items.length) setMessage('Nessuna foto trovata: prova con un nome più breve.'); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function addCommons(image) {
    await perform(() => api('/computers/' + computer.id + '/images', { method: 'POST', body: JSON.stringify({
      image_url: image.image_url, thumbnail_url: image.thumbnail_url, caption: image.title.replace(/^File:/, ''),
      author: image.author || null, license_name: image.license_name || null,
      license_url: image.license_url || null, source_url: image.source_url || null,
      is_primary: !computer.images?.length
    }) }), 'Fotografia aggiunta. Controlla sempre che rappresenti il modello corretto e che la licenza sia adatta.');
  }
  async function upload(e) {
    e.preventDefault();
    if (!file) { setError('Seleziona un file immagine.'); return; }
    const data = new FormData();
    data.append('file', file);
    if (caption) data.append('caption', caption);
    if (author) data.append('author', author);
    if (licenseName) data.append('license_name', licenseName);
    if (licenseUrl) data.append('license_url', licenseUrl);
    if (sourceUrl) data.append('source_url', sourceUrl);
    data.append('is_primary', String(isPrimary));
    await perform(() => api('/computers/' + computer.id + '/images/upload', { method: 'POST', body: data }), 'Immagine caricata sul server.');
  }
  async function link(e) {
    e.preventDefault();
    await perform(() => api('/computers/' + computer.id + '/images', { method: 'POST', body: JSON.stringify({
      image_url: url, caption, author, license_name: licenseName, license_url: licenseUrl || null,
      source_url: sourceUrl || null, is_primary: isPrimary
    }) }), 'Fotografia aggiunta tramite URL.');
  }
  async function makeCover(id) { await perform(() => api('/computers/' + computer.id + '/images/' + id + '/primary', { method: 'POST' }), 'Copertina aggiornata.'); }
  async function remove(id) {
    if (!window.confirm('Eliminare questa immagine dal sistema?')) return;
    await perform(() => api('/computers/' + computer.id + '/images/' + id, { method: 'DELETE' }), 'Immagine eliminata.');
  }
  return <section className="manager-section">
    <button className="manage-toggle" onClick={() => setOpen(v => !v)}><Images size={17} /> {open ? 'Chiudi gestione immagini' : 'Gestisci fotografie'} <ChevronRight size={16} className={open ? 'rotated' : ''} /></button>
    {open && <div className="panel manager-panel">
      <h3>Archivio fotografico · {computer.images?.length || 0} immagini</h3>
      <p className="muted">Scegli la fotografia principale: sarà mostrata nel catalogo e nella timeline. Le immagini sono associate solo a questo sistema.</p>
      {!!computer.images?.length && <div className="manage-images">{computer.images.map(i =>
        <div className="manage-image" key={i.id}>
          <img src={i.thumbnail_url || i.url} alt={i.caption || 'Fotografia'} loading="lazy" />
          <div className="manage-image-info"><b>{i.caption || 'Senza didascalia'}</b><span>{i.storage === 'local' ? 'Caricata sul server' : 'Immagine esterna'} · {i.license_name || 'Licenza non indicata'}</span></div>
          <div className="manage-actions">
            {i.is_primary ? <span className="primary-label"><Star size={13} fill="currentColor" /> Principale</span>
              : <button disabled={busy} onClick={() => makeCover(i.id)} title="Imposta come copertina"><Star size={15} /> Copertina</button>}
            <button disabled={busy} className="danger" onClick={() => remove(i.id)} title="Elimina"><Trash2 size={15} /></button>
          </div>
        </div>)}</div>}
      <div className="mode-tabs">
        <button className={mode === 'commons' ? 'active' : ''} onClick={() => { setMode('commons'); setError(''); }}><Search size={15} /> Cerca su Commons</button>
        <button className={mode === 'upload' ? 'active' : ''} onClick={() => { setMode('upload'); setError(''); }}><Upload size={15} /> Carica un file</button>
        <button className={mode === 'url' ? 'active' : ''} onClick={() => { setMode('url'); setError(''); }}><LinkIcon size={15} /> Inserisci URL</button>
      </div>
      {error && <p className="inline-error">{error}</p>}
      {message && <p className="inline-success"><Check size={15} />{message}</p>}
      {mode === 'commons' && <div>
        <p className="muted">Cerca fotografie su Wikimedia Commons e seleziona solo quelle effettivamente riferite al calcolatore. L'autore, la fonte e la licenza disponibili vengono registrati automaticamente.</p>
        <form className="commons-search" onSubmit={searchCommons}><input value={query} onChange={e => setQuery(e.target.value)} minLength="2" maxLength="90" required aria-label="Cerca immagini" /><button disabled={busy}><Search size={16} /> {busy ? 'Ricerca…' : 'Cerca fotografie'}</button></form>
        {!!results.length && <div className="commons-results">{results.map((r, index) =>
          <article className="commons-item" key={r.source_url || index}>
            <img src={r.thumbnail_url} loading="lazy" alt={r.title} />
            <div><b title={r.title}>{r.title.replace(/^File:/, '')}</b><span>{r.license_name || 'Licenza da verificare'}</span><span>{r.author || 'Autore non indicato'}</span></div>
            <button disabled={busy} onClick={() => addCommons(r)}><Plus size={14} /> Aggiungi</button>
            {r.source_url && <a href={r.source_url} target="_blank" rel="noopener noreferrer">Verifica su Commons <ExternalLink size={12} /></a>}
          </article>)}</div>}
      </div>}
      {(mode === 'upload' || mode === 'url') && <form className="image-form" onSubmit={mode === 'upload' ? upload : link}>
        {mode === 'upload'
          ? <label className="image-field wide">Fotografia (JPEG, PNG, WebP o GIF · max 10 MB)<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={e => setFile(e.target.files?.[0] || null)} required /></label>
          : <label className="image-field wide">URL immagine HTTPS<input type="url" placeholder="https://esempio.org/immagine.jpg" value={url} onChange={e => setUrl(e.target.value)} required /></label>}
        <label className="image-field wide">Didascalia<input value={caption} maxLength={300} onChange={e => setCaption(e.target.value)} placeholder="Vista frontale del calcolatore" /></label>
        <label className="image-field">Autore / fotografo<input value={author} maxLength={350} onChange={e => setAuthor(e.target.value)} /></label>
        <label className="image-field">Licenza<input value={licenseName} maxLength={160} onChange={e => setLicenseName(e.target.value)} placeholder="es. CC BY-SA 4.0" /></label>
        <label className="image-field wide">Pagina della fonte<input type="url" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} placeholder="https://…" /></label>
        <label className="image-field wide">Link della licenza<input type="url" value={licenseUrl} onChange={e => setLicenseUrl(e.target.value)} placeholder="https://…" /></label>
        <label className="image-check"><input type="checkbox" checked={isPrimary} onChange={e => setIsPrimary(e.target.checked)} /> Imposta come immagine principale</label>
        <button className="image-submit" disabled={busy}><Plus size={17} />{busy ? 'Salvataggio…' : mode === 'upload' ? 'Carica fotografia' : 'Salva immagine esterna'}</button>
      </form>}
      <div className="license-note"><Info size={16} /><span>Le fotografie non sono automaticamente libere da diritti: controlla sempre la pagina originale e attribuisci correttamente gli autori. Le immagini caricate sono conservate localmente; quelle via URL restano sui siti di origine.</span></div>
    </div>}
  </section>;
}

function Stats({ analytics }) {
  return <div className="stats"><div><span>SISTEMI CATALOGATI</span><b>{analytics?.total ?? '—'}</b><small>nel database</small></div>
    <div><span>PRODUTTORI</span><b>{analytics?.by_manufacturer?.length ?? '—'}</b><small>rappresentati</small></div>
    <div><span>CATEGORIE</span><b>{analytics?.by_category?.length ?? '—'}</b><small>di calcolatori</small></div>
    <div><span>PERIODO</span><b className="range">{analytics?.year_range?.join('–') ?? '—'}</b><small>anni coperti</small></div></div>;
}

function Filters({ meta, filters, setFilters }) {
  const update = (k, v) => setFilters(f => ({ ...f, [k]: v }));
  return <div className="filters">
    <div className="search"><Search size={17} /><input placeholder="Cerca un sistema…" value={filters.q} onChange={e => update('q', e.target.value)} /></div>
    <select value={filters.category_id} onChange={e => update('category_id', e.target.value)} aria-label="Categoria"><option value="">Tutte le categorie</option>{meta.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
    <select value={filters.manufacturer_id} onChange={e => update('manufacturer_id', e.target.value)} aria-label="Produttore"><option value="">Tutti i produttori</option>{meta.manufacturers.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
    <input className="year-input" type="number" min="1" max="9999" placeholder="Da anno" value={filters.year_from} onChange={e => update('year_from', e.target.value)} />
    <input className="year-input" type="number" min="1" max="9999" placeholder="A anno" value={filters.year_to} onChange={e => update('year_to', e.target.value)} />
    <button onClick={() => setFilters({ q: '', category_id: '', manufacturer_id: '', year_from: '', year_to: '' })}>Reset</button>
  </div>;
}

function ComputerDetail({ computer, onClose, onChanged }) {
  return <>
    <button className="back" onClick={onClose}><ArrowLeft size={16} /> Torna all'esplorazione</button>
    <div className="eyebrow">SCHEDA SISTEMA · #{computer.id}</div>
    <h1>{computer.model_name}</h1>
    <p className="lead">{computer.manufacturer} · {computer.first_release || 'Data non disponibile'}</p>
    <p>{computer.description}</p><div className="tag-row">{computer.categories.map(x => <span className="tag" key={x}>{x}</span>)}</div>
    <div className="section-title">Galleria fotografica <span>{computer.images?.length || 0} fotografie</span></div>
    <Gallery computer={computer} />
    <ImageManager computer={computer} onChanged={onChanged} />
    <div className="section-title">Configurazioni e specifiche</div>
    {computer.configurations.map(c => <section className="panel" key={c.id}><h3>{c.variant_name}</h3><table><tbody>{c.specifications.map(s => <tr key={s.id}><td>{s.component_type} · {s.property_name}</td><td><strong>{s.numeric_value ?? s.text_value} {s.unit || ''}</strong></td></tr>)}</tbody></table></section>)}
    <div className="section-title">Commercializzazione</div>
    {computer.releases.map(r => <section className="panel" key={r.id}><b>{r.market}</b><p>{r.release_date || 'Data non disponibile'} · {r.price != null ? `${r.price} ${r.currency}` : 'Prezzo non disponibile'}</p>{r.sources.map(s => <Source key={s.id} s={s} />)}</section>)}
    <div className="section-title">Fonti e verificabilità</div>
    <section className="panel">{computer.sources.length ? computer.sources.map(s => <Source key={s.id} s={s} />) : <p className="muted">Non sono ancora state associate fonti verificate a questa scheda. I dati iniziali sono dimostrativi. Le fonti fotografiche sono indicate nella galleria.</p>}</section>
  </>;
}

function App() {
  const [tab, setTab] = useState('timeline');
  const [revision, setRevision] = useState(0);
  const [adminDirty, setAdminDirty] = useState(false);
  const [meta, setMeta] = useState({ manufacturers: [], categories: [] });
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState({ q: '', category_id: '', manufacturer_id: '', year_from: '', year_to: '' });
  const [selected, setSelected] = useState(null);
  const [compare, setCompare] = useState([]);
  const [comparisonConfigurations, setComparisonConfigurations] = useState({});
  const [analytics, setAnalytics] = useState(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    setComparisonConfigurations(previous => {
      const kept = Object.entries(previous).filter(([id]) => compare.some(c => String(c.id) === id));
      return kept.length === Object.keys(previous).length ? previous : Object.fromEntries(kept);
    });
  }, [compare.map(c => c.id).join(',')]);
  useEffect(() => { api('/meta').then(setMeta).catch(e => setError(e.message)); }, [revision]);
  useEffect(() => {
    if (tab !== 'timeline' && tab !== 'catalog') return;
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v !== ''));
    return latestRequest(signal => allComputers(params, signal), rows => { setItems(rows); setError(''); }, e => setError(e.message));
  }, [filters, revision, tab]);
  useEffect(() => { api('/analytics').then(setAnalytics).catch(() => {}); }, [revision]);
  // Refresh stored labels after administrative edits without loading the archive for the picker.
  useEffect(() => {
    if (!compare.length) return;
    return latestRequest(signal => Promise.all(compare.map(c => api('/computers/' + c.id, { signal }))),
      rows => setCompare(current => current.map(c => comparisonSummary(rows.find(row => row.id === c.id) || c))), () => {});
  }, [revision]);
  async function refreshComputer() {
    if (!selected) return;
    const [updated, listing] = await Promise.all([api('/computers/' + selected.id), allComputers()]);
    setSelected(updated);
    setItems(previous => previous.map(old => listing.find(c => c.id === old.id) || old));
  }
  const openComputer = async id => { try { setSelected(await api('/computers/' + id)); } catch (e) { setError(e.message); } };
  const toggle = computer => setCompare(a => a.some(c => c.id === computer.id) ? a.filter(c => c.id !== computer.id) : a.length < 5 ? [...a, comparisonSummary(computer)] : a);
  const ask = async e => {
    e.preventDefault(); setLoading(true); setAnswer('');
    try { const result = await api('/assistant', { method: 'POST', body: JSON.stringify({ question }) }); setAnswer(result.answer); }
    catch (e) { setAnswer(e.message); }
    finally { setLoading(false); }
  };
  return <div className="shell"><aside className="sidebar">
    <div className="brand"><div className="brand-icon"><Monitor size={22} /></div><div><b>HARDWARE</b><span>HISTORY EXPLORER</span></div></div>
    <div className="side-label">ESPLORA</div>
    <nav>{nav.map(([id, label, Icon]) => <button key={id} onClick={() => { if (id === tab && !selected) return; if (tab === 'admin' && adminDirty && !window.confirm('Ci sono modifiche non salvate. Vuoi abbandonarle?')) return; setAdminDirty(false); setTab(id); setSelected(null); }} className={tab === id ? 'active' : ''}><Icon size={18} />{label}{id === 'compare' && compare.length > 0 ? <small>{compare.length}</small> : null}</button>)}</nav>
    <div className="side-bottom"><div className="status-dot" />Archivio dimostrativo<br /><span>Versione 1.1 · Single-user</span></div>
  </aside><main><header><div className="breadcrumb">ARCHIVIO DIGITALE <ChevronRight size={14} /> {nav.find(x => x[0] === tab)?.[1].toUpperCase()}</div><div className="header-actions"><ThemeSwitcher /><div className="header-right"><span className="header-tagline">STORIA DELL'INFORMATICA</span><span className="avatar">H</span></div></div></header>
    <div className="content">{error && <div className="error">{error} <button onClick={() => setError('')}>×</button></div>}
      {selected ? <ComputerDetail computer={selected} onClose={() => setSelected(null)} onChanged={refreshComputer} /> : <>
        {tab === 'admin' && <AdminPanel onSaved={() => setRevision(v => v + 1)} onDirtyChange={setAdminDirty} onOpenComputer={openComputer} />}
        {tab === 'timeline' && <><div className="eyebrow">UN VIAGGIO NELL'EVOLUZIONE TECNOLOGICA</div><h1>La storia dei <em>calcolatori.</em></h1><p className="lead">Esplora i sistemi che hanno definito l'informatica, dai mainframe ai personal computer.</p><Stats analytics={analytics} /><div className="section-title">Timeline delle innovazioni <span>{items.length} sistemi</span></div><Filters meta={meta} filters={filters} setFilters={setFilters} />
          <div className="timeline">{items.map(c => <div className="time-item" key={c.id}><div className="time-year">{c.year || '—'}</div><div className="time-line"><i /></div>
            <div className="time-card" onClick={() => openComputer(c.id)}><div className="time-top"><span className="tag">{c.categories[0]}</span><span>{c.manufacturer}</span></div><div className="time-content"><SystemCover src={c.image_url} name={c.model_name} year={c.year} className="time-photo" /><div className="time-info"><h3>{c.model_name}</h3><p>{c.description}</p></div></div>
              <div className="card-foot"><span>Esplora scheda <ChevronRight size={15} /></span><button onClick={e => { e.stopPropagation(); toggle(c); }} className={compare.some(s => s.id === c.id) ? 'added' : ''}>{compare.some(s => s.id === c.id) ? '✓ Selezionato' : '+ Confronta'}</button></div></div>
          </div>)}</div></>}
        {tab === 'catalog' && <><div className="eyebrow">DATABASE STORICO</div><h1>Catalogo sistemi</h1><p className="lead">Cerca, filtra e approfondisci le caratteristiche dei calcolatori.</p><Filters meta={meta} filters={filters} setFilters={setFilters} />
          <div className="catalog-grid">{items.map(c => <article className="catalog-card" key={c.id}><SystemCover src={c.image_url} name={c.model_name} year={c.year} className="catalog-photo" /><span className="tag">{c.categories[0]}</span><h3>{c.model_name}</h3><p className="muted">{c.manufacturer}</p><p>{c.description}</p><div className="card-foot"><button onClick={() => openComputer(c.id)}>Dettagli <ChevronRight size={15} /></button><button onClick={() => toggle(c)} className={compare.some(s => s.id === c.id) ? 'added' : ''}>{compare.some(s => s.id === c.id) ? '✓' : '+ Confronta'}</button></div></article>)}</div></>}
        {tab === 'analysis' && <><div className="eyebrow">DATA EXPLORATION</div><h1>Analisi dell'archivio</h1><p className="lead">Distribuzioni temporali e per categoria calcolate direttamente dal database.</p><Stats analytics={analytics} /><div className="charts"><section className="panel"><h3>Sistemi per anno di commercializzazione</h3><div className="chart"><ResponsiveContainer><BarChart data={analytics?.by_year || []}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" vertical={false} /><XAxis stroke="var(--chart-axis)" tick={{ fill: 'var(--chart-text)' }} dataKey="year" /><YAxis stroke="var(--chart-axis)" allowDecimals={false} /><Tooltip contentStyle={{ backgroundColor: 'var(--chart-tooltip-bg)', color: 'var(--chart-tooltip-text)', borderColor: 'var(--chart-grid)', borderRadius: 8 }} labelStyle={{ color: 'var(--chart-tooltip-text)' }} itemStyle={{ color: 'var(--chart-tooltip-text)' }} cursor={{ fill: 'var(--chart-cursor)' }} /><Bar dataKey="count" fill="var(--chart-bar)" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div></section><section className="panel"><h3>Distribuzione per categoria</h3><div className="chart"><ResponsiveContainer><BarChart data={analytics?.by_category || []} layout="vertical" margin={{ left: 35 }}><XAxis stroke="var(--chart-axis)" tick={{ fill: 'var(--chart-text)' }} type="number" allowDecimals={false} /><YAxis stroke="var(--chart-axis)" type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: 'var(--chart-text)' }} /><Tooltip contentStyle={{ backgroundColor: 'var(--chart-tooltip-bg)', color: 'var(--chart-tooltip-text)', borderColor: 'var(--chart-grid)', borderRadius: 8 }} labelStyle={{ color: 'var(--chart-tooltip-text)' }} itemStyle={{ color: 'var(--chart-tooltip-text)' }} cursor={{ fill: 'var(--chart-cursor)' }} /><Bar dataKey="count" fill="var(--chart-bar)" radius={[0, 5, 5, 0]} /></BarChart></ResponsiveContainer></div></section></div><p className="muted">Le distribuzioni riflettono il campione dimostrativo e non la totalità del mercato storico.</p></>}
        {tab === 'compare' && <><div className="eyebrow">ANALISI COMPARATIVA</div><h1>Confronta i sistemi</h1><p className="lead">Cerca e aggiungi da 2 a 5 sistemi per confrontarli subito. Puoi selezionarli anche dal catalogo e dalla timeline.</p>
          <ComparisonPicker selected={compare} onSelect={toggle} onRemove={id => setCompare(a => a.filter(c => c.id !== id))} />
          {compare.length >= 2 ? <ComparisonTable ids={compare.map(c => c.id)} configurations={comparisonConfigurations} onConfigurationChange={(id, value) => setComparisonConfigurations(previous => ({ ...previous, [id]: value }))} Cover={SystemCover} /> : <div className="empty">{compare.length ? 'Aggiungi un altro sistema per visualizzare il confronto.' : 'Cerca e seleziona almeno due calcolatori per visualizzare il confronto.'}</div>}</>}
        {tab === 'assistant' && <><div className="eyebrow">INTERROGAZIONE IN LINGUAGGIO NATURALE</div><h1>Assistente storico <em>AI.</em></h1><p className="lead">Fai domande sull'archivio. L'assistente riceve i dati disponibili e ne segnala le lacune.</p><div className="assistant-panel"><div className="assistant-intro"><Bot size={26} /><h3>Come posso aiutarti?</h3><p>Prova: «Quali sistemi sono stati commercializzati negli anni '70?» oppure «Confronta Apple II e IBM PC».</p></div>{answer && <div className="answer">{answer}</div>}<form onSubmit={ask} className="ask-form"><input value={question} onChange={e => setQuestion(e.target.value)} placeholder="Scrivi una domanda sulla storia dell'hardware..." minLength={3} required /><button disabled={loading}>{loading ? 'Elaborazione…' : 'Invia →'}</button></form></div><p className="muted">L'assistente non può modificare il database o eseguire query SQL arbitrarie. Richiede una chiave API OpenAI configurata sul server.</p></>}
      </>}</div></main></div>;
}

createRoot(document.getElementById('root')).render(<App />);
