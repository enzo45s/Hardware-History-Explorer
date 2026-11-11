# Resoconto importazioni — 11 novembre 2026

Branch `feat/historical-data-import`, base `feat/admin-panel` (`9c701fc`).
Nessuna modifica diretta o merge su main. Funzioni e dati precedenti preservati.

## Risultato implementato

ETL Python e amministrazione React funzionanti: anteprima persistente,
applicazione esplicita, esclusione di righe, corrispondenze manuali,
deduplicazione conservativa, aggiornamenti additivi, fonti per campo e
specifica, conflitti, verifiche umane motivate, storico e nuovi tentativi.
File originali, hash e normalizzati separati. Supportate le entità esistenti
Computer, Manufacturer, Category, Configuration, Specification, Market,
Release, Sale, Review, Fact e Source; nessuna fotografia importata o rimossa.

Il motore preserva quantità/unità, prezzo/valuta/tipo e punteggio/scala come
gruppi; non produce combinazioni mai dichiarate da una fonte. Le date parziali
mantengono precisione dove lo schema esistente la supporta. Le altre date
parziali sono respinte invece di inventare un giorno.

L'assistente cerca nell'intero catalogo anziché leggere solo le prime 100
schede, e riceve una selezione limitata con citazioni e stati di verifica.
Le API remote accettano solo endpoint ufficiali fissi, con timeout, limite
di risposta e senza redirect. Nessun crawler o fetch arbitrario è stato aggiunto.

## Fonti realmente esaminate e integrate

| Fonte | Esito concreto |
|---|---|
| RetroFlops | Letti repository, licenza contenuti, organizzazione dati, schema, generatore export e indice. Catalogo/export CC BY 4.0. Adattatore per JSON completo e fetch ufficiale; un campione reale derivato dai record canonici è incluso con attribuzione |
| Wikidata | Adattatore wbgetentities per QID espliciti, etichette, produttore e date supportate; testato con fixture. Nessun recupero live riuscito da questa rete |
| Oldcomputers.net | Caricamento manuale autorizzato; robots, struttura, termini e copertura non accertabili dalla rete cloud |
| 1000bit | Caricamento manuale autorizzato; stessi limiti di accesso |
| dev.computerhistory.org | Caricamento manuale autorizzato; stessi limiti di accesso |

Le richieste alle pagine dei cinque siti e ai robots sono state rifiutate dal
proxy con 403; questo non significa che i siti siano pubblicamente indisponibili.
Non è stato eseguito scraping massivo. Per dettagli: [valutazione fonti](IMPORT_SOURCES.md).

## Dati storici effettivamente importati

Database SQLite separato di prova `/tmp/hhe-real-import-final.sqlite`:

- **1 modello reale: Apple II**, da un sottoinsieme dei record canonici RetroFlops.
- Produttore, categoria, configurazione con RAM non specificata e data di
  commercializzazione a precisione mensile, come dichiarati dal dataset.
- **0 specifiche tecniche numeriche aggiunte**, perché il campione non contiene
  misurazioni; nessun valore di RAM inventato.
- **0 asserzioni verificate automaticamente**. Tutte restano pending.
- Una seconda applicazione del campione restituisce `unchanged: 1`; rimane
  un solo modello. I due tentativi sono conservati nello storico.

Il JSON include dichiarazione della trasformazione YAML → sottoinsieme JSON,
attribuzione e hash dei due file canonici scaricati. Non è presentato come
un download live dell'esportazione integrale. I record sintetici creati dai
test non sono dati storici e non sono inclusi in questi conteggi. Nessun
database sul computer dell'utente è stato modificato dal cloud.

## Verifiche eseguite

| Controllo | Esito |
|---|---|
| Dipendenze backend da requirements.lock e pip check | Installazione riuscita, nessuna dipendenza incoerente |
| npm ci | Riuscito con package-lock aggiornato; Playwright aggiunto solo come dipendenza di sviluppo |
| Suite SQLite completa | **97 passed, 1 skipped** (test specifico PostgreSQL) |
| Suite PostgreSQL completa in Docker | **98 passed**, database separato `hardware_history_import_test` |
| Test dedicati all'importazione | **24**, inclusi normalizzazione, deduplica, fonti, aggiornamenti, conflitti, prezzi/valute, stime, retry, limiti, rollback, alias, paginazione e release multiple |
| Test frontend | **21 passed** |
| Build Vite | Riuscita |
| docker compose config | Valida |
| Build e avvio Compose completo | Riusciti con CA proxy fidata e porte locali alternative; API e PostgreSQL healthy |
| Migrazione additiva ripetuta due volte | Riuscita, dati preservati |
| Chromium su Compose | Upload → anteprima → applicazione → conflitto → revisione umana → ricerca nel confronto: riusciti, nessun errore JavaScript |
| Tema scuro e viewport 320 px | Riusciti, nessun overflow orizzontale |
| CLI su campione reale e replay | Importazione 1 / invariata 1, senza duplicati |

