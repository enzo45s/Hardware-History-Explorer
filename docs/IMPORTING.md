# Importazione dati storici

Il sistema riutilizza le entità del catalogo e i collegamenti alle fonti.
Non esegue scraping HTML né importa fotografie automaticamente. Prima di
caricare materiale di terzi leggi [la valutazione delle fonti](IMPORT_SOURCES.md).

## Avvio e migrazione

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose up --build -d
```

L'avvio crea sei tabelle additive: `import_jobs`, `import_rows`,
`import_identities`, `import_claims`, `catalog_reconciliations`, `archive_resets`.
Le ultime due conservano l'audit delle riconciliazioni e degli svuotamenti
esplicitamente richiesti dall'operatore. Un aggiornamento non svuota il catalogo.
Nessuna tabella del catalogo viene
ricreata e nessun dato viene cancellato. Non servono nuove variabili d'ambiente
o chiavi API per gli importatori. Per una migrazione esplicita, dopo un backup
e con il database avviato:

```bash
docker compose stop api web
docker compose run --rm --no-deps api python -m migrations.historical_imports
docker compose up -d
```

Migrazione ripetibile su PostgreSQL e SQLite. Non sostituisce la migrazione
`migrations.review_score` richiesta dai vecchi database. Non usare `down -v`.

## Utilizzo

1. Apri **Amministrazione → Importazioni** e seleziona la fonte.
2. Carica CSV/JSON autorizzati confermando i diritti di riuso, oppure recupera
   l'esportazione RetroFlops o fino a 20 QID dall'API Wikidata.
3. Controlla originali, normalizzati e corrispondenze. L'anteprima conserva
   l'audit, senza cambiare il catalogo. Le righe non valide riportano il motivo.
   Per una corrispondenza ambigua cerca e seleziona il calcolatore esistente.
   Puoi escludere singole righe prima dell'applicazione, ad esempio componenti,
   prototipi o record che non identificano un calcolatore commerciale. Seleziona
   QID Wikidata pertinenti: l'adattatore non certifica la classificazione storica.
4. Premi **Applica le righe pronte all'archivio**. Ogni riga ha un savepoint:
   un errore non annulla le altre. Controlla importati, aggiornati, invariati,
   scartati, falliti, ambigui e conteggi degli stati delle asserzioni.
5. Apri **Fonti e verifiche**. I conflitti conservano il dato esistente; puoi
   accettare il valore proposto con una motivazione oppure rifiutare quella
   fonte per l'asserzione. Nessuna verifica è automatica.

Le decisioni mostrano nomi leggibili (per esempio **Produttore: Apple Computer**
contro **Apple**) e il contesto della scheda/configurazione. **Fonte a supporto**
è la citazione: il titolo di un manuale non è il produttore proposto.
**Mantieni il dato attuale** rifiuta solo quella asserzione, senza eliminare la
fonte dalla bibliografia. Gli identificativi originali restano espandibili.
Se il dato è cambiato dopo l'importazione, prepara una nuova anteprima prima
di accettare; il pulsante è disabilitato per una decisione ormai superata.

Rifiutare una fonte non cancella retroattivamente valori già inseriti: usa
l'editor per correggere il catalogo. Nessuna importazione cancella fotografie,
configurazioni o dati assenti nel nuovo file. I collegamenti `*_sources`
preesistenti conservano lo stato prudenziale pending; le decisioni dettagliate
sono nelle asserzioni `import_claims`.

**Riprova** crea una nuova anteprima collegata al tentativo precedente. Per
fonti remote ripete il recupero; per upload riusa il file conservato. Per
correggere un file devi caricarne una nuova versione. Un lavoro già applicato
non viene riapplicato; ripetere un file non duplica le entità ma conserva nuovi
eventi di audit. Le decisioni registrate non vengono riscritte. Se il valore
è cambiato nel frattempo, la verifica risponde 409: crea una nuova anteprima.
La nuova anteprima ripristina anche le righe escluse: ricontrolla le selezioni.

L'archivio è locale e single-user: nessuna autenticazione è aggiunta. Le porte
Compose restano limitate a localhost. Non esporre queste API su Internet senza
protezioni adeguate. L'audit non è crittograficamente immutabile rispetto a
chi può modificare direttamente il database.

## Formato canonico CSV/JSON

JSON: elenco di oggetti oppure `{"records": [...]}`. Questo esempio è
**sintetico e non è un dato storico**:

```json
[
  {
    "external_id": "esempio-1",
    "manufacturer": "Produttore di esempio",
    "model_name": "Modello di esempio",
    "source": {
      "title": "Fonte di esempio — sostituire con una fonte reale",
      "url": "https://example.org/dataset",
      "license": "Indicare la licenza effettiva"
    },
    "categories": ["Personal computer"],
    "releases": [{"market": "Mercato di esempio", "release_date": "1980"}],
    "configurations": [{
      "variant_name": "Configurazione di esempio",
      "specifications": [{"component_type": "RAM", "property_name": "Capacità", "numeric_value": 4, "unit": "KB"}]
    }]
  }
]
```

| Entità | Altri campi supportati |
|---|---|
| Computer | `description`, `announcement_date`, `categories` |
| Configuration | `variant_name`, `description`, `specifications` |
| Specification | `component_type`, `component_name`, `property_name`, un solo `numeric_value` o `text_value`, `unit` |
| Release | `market`, `release_date`, `discontinuation_date`, `price`, `currency` ISO a tre lettere, `price_type` |
| Sale | `market`, `period_start`, `period_end`, `units_sold`, `metric_type`, `estimated` |
| Review | `publication`, `review_date`, `score`, `max_score`, `summary` |
| Fact | `fact_type`, `statement`, `reference_date` |

Ogni elemento può avere `source`, `evidence` (localizzatore/passaggio breve) ed
`estimated`. La fonte si eredita dalla configurazione e infine dal modello.
Le fonti supportano `title`, `url`, `author`, `publisher`, `license`, `access_date`,
`publication_date` e `source_type` (predefinito `dataset`; per esempio `book`).
Ogni specifica ha anche il normale collegamento `specification_sources`.

Annuncio/lancio/fine supportano `AAAA`, `AAAA-MM`, `AAAA-MM-GG` conservando la
precisione. Lo schema preesistente di vendite/recensioni/fatti non ha precisione:
le loro date devono essere complete oppure omesse. Date parziali non diventano
giorni inventati. Per «circa» usa una data ISO con `estimated: true`; testi
ambigui vengono rifiutati. `null` e omissione restano ignoti; zero resta zero.
Prezzi senza valuta, punteggi senza scala, numeri non finiti e intervalli
invalidi vengono rifiutati.

CSV: UTF-8, intestazioni uguali ai campi JSON. `manufacturer`, `model_name` e
`source` sono obbligatori. `source`, `configurations`, `releases`, `sales`,
`reviews`, `facts` sono colonne JSON con quoting CSV standard. `categories`
usa `|` come separatore. I campi extra vengono rifiutati: adatta le colonne
prima dell'upload. Nessuna formula viene eseguita. Limiti: **8 MB e 1000 righe**
per lotto; suddividi dataset più grandi.

## Deduplicazione e qualità

Per ripartire da zero usa [il reset controllato dell'archivio](ARCHIVE_RESET.md):
anteprima, backup, conferma esplicita e catalogo vuoto anche al riavvio.
Lo storico e le fonti restano conservati; le vecchie corrispondenze non
vengono riutilizzate dai nuovi import.

Nomi normalizzati con Unicode NFKC, spazi e confronto senza maiuscole. Gli alias
espliciti di produttori e modelli sono riconosciuti da `importing/identity.py`
(per esempio Apple/Apple Computer e IBM PC 5150/IBM Personal Computer 5150).
Una corrispondenza univoca riusa scheda e nome esistenti; più corrispondenze
richiedono una decisione. Non si fondono automaticamente nomi solo simili.
Per duplicati già creati usa la [riconciliazione con anteprima](RECONCILIATION.md).
Famiglie e modelli specifici, come System/360 e Model 50, restano distinti. `4 kbytes`
diventa `4 KB`, ma `KB`, `KiB` e `kb` rimangono distinti. Non si convertono
valute o unità ambigue. Non sono previste traduzioni automatiche dei nomi.

Il vocabolario delle specifiche uniforma alias espliciti: `main-cpu` diventa
`CPU`, `clock-frequency` diventa `Frequenza`, `memory-capacity` diventa
`Capacità`. RAM e ROM restano distinte; `system-memory` senza indicazioni
univoche resta **Memoria**. Le frequenze CPU/GPU in Hz/kHz/MHz/GHz sono
espresse in MHz; le capacità in B/KiB/MiB/GiB in KiB. `KB`, `MB`, `GB` e bit
restano distinti dalle unità IEC. I dati originali non vengono riscritti:
upload e asserzioni mantengono l'audit, e le API delle schede aggiungono una
vista `normalized` alle specifiche mantenendo i campi originali. Anche le
specifiche precedenti si abbinano per significato e quantità equivalente,
senza duplicarle o cambiare automaticamente i loro identificativi.

Le frequenze di parti hardware differenti (per esempio core prestazioni ed
efficienza) restano proprietà separate. I valori RetroFlops `rumored` non
diventano stime attendibili e sono esclusi; restano negli originali. Una data
esplicitamente descritta dalla fonte come annuncio non diventa una data di
commercializzazione. Queste regole non certificano l'attendibilità storica.

L'identità è `(fonte, external_id)`; per file generici l'ID è anche separato
per URL della citazione, o titolo/autore per fonti senza URL. Altrimenti il
motore cerca produttore e modello normalizzati, includendo gli alias espliciti. Più corrispondenze
richiedono una scelta. Gli abbinamenti manuali sono mantenuti dalle identità
esterne; eventuali nomi discordanti producono asserzioni in conflitto.

Le configurazioni si abbinano per nome; le specifiche per componente,
proprietà e nome nella configurazione. Quantità/unità, prezzo/valuta/tipo,
punteggio/scala e quantità venduta/stima/metrica sono gruppi indivisibili.
I valori mancanti vengono aggiunti; le discordanze non sono sovrascritte.
Release: mercato, e data se multiple; vendite: mercato/intervallo/metrica;
recensioni: testata/data; fatti: tipo/testo. Le ambiguità non vengono fuse.

## Fonti integrate e campione reale

- **RetroFlops**: esportazione completa `catalog-v1.json` da caricare oppure
  recuperare dall'URL ufficiale fisso. Solo mainframe, minicomputer, home
  computer, personal computer e workstation; configurazioni e misure numeriche
  conservano contesto e riferimenti. Le misure ignote non diventano zero.
  Quando il componente principale è esplicitamente una CPU e ne è indicato il
  nome, viene aggiunta la specifica testuale **CPU · Modello**, anche in assenza
  di una frequenza nota. Il nome non viene dedotto dall'architettura.
  Attribuzione RetroFlops, CC BY 4.0, con adattamenti dichiarati.
- **Wikidata**: `wbgetentities`, etichette e statement, poi etichette dei
  produttori. Richiede un produttore univoco. Date P577 senza qualificatori e
  con calendario gregoriano; P571 non viene reinterpretata come lancio.
  Nessuna fotografia o pagina enciclopedica viene importata. Per upload includi
  anche le entità dei produttori e `requested_ids` nell'oggetto JSON.
- **Oldcomputers, 1000bit, Computer History Museum**: caricamento canonico
  manuale autorizzato, nessun adattatore HTML automatico abilitato.

I metadati non mappati restano nel file originale con SHA-256. Per Wikidata lo
snapshot aggrega le risposte entità e produttori utilizzate. I timeout e il
limite di risposta di 8 MB sono applicati a URL fissi, senza redirect o fetch
di URL arbitrari. I blocchi di rete restano lavori falliti ripetibili.

`examples/retroflops-apple-ii.snapshot.json` è un campione reale derivato dai
record canonici ufficiali Apple II e della fonte. La trasformazione YAML →
sottoinsieme JSON, attribuzione e impronte sono dichiarate: non è il download
dell'esportazione live. Non contiene misure tecniche; quelle assenti restano
ignote. Nel database dimostrativo il nuovo registro di alias riusa l'Apple II
esistente anche con «Apple Computer» e «Apple». Se esistono già due schede,
controlla prima i duplicati o scegli esplicitamente la corrispondenza.

Sono disponibili anche il [campione di quattro modelli](examples/retroflops-home-computers-4.README.md)
e il [campione ampliato di 19 modelli](examples/retroflops-computers-19.README.md),
con modelli CPU e misure corredate di fonte. Quest'ultimo comprende 26
configurazioni e 70 specifiche. Le istruzioni descrivono le associazioni
manuali da controllare e i risultati delle importazioni in database separati.
Nessun dato è stato verificato automaticamente o importato sul computer
dell'utente dal cloud.

## CLI e API

Su un database già inizializzato, con `DATABASE_URL` corretto:

```bash
cd backend
python -m app.importing ../docs/examples/retroflops-apple-ii.snapshot.json --provider retroflops --rights-confirmed
```

Il comando conserva solo l'anteprima; aggiungi `--apply` per applicare le righe
pronte. Le dipendenze sono in `backend/requirements.lock`.

API sotto `/api/admin/imports`: `GET /providers`, `GET /` con limit/offset,
`POST /upload` multipart (`file`, `provider`, `rights_confirmed`), `POST /remote`
(`provider`, `ids`), `GET /{id}` con righe paginate, `GET /{id}/original`,
`POST /{id}/apply`, `POST /{id}/retry`, `POST /{id}/rows/{row_id}/match`
(`computer_id`), `POST /{id}/rows/{row_id}/skip`, `POST /claims/{claim_id}/review` (`decision: accept|reject`,
`note`). Il download originale è testo allegato, non HTML eseguibile.

Catalogo, timeline, analisi e confronti leggono subito le entità normali.
L'assistente cerca nell'intero catalogo e seleziona fino a 30 schede pertinenti
con fonti e stati, in un contesto JSON entro 60.000 caratteri. È una selezione,
non un elenco esaustivo; la generazione AI esterna richiede ancora chiave e
crediti e non è stata verificata con un servizio configurato in questa sessione.

## Verifiche

```bash
cd backend
python -m pytest -q
cd ../frontend
npm ci
npm test
npm run build
```

Per PostgreSQL usa `HHE_TEST_DATABASE_URL` con un database separato che termina
in `_test`: i test ne cancellano e ricreano le tabelle. Mai usare il database reale.

Prova browser su un progetto Compose di prova, perché crea record sintetici:

```bash
cd frontend
npx playwright install chromium
HHE_BASE_URL=http://127.0.0.1:8080/ npm run test:browser
```

È supportato `CHROMIUM_PATH` per un Chromium già installato. La CI esegue
SQLite, PostgreSQL, frontend, build, Compose e browser. I test sintetici non
sono dati storici pubblicati.
