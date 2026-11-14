import React, { useEffect, useLayoutEffect, useState } from 'react';
import { Plus, Pencil, Save, X, BookOpen, Monitor, ExternalLink } from 'lucide-react';
import { api, allComputers, latestRequest } from './api.js';
import { newComputer, newSource, computerDraft, computerPayload, sourcePayload } from './admin-data.js';
import './admin.css';
import ImportPanel from './ImportPanel.jsx';
import PhotoPanel from './PhotoPanel.jsx';

function Field({ label, value, onChange, wide = false, multiline = false, ...props }) {
  const Tag = multiline ? 'textarea' : 'input';
  return <label className={'admin-field' + (wide ? ' wide' : '')}><span>{label}</span>
    <Tag aria-label={label} value={value ?? ''} onChange={e => onChange(e.target.value)} {...props} />
  </label>;
}
function Choices({ label, options, value = [], onChange }) {
  return <fieldset className="admin-choices"><legend>{label}</legend>
    {options.length ? options.map(option => <label key={option.id}><input type="checkbox" checked={value.includes(option.id)}
      onChange={e => onChange(e.target.checked ? [...value, option.id] : value.filter(id => id !== option.id))} />{option.name || option.title}</label>)
      : <p className="muted">Nessun elemento disponibile.</p>}
  </fieldset>;
}
function ReferenceCreator({ label, path, onCreated }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function create() {
    if (!name.trim()) return;
    setBusy(true); setError('');
    try {
      const entry = await api('/' + path, { method: 'POST', body: JSON.stringify({ name }) });
      await onCreated(entry); setName('');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <div className="admin-reference"><div>
    <label>{label}<input value={name} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); if (!busy) create(); } }} maxLength={100} /></label>
    <button type="button" disabled={busy || !name.trim()} onClick={create}><Plus size={14} />Aggiungi</button>
  </div>{error && <p className="inline-error" role="alert">{error}</p>}</div>;
}

