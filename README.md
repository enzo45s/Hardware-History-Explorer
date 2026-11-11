# Hardware History Explorer — versione 1.1 (fotografie)

Web app per esplorare la storia dei calcolatori commerciali: timeline, catalogo, gallerie fotografiche, schede, confronti, statistiche e assistente AI basato sui dati archiviati.

## Avvio con Docker

1. Installa Docker Desktop / Docker Engine e Docker Compose.
2. Estrai l'archivio e apri il terminale nella cartella `hardware-history-explorer`.
3. Facoltativo: copia `.env.example` in `.env` e configura `OPENAI_API_KEY` per l'assistente.
4. Esegui `docker compose up --build -d`.
5. Apri **http://localhost:8080**. API e documentazione Swagger: **http://localhost:8000/docs**.
6. Arresto: `docker compose down` (i dati e le fotografie caricate restano nei volumi Docker).

Se stai **aggiornando la versione 1.0**, scompatta la nuova versione in una cartella e assicurati di avviare Compose dallo **stesso progetto/cartella**, così Docker può riutilizzare i precedenti volumi. Per backup e migrazione tra cartelle Compose usa un nome progetto stabile (`docker compose -p hardware-history-explorer ...`) e verifica i volumi. Non eseguire `docker compose down -v` perché elimina i volumi, incluse le immagini.

## Aggiungere le fotografie