Artefatti della sessione: `/workspace/hhe-import-artifacts/imports-desktop.png`
e `imports-mobile.png`; log finali in `/tmp/hhe-import-*-final.log`.
La CI è stata aggiornata con la stessa prova browser dopo l'avvio Compose;
non si dichiara una CI remota eseguita prima della disponibilità della PR.

Avvisi non bloccanti: Vite segnala il bundle principale oltre 500 kB e
Starlette segnala la futura deprecazione dell'integrazione TestClient/httpx.
Non sono fallimenti dei controlli. La generazione AI esterna e i recuperi
Wikidata/RetroFlops live non sono verificati in questa rete. Sono testati
recupero dei dati per l'assistente, adattamento e gestione dei fallimenti.

## File modificati o aggiunti rispetto alla base

- `backend/app/import_models.py`: quattro tabelle di audit additive.
- `backend/app/importing/__init__.py`, `__main__.py`: modulo ETL e CLI.
- `backend/app/importing/normalize.py`: formati e validazione.
- `backend/app/importing/providers.py`: fonti e adattatori autorizzati.
- `backend/app/importing/engine.py`: staging, matching, applicazione e verifica.
- `backend/app/importing/router.py`: API amministrative.
- `backend/app/assistant_context.py`, `backend/app/main.py`: integrazione API,
  registrazione dei modelli e recupero del contesto con fonti.
- `backend/migrations/historical_imports.py`: migrazione ripetibile.
- `backend/tests/test_imports.py`: 24 prove automatiche nuove.
- `frontend/src/ImportPanel.jsx`, `imports.css`: interfaccia completa.
- `frontend/src/AdminPanel.jsx`: nuova scheda Importazioni.
- `frontend/nginx.conf`: timeout specifico per i lotti d'importazione.
- `frontend/tests/browser/imports.cjs`: prova browser ripetibile.
- `frontend/package.json`, `package-lock.json`: comando browser e Playwright.
- `.github/workflows/test.yml`: estensione CI a Compose e browser.
- `README.md`, `docs/IMPORTING.md`: istruzioni operative.
- `docs/IMPORT_PLAN.md`, `IMPORT_SOURCES.md`, `IMPORT_REPORT.md`, `IMPORT_PR.md`:
  piano, fonti, esiti e descrizione della PR.
- `docs/examples/retroflops-apple-ii.snapshot.json`: campione reale attribuito.
- `docs/source-audit/retroflops-apple-ii.yaml`,
  `retroflops-apple-ii-reference-manual.yaml`, `retroflops-license.txt`,
  `retroflops-readme.txt`: documenti originali consultati e attribuiti.

I dati dimostrativi già presenti non sono stati riscritti e non si eseguono
importazioni automatiche all'avvio. Per istruzioni e limiti di abbinamento
vedi [la guida](IMPORTING.md).

## Consegna GitHub

Cinque commit coerenti sono stati inviati al branch della funzionalità, seguiti
da questo aggiornamento del resoconto. La creazione effettiva della PR con
`gh pr create --base feat/admin-panel --head feat/historical-data-import`
è stata tentata ma bloccata con `Post https://api.github.com/graphql: Forbidden`
(HTTP 403). Il push Git è riuscito; non è un rifiuto automatico di approvazione.
Non viene dichiarata una PR già aperta o una CI remota già eseguita.

[Apri il confronto per creare la PR](https://github.com/enzo45s/Hardware-History-Explorer/compare/feat/admin-panel...feat/historical-data-import?expand=1).
Titolo proposto: «Importazione storica con staging, fonti e revisione dei conflitti»;
descrizione pronta in [IMPORT_PR.md](IMPORT_PR.md). Il riferimento remoto di
main è rimasto `6f96f2b79bc2a6dd59e419e2a1037ccbd6b5ded2`.