function ComputerEditor({ draft, setDraft, meta, sources, reload, onReferenceChange }) {
  const set = (key, value) => setDraft({ ...draft, [key]: value });
  const patchRelease = (index, key, value) => set('releases', draft.releases.map((r, i) => i === index ? { ...r, [key]: value } : r));
  const patchConfig = (index, key, value) => set('configurations', draft.configurations.map((c, i) => i === index ? { ...c, [key]: value } : c));
  const patchSpec = (ci, si, key, value) => patchConfig(ci, 'specifications', draft.configurations[ci].specifications.map((s, i) => i === si ? { ...s, [key]: value } : s));
  const remove = (label, action) => { if (window.confirm('Rimuovere ' + label + '? La modifica sarà applicata quando salvi il calcolatore.')) action(); };
  async function reference(path, item) {
    if (path === 'manufacturers') setDraft(current => ({ ...current, manufacturer_id: item.id }));
    if (path === 'categories') setDraft(current => ({ ...current, category_ids: [...current.category_ids, item.id] }));
    await reload(); onReferenceChange();
  }
  return <>
    <h3>Dati del calcolatore</h3>
    <div className="admin-grid">
      <Field label="Nome del modello" required maxLength={180} value={draft.model_name} onChange={v => set('model_name', v)} />
      <label className="admin-field"><span>Produttore</span><select aria-label="Produttore" required value={draft.manufacturer_id} onChange={e => set('manufacturer_id', Number(e.target.value))}>
        <option value="">Scegli un produttore</option>{meta.manufacturers.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
      </select></label>
      <Field label="Descrizione" wide multiline rows={4} maxLength={20000} value={draft.description} onChange={v => set('description', v)} />
      <Field label="Data di annuncio" placeholder="Es. 1982 oppure 1982-08 oppure 1982-08-01" pattern="[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?" value={draft.announcement_date} onChange={v => set('announcement_date', v)} />
    </div>
    <p className="muted">Per le date puoi indicare solo l'anno, anno e mese oppure la data completa. Lascia vuoto ciò che non conosci.</p>
    <Choices label="Categorie" options={meta.categories} value={draft.category_ids} onChange={v => set('category_ids', v)} />
    <details className="admin-reference-tools"><summary>Aggiungi produttore o categoria</summary>
      <ReferenceCreator label="Nuovo produttore" path="manufacturers" onCreated={item => reference('manufacturers', item)} />
      <ReferenceCreator label="Nuova categoria" path="categories" onCreated={item => reference('categories', item)} />
    </details>
    <Choices label="Fonti del calcolatore" options={sources} value={draft.source_ids} onChange={v => set('source_ids', v)} />
    {!sources.length && <p className="muted">Puoi creare le fonti nella sezione Fonti e associarle qui.</p>}
    <div className="admin-section"><h3>Commercializzazioni</h3><button type="button" onClick={() => set('releases', [...draft.releases, {
      market_id: meta.markets[0]?.id || '', release_date: '', discontinuation_date: '', price: '', currency: '', price_type: 'launch', source_ids: []
    }])}><Plus size={15} />Aggiungi commercializzazione</button></div>
    {draft.releases.map((r, i) => <section className="admin-nested" key={r.id || 'new-' + i}>
      <div className="admin-section"><h4>Commercializzazione {i + 1}</h4><button type="button" className="admin-remove" onClick={() => remove('questa commercializzazione', () => set('releases', draft.releases.filter((_, n) => i !== n)))}>Rimuovi</button></div>
      <div className="admin-grid">
        <label className="admin-field"><span>{'Mercato ' + (i + 1)}</span><select aria-label={'Mercato ' + (i + 1)} required value={r.market_id} onChange={e => patchRelease(i, 'market_id', Number(e.target.value))}>
          <option value="">Scegli un mercato</option>{meta.markets.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select></label>
        <Field label={'Data di lancio ' + (i + 1)} placeholder="AAAA, AAAA-MM o AAAA-MM-GG" value={r.release_date} onChange={v => patchRelease(i, 'release_date', v)} />
        <Field label={'Fine commercializzazione ' + (i + 1)} placeholder="AAAA, AAAA-MM o AAAA-MM-GG" value={r.discontinuation_date} onChange={v => patchRelease(i, 'discontinuation_date', v)} />
        <Field label={'Prezzo ' + (i + 1)} type="number" min="0" step="any" value={r.price} onChange={v => patchRelease(i, 'price', v)} />
        <Field label={'Valuta ' + (i + 1)} placeholder="Es. USD, EUR, ITL" maxLength={3} value={r.currency} onChange={v => patchRelease(i, 'currency', v.toUpperCase())} />
        <Field label={'Tipo di prezzo ' + (i + 1)} maxLength={30} value={r.price_type} onChange={v => patchRelease(i, 'price_type', v)} />
      </div>
      <Choices label={'Fonti commercializzazione ' + (i + 1)} options={sources} value={r.source_ids} onChange={v => patchRelease(i, 'source_ids', v)} />
    </section>)}
    <details className="admin-reference-tools"><summary>Aggiungi un mercato</summary><ReferenceCreator label="Nuovo mercato" path="markets" onCreated={async () => { await reload(); onReferenceChange(); }} /></details>
    <div className="admin-section"><h3>Configurazioni e specifiche</h3><button type="button" onClick={() => set('configurations', [...draft.configurations, { variant_name: '', description: '', specifications: [] }])}><Plus size={15} />Aggiungi configurazione</button></div>
    {draft.configurations.map((cfg, ci) => <section className="admin-nested" key={cfg.id || 'new-' + ci}>
      <div className="admin-section"><h4>Configurazione {ci + 1}</h4><button type="button" className="admin-remove" onClick={() => remove('questa configurazione e le sue specifiche', () => set('configurations', draft.configurations.filter((_, n) => ci !== n)))}>Rimuovi</button></div>
      <div className="admin-grid">
        <Field label={'Nome configurazione ' + (ci + 1)} required maxLength={140} value={cfg.variant_name} onChange={v => patchConfig(ci, 'variant_name', v)} />
        <Field label={'Descrizione configurazione ' + (ci + 1)} maxLength={10000} value={cfg.description} onChange={v => patchConfig(ci, 'description', v)} />
      </div>
      {cfg.specifications.map((s, si) => <div className="admin-spec" key={s.id || 'new-' + si}>
        <div className="admin-section"><h4>Specifica {ci + 1}.{si + 1}</h4><button type="button" className="admin-remove" onClick={() => remove('questa specifica', () => patchConfig(ci, 'specifications', cfg.specifications.filter((_, n) => si !== n)))}>Rimuovi</button></div>
        <div className="admin-grid">
          <Field label={'Componente ' + (ci + 1) + '.' + (si + 1)} required placeholder="CPU, RAM, memoria…" maxLength={80} value={s.component_type} onChange={v => patchSpec(ci, si, 'component_type', v)} />
          <Field label={'Nome componente ' + (ci + 1) + '.' + (si + 1)} maxLength={160} value={s.component_name} onChange={v => patchSpec(ci, si, 'component_name', v)} />
          <Field label={'Proprietà ' + (ci + 1) + '.' + (si + 1)} required placeholder="Modello, frequenza, capacità…" maxLength={120} value={s.property_name} onChange={v => patchSpec(ci, si, 'property_name', v)} />
          <label className="admin-field"><span>{'Tipo di valore ' + (ci + 1) + '.' + (si + 1)}</span><select aria-label={'Tipo di valore ' + (ci + 1) + '.' + (si + 1)} value={s.value_kind} onChange={e => patchSpec(ci, si, 'value_kind', e.target.value)}><option value="text">Testo</option><option value="number">Numero</option></select></label>
          <Field label={'Valore ' + (ci + 1) + '.' + (si + 1)} required type={s.value_kind === 'number' ? 'number' : 'text'} step={s.value_kind === 'number' ? 'any' : undefined}
            value={s.value_kind === 'number' ? s.numeric_value : s.text_value} onChange={v => patchSpec(ci, si, s.value_kind === 'number' ? 'numeric_value' : 'text_value', v)} />
          <Field label={'Unità ' + (ci + 1) + '.' + (si + 1)} maxLength={30} value={s.unit} onChange={v => patchSpec(ci, si, 'unit', v)} />
        </div>
        <Choices label={'Fonti specifica ' + (ci + 1) + '.' + (si + 1)} options={sources} value={s.source_ids} onChange={v => patchSpec(ci, si, 'source_ids', v)} />
      </div>)}
      <button type="button" onClick={() => patchConfig(ci, 'specifications', [...cfg.specifications, { component_type: '', component_name: '', property_name: '', value_kind: 'text', text_value: '', numeric_value: null, unit: '', source_ids: [] }])}><Plus size={15} />Aggiungi specifica</button>
    </section>)}
  </>;
}
function SourceEditor({ draft, setDraft }) {
  const set = (key, value) => setDraft({ ...draft, [key]: value });
  return <div className="admin-grid">
    <Field label="Titolo della fonte" required minLength={2} maxLength={300} wide value={draft.title} onChange={v => set('title', v)} />
    <Field label="Autore" maxLength={180} value={draft.author} onChange={v => set('author', v)} />
    <Field label="Editore o pubblicazione" maxLength={180} value={draft.publisher} onChange={v => set('publisher', v)} />
    <Field label="URL della fonte" type="url" maxLength={800} wide placeholder="https://…" value={draft.url} onChange={v => set('url', v)} />
    <Field label="Tipo di fonte" required maxLength={60} placeholder="website, book, manual, archive…" value={draft.source_type} onChange={v => set('source_type', v)} />
    <Field label="Data di pubblicazione" type="date" value={draft.publication_date} onChange={v => set('publication_date', v)} />
    <Field label="Data di consultazione" type="date" value={draft.access_date} onChange={v => set('access_date', v)} />
  </div>;
}

export default function AdminPanel({ onSaved, onDirtyChange, onOpenComputer, onArchiveReset = onSaved }) {
  const [section, setSection] = useState('computers');
  useLayoutEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); }, [section]);
  const [records, setRecords] = useState([]);
  const [sources, setSources] = useState([]);
  const [meta, setMeta] = useState({ manufacturers: [], categories: [], markets: [] });
  const [draft, setDraft] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  async function loadData(signal) {
    return Promise.all([allComputers(new URLSearchParams({ sort: 'name' }), signal), api('/sources', { signal }), api('/meta', { signal })]);
  }
  function receive([computers, bibliography, metadata]) { setRecords(computers); setSources(bibliography); setMeta(metadata); setLoading(false); }
  async function reload() { receive(await loadData()); }
  useEffect(() => latestRequest(loadData, receive, e => { setError(e.message); setLoading(false); }), []);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  const change = value => { setDraft(value); setDirty(true); setMessage(''); };
  const discard = () => !dirty || window.confirm('Ci sono modifiche non salvate. Vuoi abbandonarle?');
  function chooseSection(value) {
    if (!discard()) return;
    setSection(value); setDraft(null); setDirty(false); setQuery(''); setError(''); setMessage('');
  }
  function create() {
    if (!discard()) return;
    setDraft(section === 'computers' ? newComputer() : newSource()); setDirty(false); setError(''); setMessage('');
  }
  async function edit(id) {
    if (!discard()) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const record = await api(section === 'computers' ? '/admin/computers/' + id : '/sources/' + id);
      setDraft(section === 'computers' ? computerDraft(record) : record); setDirty(false);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const payload = section === 'computers' ? computerPayload(draft) : sourcePayload(draft);
      const result = await api('/' + section + (draft.id ? '/' + draft.id : ''), { method: draft.id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      setDraft(section === 'computers' ? computerDraft(result) : result); setDirty(false);
      setMessage(section === 'computers' ? 'Calcolatore salvato.' : 'Fonte salvata.');
      onSaved();
      try { await reload(); } catch { setError('Salvataggio riuscito. Non è stato possibile aggiornare gli elenchi: ricarica la pagina.'); }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const listing = (section === 'computers' ? records : sources).filter(r =>
    [r.model_name, r.manufacturer, r.title, r.author, r.publisher].filter(Boolean).join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  return <section className="admin-panel">
    <div className="eyebrow">GESTIONE DELL'ARCHIVIO</div><h1>Amministrazione</h1>
    <p className="lead">Inserisci e aggiorna calcolatori e fonti. Le informazioni salvate sono subito disponibili nell'archivio.</p>
    <div className="admin-tabs" aria-label="Sezioni amministrative">
      <button disabled={busy} className={section === 'computers' ? 'active' : ''} onClick={() => chooseSection('computers')}><Monitor size={17} />Calcolatori</button>
      <button disabled={busy} className={section === 'sources' ? 'active' : ''} onClick={() => chooseSection('sources')}><BookOpen size={17} />Fonti</button>
      <button disabled={busy} className={section === 'imports' ? 'active' : ''} onClick={() => chooseSection('imports')}>Importazioni</button>
      <button disabled={busy} className={section === 'photos' ? 'active' : ''} onClick={() => chooseSection('photos')}>Foto automatiche</button>
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p className="inline-success" role="status">{message}</p>}
    {section === 'photos' ? <PhotoPanel onSaved={() => { onSaved(); reload().catch(e => setError(e.message)); }} /> : section === 'imports' ? <ImportPanel onSaved={() => { onSaved(); reload().catch(e => setError(e.message)); }}
      onArchiveReset={() => { setDraft(null); setDirty(false); setQuery(''); setMessage(''); onArchiveReset(); reload().catch(e => setError(e.message)); }} /> : <div className="admin-layout"><aside className="panel admin-list">
      <button className="admin-primary" disabled={busy || loading} onClick={create}><Plus size={16} />{section === 'computers' ? 'Nuovo calcolatore' : 'Nuova fonte'}</button>
      <label className="admin-field"><span>Cerca {section === 'computers' ? 'calcolatori' : 'fonti'}</span><input value={query} onChange={e => setQuery(e.target.value)} /></label>
      {loading ? <p>Caricamento…</p> : <>
        <p className="muted">{listing.length} {section === 'computers' ? 'calcolatori' : 'fonti'}</p>
        <div className="admin-records">{listing.map(record => <button key={record.id} disabled={busy} className={record.id === draft?.id ? 'selected' : ''} onClick={() => edit(record.id)}>
          <span><b>{record.model_name || record.title}</b><small>{record.manufacturer || record.author || record.publisher || record.source_type}</small></span><Pencil size={14} />
        </button>)}</div>
        {!listing.length && <p className="muted">Nessun risultato.</p>}
      </>}
    </aside><div className="panel admin-editor">
      {!draft ? <div className="admin-empty"><Pencil size={30} /><h3>Scegli un elemento oppure creane uno nuovo</h3><p>Le modifiche vengono applicate solo quando premi Salva.</p></div> : <form onSubmit={save}>
        <fieldset className="admin-form-fields" disabled={busy}>
          <div className="admin-section"><h2>{draft.id ? 'Modifica ' : 'Nuovo '}{section === 'computers' ? 'calcolatore' : 'fonte'}</h2>{dirty && <span className="admin-unsaved">Modifiche non salvate</span>}</div>
          {section === 'computers' ? <ComputerEditor draft={draft} setDraft={change} meta={meta} sources={sources} reload={reload} onReferenceChange={onSaved} /> : <SourceEditor draft={draft} setDraft={change} />}
          <div className="admin-save-bar"><button type="submit" className="admin-primary"><Save size={16} />{busy ? 'Salvataggio…' : 'Salva ' + (section === 'computers' ? 'calcolatore' : 'fonte')}</button>
            <button type="button" onClick={() => { if (discard()) { setDraft(null); setDirty(false); setError(''); setMessage(''); } }}><X size={16} />Annulla</button>
            {section === 'computers' && draft.id && !dirty && <button type="button" onClick={() => onOpenComputer(draft.id)}><ExternalLink size={16} />Apri scheda e fotografie</button>}
          </div>
        </fieldset>
      </form>}
    </div></div>}
  </section>;
}