1. Apri il **Catalogo** (o la Timeline), poi una scheda con **Dettagli**.
2. Scorri fino alla sezione **Galleria fotografica** e clicca **Gestisci fotografie**.
3. Scegli una di tre opzioni:
   - **Cerca su Commons** — cerca fotografie su [Wikimedia Commons](https://commons.wikimedia.org/), visualizza i risultati con dati su licenza/autore e clicca **Aggiungi** su quella corretta. Richiede connessione Internet al servizio Wikimedia Commons da parte del backend. L'app non scarica il file: salva un URL online e i metadati disponibili.
   - **Carica un file** — carica un file JPEG, PNG, WebP o GIF (max 10 MB e 20 megapixel); il backend lo verifica, converte in WebP statico (incluso il primo fotogramma di un GIF), rimuove i metadati incorporati e lo salva nel volume Docker `image_uploads`.
   - **Inserisci URL** — usa il collegamento diretto HTTPS di un'immagine sul Web; puoi aggiungere didascalia, fotografo, fonte e licenza.
4. Puoi aggiungere **più immagini per sistema**, selezionare una **Copertina** e cancellare quelle non più necessarie. La copertina appare nel Catalogo, nella Timeline e nella tabella di confronto.

**Fonti fotografiche:** le foto non sono per forza utilizzabili liberamente. Controlla che mostrino proprio il modello descritto e verifica diritti, licenza, obblighi di attribuzione, condizioni per modifiche e eventuali requisiti di condivisione allo stesso modo. I metadati estratti automaticamente possono essere incompleti. Il progetto espone il link della fonte originale e quello della licenza quando presenti.

## Sviluppo senza Docker

Backend (Python 3.12+, verificato su Linux e Docker):

```bash
cd backend
python -m venv .venv
# attiva il virtualenv
pip install -r requirements.lock
uvicorn app.main:app --reload
```

Se hai creato `.env` nella radice del repository, avvia con `uvicorn app.main:app --reload --env-file ../.env`; il comando senza `--env-file` usa solo le variabili già esportate.

In assenza di `DATABASE_URL` si usa SQLite (`hardware_history.db`); le fotografie vengono salvate in `backend/uploads` a meno che non sia impostato `UPLOAD_DIR`.

Frontend (Node.js 20+):

```bash
cd frontend
npm ci
npm run dev
```

Apri **http://localhost:5173**. Vite inoltra `/api` e `/media` a FastAPI sulla porta 8000.

## API fotografie

| Metodo | Percorso | Scopo |
|---|---|---|
| `GET` | `/api/computers/{id}/images` | Elenco immagini |
| `POST` (JSON) | `/api/computers/{id}/images` | Inserimento da URL HTTPS |
| `POST` (multipart) | `/api/computers/{id}/images/upload` | Upload e conversione locale |
| `POST` | `/api/computers/{id}/images/{image_id}/primary` | Imposta la copertina |
| `DELETE` | `/api/computers/{id}/images/{image_id}` | Elimina un'immagine |
| `GET` | `/api/images/search?q=...` | Ricerca Wikimedia Commons |

La struttura dati comprende ora **19 tabelle**: le 18 originali più `computer_images`. Il campo storico `computers.image_url` resta per compatibilità con database esistenti. I media vengono restituiti tramite `/media/<nome>.webp` e non sono inclusi nelle risposte testuali dell'assistente AI.

## Altre funzionalità

- Timeline ordinata per primo lancio commerciale, con precisione storica delle date.
- Catalogo filtrabile per nome, produttore, categoria e anni.
- Schede con specifiche, configurazioni, mercati, dati di vendita, recensioni, fatti e fonti.
- Confronti tra 2–5 sistemi, analisi e distribuzioni statistiche.
- Assistente AI opzionale: solo dati del database, nessun accesso arbitrario a SQL.

## Stato dei dati e sicurezza

I **10 sistemi iniziali sono esempi dimostrativi**, non un corpus storico verificato, e non includono necessariamente fotografie: puoi inserirle dalla nuova interfaccia. I campi che non hanno dati non vengono inventati.

Questo progetto è progettato per uso **locale single-user**: gli endpoint di modifica (compresi upload e cancellazione) **non richiedono autenticazione**. Non esporre la porta API, il frontend o il database a Internet senza autenticazione, autorizzazioni, limiti di richiesta e configurazione di sicurezza adeguati. Per una distribuzione pubblica è necessario aggiungere anche backup e migrazioni database (es. Alembic). `create_all()` crea le tabelle mancanti ma non aggiorna automaticamente tabelle preesistenti con colonne nuove; in questa release si aggiunge soltanto la tabella separata delle immagini.

## Test

```bash
cd backend
pytest -q
```

## Correzioni, dipendenze e verifiche

Vedi [il rapporto tecnico](docs/REVIEW.md) per architettura, correzioni, limiti e risultati. I filtri per anno si riferiscono alla **prima commercializzazione** del sistema; sono validi gli anni da 1 a 9999. Il catalogo legge tutte le pagine API e ignora le risposte di ricerche ormai superate.

Usa `backend/requirements.lock` e `npm ci` per riprodurre le versioni verificate. `backend/requirements.txt` mantiene i requisiti diretti; dopo un aggiornamento intenzionale, aggiorna il lock da un virtualenv pulito e riesegui test e audit. Pillow 13 è richiesto per le correzioni di sicurezza della libreria immagini.

```bash
cd backend
python -m pytest -q
cd ../frontend
npm test
npm run build
npm audit
```

I test backend usano database e upload temporanei. Per testare PostgreSQL, crea un database **dedicato** con nome che termina in `_test` e imposta `HHE_TEST_DATABASE_URL` prima di `python -m pytest -q`. La suite ricrea le tabelle in quel database: non indicare il database dell'applicazione. In assenza della variabile usa SQLite. La CI esegue entrambe le modalità, i test/build frontend e la build Docker.

### Database già esistenti

`create_all()` non modifica i vincoli di tabelle già presenti. Per applicare il nuovo controllo sulla scala delle recensioni, fai un backup, ferma l'API ed esegui da `backend`:

```bash
# DATABASE_URL deve indicare il database da migrare, tramite ambiente sicuro.
python -m migrations.review_score
```

La migrazione supporta PostgreSQL e SQLite, è ripetibile e preserva righe e riferimenti. Si ferma senza modificare dati se trova punteggi fuori scala, uno schema inatteso o violazioni di chiave esterna. I punteggi richiedono `max_score` positivo; prima di riprovare, esamina e correggi consapevolmente gli eventuali dati storici invalidi. In Docker il modulo è incluso nell'immagine API: con l'API fermata puoi usare `docker compose run --rm --no-deps api python -m migrations.review_score` mentre il database è avviato. Non usare `down -v`.

### Proxy HTTPS con CA privata

Solo se la rete usa una CA privata affidabile, indica un bundle PEM con radici pubbliche e CA del proxy e usa l'override opzionale:

```bash
export PROXY_CA_BUNDLE=/percorso/assoluto/ca-bundle.pem
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up --build -d
```

Il bundle viene montato come secret durante la build e in sola lettura nell'API; la verifica TLS rimane attiva. L'accesso di rete deve comunque consentire registri npm/PyPI, `commons.wikimedia.org` per la ricerca, `upload.wikimedia.org` per visualizzare le fotografie Commons e `api.openai.com` per l'assistente opzionale.

Le porte Docker sono limitate a localhost. L'app resta single-user, senza autenticazione: prima di un'esposizione remota servono controlli degli accessi e limiti delle richieste. Non inserire chiavi o credenziali nei file versionati.

## Pannello amministrativo

Dal menu **Amministrazione** puoi inserire e modificare calcolatori e fonti bibliografiche, aggiungere produttori/categorie/mercati e aggiornare commercializzazioni e specifiche tecniche. Le schede conservano fotografie e altri dati storici già archiviati. Le modifiche sono applicate con il pulsante Salva; il pannello segnala quelle non salvate.

La gestione delle fotografie resta disponibile nella normale scheda del calcolatore, raggiungibile anche dal pannello. Non serve una migrazione aggiuntiva del database. Vedi [la guida del pannello](docs/ADMIN.md) per campi, date, fonti e API. Il pannello segue la modalità locale single-user del progetto.

### Problemi nella ricerca Wikimedia Commons

La ricerca Commons è gratuita e non usa la chiave OpenAI. Il backend si identifica con lo User-Agent `HardwareHistoryExplorer/1.2 (https://github.com/enzo45s/Hardware-History-Explorer)`, richiede esplicitamente il formato JSON con pagine indicizzate e attende fino a 30 secondi per ciascuna fase della richiesta HTTP.

Gli errori distinguono ora timeout (504), limitazione/sovraccarico Wikimedia (503, conservando `Retry-After` numerico), HTTP 403, problemi del proxy, certificati HTTPS e risposte inattese. Un risultato senza fotografie rimane una ricerca riuscita con elenco vuoto. Non disabilitare la verifica TLS: per una CA privata usa l'override proxy descritto sopra.

Dopo un aggiornamento, ricostruisci e ricrea i servizi con `docker compose up --build -d`. Puoi consultare `docker compose logs --tail=100 api`: i messaggi `Wikimedia search failed` indicano categoria e stato upstream senza includere testo della ricerca, risposte remote o credenziali del proxy.

Una risposta HTTP 200 a una richiesta `siteinfo` conferma la raggiungibilità, ma non prova che una ricerca completa funzioni. Verifica anche l'operazione di ricerca dallo stesso container API: User-Agent, parametri e tempi di risposta possono differire da quelli del browser. Nelle reti con policy restrittive deve essere consentito l'accesso a `commons.wikimedia.org`.
