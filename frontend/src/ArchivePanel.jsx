import React, { useState } from 'react';
import { api } from './api.js';

const labels = { computers: 'Calcolatori', configurations: 'Configurazioni', specifications: 'Specifiche',
  releases: 'Commercializzazioni e prezzi', sales: 'Vendite', reviews: 'Recensioni', facts: 'Fatti',
  computer_images: 'Associazioni fotografiche', manufacturers: 'Produttori', categories: 'Categorie', markets: 'Mercati' };

export default function ArchivePanel({ onReset }) {
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const [confirmation, setConfirmation] = useState('');
  const [backup, setBackup] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function action(work) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <details className="panel archive-maintenance">
    <summary>Svuota archivio per un nuovo import</summary>
    <p>Rimuove tutti i calcolatori, i dati tecnici, i prezzi, le associazioni fotografiche e i produttori/categorie/mercati attuali. Fonti, file fotografici e storico delle importazioni restano conservati.</p>
    <p>Dopo lo svuotamento il catalogo resta vuoto anche al riavvio: le macchine dimostrative non ricompaiono. I vecchi abbinamenti sono rimossi e le importazioni precedenti vengono archiviate.</p>
    <p>Prima di procedere salva un backup del database e del volume fotografico. Gli originali conservati nello storico non sostituiscono un backup completo e non hanno un ripristino automatico.</p>
    <button type="button" disabled={busy} onClick={() => action(async () => {
      const [p, h] = await Promise.all([api('/admin/archive/preview'), api('/admin/archive/resets')]);
      setPreview(p); setHistory(h); setConfirmation(''); setBackup(false); setNote('');
    })}>Prepara anteprima di svuotamento</button>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {message && <p role="status" className="inline-success">{message}</p>}
    {preview && <section aria-label="Anteprima svuotamento archivio">
      <h3>Dati da rimuovere dal catalogo</h3>
      <dl className="import-values">{Object.entries(labels).map(([key, label]) => <React.Fragment key={key}>
        <dt>{label}</dt><dd>{preview.counts[key]}</dd>
      </React.Fragment>)}</dl>
      <p>Restano {preview.counts.sources_retained} fonti bibliografiche e {preview.counts.import_jobs_retained} importazioni nello storico. Le vecchie decisioni non potranno modificare le nuove schede.</p>
      <label>Motivazione dello svuotamento<textarea rows={2} disabled={busy} value={note} maxLength={2000} onChange={e => setNote(e.target.value)} /></label>
      <label className="import-rights"><input type="checkbox" disabled={busy} checked={backup} onChange={e => setBackup(e.target.checked)} />Ho salvato un backup del database e delle fotografie e accetto la rimozione dei dati elencati.</label>
      <label>Scrivi SVUOTA ARCHIVIO per confermare<input disabled={busy} value={confirmation} maxLength={30} autoComplete="off" onChange={e => setConfirmation(e.target.value)} /></label>
      <button className="archive-reset-button" type="button" disabled={busy || !backup || confirmation !== 'SVUOTA ARCHIVIO' || note.trim().length < 5}
        onClick={() => action(async () => {
          await api('/admin/archive/reset', { method: 'POST', body: JSON.stringify({ token: preview.token,
            confirmation, backup_confirmed: backup, note }) });
          setPreview(null); setConfirmation(''); setBackup(false); setNote('');
          onReset(); setHistory(await api('/admin/archive/resets'));
          setMessage('Archivio svuotato. Catalogo: 0 calcolatori. Puoi preparare un nuovo import; le macchine dimostrative restano disattivate.');
        })}>Svuota i dati elencati</button>
      <button type="button" disabled={busy} onClick={() => { setPreview(null); setConfirmation(''); }}>Annulla svuotamento</button>
    </section>}
    {!!history.length && <details><summary>Storico degli svuotamenti</summary>{history.map(item => <p key={item.id}>
      Svuotamento #{item.id}: {item.counts.computers} calcolatori. {item.note} · <a href={`/api/admin/archive/resets/${item.id}/original`} download>Scarica dati precedenti (JSON)</a>
    </p>)}</details>}
  </details>;
}
