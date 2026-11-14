import React, { useEffect, useRef, useState } from 'react';
import { api } from './api.js';

export default function CatalogRefinementPanel({ onSaved }) {
  const [regional, setRegional] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState(null);
  const running = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; running.current = false; }; }, []);
  async function action(work) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { if (mounted.current) setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function enrich() {
    running.current = true;
    let current = preview, done = 0, updated = 0, conflicts = 0;
    try {
      do {
        const result = await api('/admin/enrichment/apply', { method: 'POST', body: JSON.stringify({ token: current.token,
          after_id: current.after_id, upper_id: current.upper_id }) });
        done += result.processed; updated += result.job?.counts.updated || 0;
        conflicts += result.job?.verification_counts.conflict || 0;
        if (!mounted.current) return;
        setProgress({ done, total: current.total, updated, conflicts });
        if (result.job?.status === 'partial') throw Error('Alcune righe richiedono controllo: consulta il lavoro #' + result.job.id + ' nelle Ultime importazioni prima di proseguire.');
        if (!result.has_more || !running.current) break;
        current = await api(`/admin/enrichment/preview?after_id=${result.next_id}&upper_id=${current.upper_id}`);
      } while (running.current);
      if (mounted.current) {
        setPreview(null); setMessage(`Elaborate ${done} schede, ${updated} aggiornate. I dati restano da verificare; ${conflicts} conflitti conservano il dato attuale.`);
      }
    } finally { running.current = false; if (mounted.current) onSaved(); }
  }
  return <details className="panel import-duplicates">
    <summary>Rifinisci catalogo: varianti regionali, descrizioni e dati</summary>
    <h4>Varianti regionali</h4>
    <p>Accorpa le denominazioni che differiscono solo per qualificatori geografici espliciti, conservando configurazioni, fotografie, prezzi e fonti nello stesso sistema. Revisioni e differenze hardware restano distinte; gli originali vengono conservati nello storico.</p>
    <button disabled={busy} onClick={() => action(async () => setRegional(await api('/admin/regional/preview')))}>Anteprima varianti regionali</button>
    {regional && <>
      <p>{regional.removed} schede regionali da accorpare in {regional.groups.length} gruppi. Totale risultante: {regional.remaining} sistemi.</p>
      <details><summary>Gruppi da accorpare</summary><ul>{regional.groups.map(g => <li key={g.target_id}>
        <b>{g.manufacturer} · {g.model_name}</b>: {g.sources.map(s => s.name).join('; ')}
      </li>)}</ul></details>
      <button disabled={busy || !regional.removed} onClick={() => action(async () => {
        const result = await api('/admin/regional/apply', { method: 'POST', body: JSON.stringify({ token: regional.token }) });
        setRegional(null); setPreview(null); setMessage(`Accorpate ${result.removed} schede regionali. Restano ${result.remaining} sistemi; configurazioni e originali conservati.`); onSaved();
      })}>Accorpa le varianti regionali proposte</button>
    </>}
    <h4>Descrizioni italiane e arricchimento documentato</h4>
    <p>Completa le descrizioni vuote con brevi sintesi italiane e aggiunge i dati disponibili nel pacchetto versionato AppleDB/MAME. Conserva le descrizioni già scritte e i valori esistenti: eventuali differenze restano in revisione.</p>
    <p>I dati video/audio e le opzioni RAM dell'emulatore sono etichettati MAME. Le informazioni documentali e i prezzi hanno fonti separate; il pacchetto contiene cinque prezzi IBM RT, non prezzi per l'intero catalogo.</p>
    <button disabled={busy} onClick={() => action(async () => { setPreview(await api('/admin/enrichment/preview')); setProgress(null); })}>Anteprima arricchimento</button>
    {preview && <>
      <p>{preview.total} sistemi esistenti. Descrizioni mancanti: {preview.coverage.missing_descriptions}.
        Schede con dati aggiuntivi disponibili: {preview.coverage.models_with_additions}; con prezzi: {preview.coverage.models_with_prices}.</p>
      <details><summary>Esempi delle descrizioni proposte</summary>{preview.examples.map((p,i) => <p key={i}><b>{p.model_name}</b>: {p.description || 'Descrizione già presente: conservata.'}</p>)}</details>
      <button disabled={busy || !preview.total} onClick={() => action(enrich)}>Applica arricchimento ai sistemi esistenti</button>
    </>}
    {busy && running.current && <button onClick={() => { running.current = false; }}>Ferma dopo il lotto corrente</button>}
    {progress && <p role="status">Elaborate {progress.done} di {progress.total}; aggiornate {progress.updated}; conflitti da controllare {progress.conflicts}.</p>}
    {error && <p role="alert" className="inline-error">{error}</p>}
    {message && <p role="status" className="inline-success">{message}</p>}
    <p className="muted">Operazioni locali esplicite. Nessun nuovo modello creato dall'arricchimento. Non occorre svuotare o ricaricare il catalogo. Mantieni aperta la sezione; dopo un'interruzione puoi rieseguire l'anteprima e ripartire senza duplicare i dati.</p>
  </details>;
}
