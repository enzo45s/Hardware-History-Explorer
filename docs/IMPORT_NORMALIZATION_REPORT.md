# Normalizzazione e campione ampliato — 12 novembre 2026

Sviluppo sul branch `feat/historical-data-import`. Nessuna modifica diretta
o merge su `main`; nessuna nuova migrazione e nessuna dipendenza aggiunta.

## Cambiamenti

- `backend/app/importing/vocabulary.py`: alias conservativi, conversioni
  dimensionali esplicite, abbinamento delle specifiche precedenti e confronto
  fra quantità equivalenti. RAM/ROM, bit/byte e unità storiche ambigue restano
  distinti. Valori estremi non diventano Infinity o zero inventati.
- `normalize.py`, `engine.py`: normalizzazione prima della validazione,
  deduplicazione fra etichette equivalenti e revisione coerente delle quantità.
  Non vengono riscritti automaticamente etichette, quantità o ID precedenti.
  Abbinamenti ambigui falliscono con rollback della singola riga.
- `providers.py`: modelli CPU mantenuti, esclusione dei valori `rumored`,
  conservazione delle parti hardware e delle date esplicitamente di annuncio.
- `presentation.py`, `router.py`: nomi leggibili per produttori, mercati,
  categorie, date e valori; contesto della scheda e dati attuali della decisione.
  Originali e identificativi restano disponibili. Una decisione superata da
  modifiche successive richiede una nuova anteprima prima dell'accettazione.
- `frontend/src/ImportPanel.jsx`, `imports.css`: confronto fra valori proposti
  e attuali, citazione bibliografica separata, azione **Mantieni il dato attuale**.
- `backend/app/main.py`, `frontend/src/main.jsx`, `comparison-specs.js`:
  vista additiva `normalized` per schede e confronti, mantenendo i campi API
  originali e i valori editabili esistenti.
- `tools/prepare_retroflops_sample.py`: costruzione riproducibile dal commit
  ufficiale fissato, con licenza, originali e hash, senza esecuzione di codice
  upstream o download dei documenti primari.
- `docs/examples/retroflops-computers-19.json` e guida: campione ampliato
  attribuito, istruzioni Windows e corrispondenze da controllare.
- Test backend di normalizzazione, frontend dei confronti e browser ampliati;
  README, guida alle importazioni e descrizione PR aggiornati.

## Fonte e dati effettivamente provati

**RetroFlops**, CC BY 4.0, repository ufficiale al commit
`fbbed6181149b997329854e5808e0d036ad769e2`: **19 modelli, 26 configurazioni,
70 specifiche e 141 file originali conservati**. Non è un export live completo
del sito. Nessuna nuova fonte web è stata aggiunta e non è stato eseguito
scraping di siti HTML. I documenti primari non sono stati verificati
indipendentemente; nessuna asserzione viene promossa automaticamente.

Prova tramite API con due database isolati, SQLite temporaneo e PostgreSQL
in Docker: seed di 10 schede, precedente campione di quattro modelli, poi
campione ampliato con quattro associazioni esplicite ai modelli del seed.

| Passaggio | Esito su entrambi i database |
|---|---|
| Campione precedente | 4 importati, totale 14 |
| Campione ampliato | 11 importati, 4 aggiornati, 4 invariati, totale 25 |
| Ripetizione ampliato | 19 invariati, totale ancora 25 |
| Divergenze | 7 conflitti editoriali, nessuno quantitativo |
| Verifica automatica | 0 asserzioni verificate |

Sono stati preservati gli ID delle configurazioni e specifiche dei quattro
modelli precedenti. Il Mac mini M1 conserva separatamente i due gruppi di
core e la data di annuncio; non riceve una commercializzazione inventata.
I sette conflitti riguardano nomi, produttori e descrizioni del seed: richiedono
valutazione umana, non una fusione automatica. Dettagli e istruzioni nella
[guida al campione](examples/retroflops-computers-19.README.md).

## Verifiche

| Controllo | Esito |
|---|---|
| Suite backend SQLite | 111 passati, 1 saltato perché specifico PostgreSQL |
| Suite backend PostgreSQL in Docker | 112 passati |
| Test frontend | 22 passati |
| Build Vite | Riuscita |
| Build e avvio Compose isolato | Riusciti, API e database healthy |
| Chromium su Compose | Upload, applicazione esplicita, conflitto quantitativo e revisione, conflitto produttore leggibile e rifiuto motivato, confronto: riusciti |
| Layout scuro mobile | Nessun overflow a 320/390 px, anche con font locale più largo |
| Generatore campione | JSON validato, 549.905 byte, 19 record |
| Diff e compilazione Python | Riusciti |

Screenshot della sessione in `/workspace/hhe-normalization-artifacts/`.
I test browser creano esclusivamente fixture sintetiche nel progetto Compose
di prova. Non è stato toccato il database sul computer dell'utente.

Restano gli avvisi già esistenti: bundle Vite oltre 500 kB e deprecazione
TestClient/httpx. La CI remota va confermata su GitHub dopo il push; una prova
locale riuscita non certifica l'esito remoto. Non sono stati riprovati il
servizio AI esterno o recuperi live dai siti bloccati dal proxy.
