import React, { useState } from 'react';
import { api } from './api.js';

export default function ClassificationPanel({ onSaved }) {
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function action(work) {
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <details className="panel import-duplicates">
    <summary>Completa le categorie delle schede generiche</summary>
    <p>Aggiunge Home computer, Personal computer, Workstation e altre categorie alle famiglie riconosciute da regole esplicite. Conserva tutte le categorie già presenti e salta le schede con classificazioni specifiche.</p>
    <p>È una classificazione editoriale da verificare, registrata nello storico delle importazioni. I casi non riconosciuti restano generici; non è necessario svuotare o ricaricare il catalogo.</p>
    <button disabled={busy} onClick={() => action(async () => setPreview(await api('/admin/classification/preview')))}>Prepara anteprima categorie</button>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {preview && <>
      <p>{preview.total} schede classificabili. {preview.unresolved} schede restano da classificare.</p>
      <ul>{Object.entries(preview.by_category).map(([category, count]) => <li key={category}>{category}: {count}</li>)}</ul>
      <details><summary>Prime assegnazioni proposte</summary><ul>{preview.proposals.slice(0, 20).map(p => <li key={p.id}>{p.manufacturer} · {p.model_name} → {p.category}</li>)}</ul></details>
      <button disabled={busy || !preview.total} onClick={() => action(async () => {
        const result = await api('/admin/classification/apply', { method: 'POST', body: JSON.stringify({ token: preview.token }) });
        setPreview(null); setMessage(`Categorie aggiunte a ${result.updated} schede. Le assegnazioni sono da verificare in Fonti e verifiche.`); onSaved();
      })}>Applica le categorie proposte</button>
    </>}
  </details>;
}
