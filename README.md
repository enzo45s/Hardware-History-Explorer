# Hardware History Explorer — versione 1.1 (fotografie)

Web app per esplorare la storia dei calcolatori commerciali: timeline, catalogo, gallerie fotografiche, schede, confronti, statistiche e assistente AI basato sui dati archiviati.

La navigazione fra sezioni, l'apertura/chiusura delle schede e il cambio di
sezione amministrativa riportano la pagina in cima. Aggiornamenti dei dati e
ricerche nella stessa vista conservano la posizione di lettura.

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

La sezione **Amministrazione → Importazioni** permette di caricare CSV/JSON,
preparare anteprime, controllare duplicati, applicare aggiornamenti incrementali,
revisionare conflitti e fonti e ripetere tentativi falliti. Sono disponibili
adattatori Wikidata e RetroFlops, oltre al caricamento manuale autorizzato.
Originali e decisioni restano nello storico; nessun dato diventa verificato
automaticamente. Non vengono importati automaticamente dataset o fotografie
all'avvio.

Vedi [la guida alle importazioni](docs/IMPORTING.md) per formati, migrazione,
CLI, API e test, e [la valutazione delle fonti](docs/IMPORT_SOURCES.md) per
licenze e blocchi effettivamente riscontrati. È incluso un campione reale Apple II
con attribuzione RetroFlops, CC BY 4.0, e un [campione ampliato di 19 modelli](docs/examples/retroflops-computers-19.README.md)
con CPU e misure tecniche corredate di fonte. La normalizzazione uniforma alias
e unità esplicite senza riscrivere i dati originali; i conflitti mostrano i
nomi proposti e attuali, separati dalla citazione bibliografica.
Per alias già duplicati, citazioni tecniche e prezzi mancanti vedi
[la guida alla riconciliazione](docs/RECONCILIATION.md): anteprima e scelta della
scheda da mantenere, trasferimento dei dati e storico degli originali.
Per ripartire con zero macchine usa **Svuota archivio per un nuovo import**:
[guida, backup e ambito del reset](docs/ARCHIVE_RESET.md). Il reset richiede
anteprima e conferma esplicita, conserva fonti e storico e impedisce che i
dieci sistemi dimostrativi ricompaiano al riavvio.

Per una prova più ampia è disponibile il [corpus MAME da 1.139 schede in cinque lotti](docs/datasets/mame-0276/README.md),
con indice di copertura e originali. CPU, clock e RAM sono esplicitamente dati
dell'emulatore, distinti dalle specifiche storiche verificate. Non contiene prezzi
né costituisce un catalogo commerciale completo: tutte le asserzioni restano da revisionare.

Dal menu **Amministrazione** puoi inserire e modificare calcolatori e fonti bibliografiche, aggiungere produttori/categorie/mercati e aggiornare commercializzazioni e specifiche tecniche. Le schede conservano fotografie e altri dati storici già archiviati. Le modifiche sono applicate con il pulsante Salva; il pannello segnala quelle non salvate.

La gestione delle fotografie resta disponibile nella normale scheda del calcolatore, raggiungibile anche dal pannello. Non serve una migrazione aggiuntiva del database. Vedi [la guida del pannello](docs/ADMIN.md) per campi, date, fonti e API. Il pannello segue la modalità locale single-user del progetto.

### Problemi nella ricerca Wikimedia Commons

La ricerca parte dal solo nome del modello: per esempio `Apple Macintosh 128K`,
senza aggiungere il produttore davanti. Il testo resta modificabile.

La ricerca Commons è gratuita e non usa la chiave OpenAI. Il backend si identifica con lo User-Agent `HardwareHistoryExplorer/1.2 (https://github.com/enzo45s/Hardware-History-Explorer)`, richiede esplicitamente il formato JSON con pagine indicizzate e attende fino a 30 secondi per ciascuna fase della richiesta HTTP.

Gli errori distinguono ora timeout (504), limitazione/sovraccarico Wikimedia (503, conservando `Retry-After` numerico), HTTP 403, problemi del proxy, certificati HTTPS e risposte inattese. Un risultato senza fotografie rimane una ricerca riuscita con elenco vuoto. Non disabilitare la verifica TLS: per una CA privata usa l'override proxy descritto sopra.

Dopo un aggiornamento, ricostruisci e ricrea i servizi con `docker compose up --build -d`. Puoi consultare `docker compose logs --tail=100 api`: i messaggi `Wikimedia search failed` indicano categoria e stato upstream senza includere testo della ricerca, risposte remote o credenziali del proxy.

Una risposta HTTP 200 a una richiesta `siteinfo` conferma la raggiungibilità, ma non prova che una ricerca completa funzioni. Verifica anche l'operazione di ricerca dallo stesso container API: User-Agent, parametri e tempi di risposta possono differire da quelli del browser. Nelle reti con policy restrittive deve essere consentito l'accesso a `commons.wikimedia.org`.

## Ricerca dei sistemi nel confronto

In **Confronta**, usa **Cerca un sistema da aggiungere**: i suggerimenti appaiono mentre scrivi il nome del modello o del produttore. Ogni risultato mostra anche produttore e anno, quando disponibile. Scegli con un clic oppure con le frecce e Invio; Esc chiude i suggerimenti e il pulsante × cancella la ricerca.

I sistemi scelti rimangono visibili sotto la barra, con un pulsante per rimuoverli. Da due sistemi in poi la tabella si aggiorna immediatamente, fino al limite di cinque. La selezione da catalogo e timeline rimane disponibile. La ricerca nel confronto consulta tutto l'archivio, indipendentemente dai filtri lasciati nel catalogo, ed esclude i sistemi già selezionati.

Per evitare un elenco ingestibile, vengono mostrati fino a otto suggerimenti: se ce ne sono altri, affina il testo. Le richieste attendono una breve pausa di digitazione e le risposte obsolete sono ignorate. Sono previsti messaggi per caricamento, nessun risultato ed errore con Riprova.

L'endpoint `GET /api/computers/suggestions?q=...` cerca nel database e restituisce solo ID, nome, produttore e anno, senza caricare specifiche o altre relazioni. Accetta `limit` da 1 a 10 (il pannello usa 8) e fino a cinque `exclude_ids` ripetuti. La query massima è di 180 caratteri; `%` e `_` sono cercati letteralmente. Non sono necessarie migrazioni del database.

Verifiche della modifica: 74 test backend superati su PostgreSQL; 73 superati e 1 specifico PostgreSQL saltato su SQLite; 10 test frontend superati. Build e avvio Docker riusciti. Nel browser sono stati verificati tastiera, aggiunta/rimozione, limite, duplicati, ricerca oltre 100 record, filtri indipendenti, risultati vuoti, errori, risposte fuori ordine e layout mobile.

### Confronto tra configurazioni

Ogni colonna del confronto ha un menu **Configurazione**. L'opzione iniziale **Tutte le configurazioni** raggruppa i valori distinti senza sovrascriverli: per esempio, varianti con RAM da 4, 8 e 48 KB producono `4 / 8 / 48 KB`. Selezionando una configurazione specifica vengono usate esclusivamente le sue specifiche.

I valori comuni compaiono una sola volta; quelli numerici sono ordinati. Unità diverse restano esplicite, senza conversioni implicite. Se una proprietà è presente solo in alcune configurazioni, la cella ne indica il numero: gli altri dati rimangono sconosciuti. I valori raggruppati possono appartenere a combinazioni diverse; scegli una variante per un confronto preciso tra sistemi.

La scelta di ciascun sistema è indipendente e resta valida passando tra le sezioni o aggiungendo/rimuovendo gli altri sistemi nella stessa sessione della pagina. Rimuovere un sistema elimina la sua scelta; ricaricare la pagina azzera la selezione, come già avveniva per il confronto. Se una configurazione scelta non è più disponibile, viene mostrata la vista generale. Un sistema senza configurazioni conserva i dati del modello, con `—` per le specifiche mancanti.

Le configurazioni si inseriscono dal pannello amministrativo. Non è prevista un'ereditarietà automatica: una specifica comune va registrata nelle configurazioni a cui si applica. Fotografie, produttore, categorie e prima commercializzazione restano dati del modello. Questa modifica non altera schema o dati archiviati e non richiede migrazioni.

Verifiche: 16 test frontend superati, build frontend/Compose e prova browser con nove varianti RAM, dati parziali, unità miste, scelte indipendenti, conservazione della scelta, configurazioni rimosse, sistemi senza configurazioni, errori/riprova e layout mobile.

## Tema chiaro e Fosfori verdi

Il marchio nella barra laterale può usare due PNG originali: copia `logo-light.png`
(lettere blu) e `logo-dark.png` (lettere bianche) in `frontend/public/branding/`.
Il logo segue il tema effettivo, comprese le variazioni del sistema operativo e
la scelta manuale. I colori dell'immagine restano invariati; nel tema chiaro
viene usato un piccolo pannello chiaro e su mobile il logo è ridotto. Se un file
manca o non è leggibile, rimane disponibile il marchio precedente. I PNG della
chat non sono inclusi: vedi [le istruzioni dei loghi](frontend/public/branding/README.md).

Il selettore nella barra superiore offre tre modalità:

- **Sistema**: impostazione iniziale; segue la preferenza chiara/scura comunicata dal sistema operativo e dal browser, anche quando cambia durante l'uso.
- **Chiaro**: mantiene il tema chiaro indipendentemente dal sistema.
- **Fosfori verdi**: sfondi quasi neri, testi in gradazioni di verde e accenti luminosi. Caratteri, dimensioni e spaziatura dei testi sono gli stessi del tema chiaro. L'alone è limitato a logo e accenti del titolo; non viene applicato ai testi lunghi.

Su schermi piccoli il selettore mostra le icone; i nomi restano disponibili alle tecnologie assistive e nei suggerimenti dei pulsanti. Grafici, tooltip, moduli, autocomplete, confronti e gallerie seguono lo stesso tema. Fotografie e immagini caricate conservano i colori originali, senza filtri o inversioni. Errori e avvisi mantengono colori distinti.

La scelta viene salvata nel browser per l'indirizzo dell'app (`localStorage`, chiave `hardware-history-theme`) e sincronizzata tra schede dello stesso indirizzo. Se il salvataggio è bloccato, il selettore funziona comunque per la pagina corrente. Per riprendere il comportamento automatico basta scegliere **Sistema**. Il cambio di tema non ricarica la pagina e non cancella filtri, selezioni o moduli non salvati.

Il file pubblico `theme.js`, caricato prima dell'interfaccia React, applica la preferenza iniziale per evitare un lampo chiaro. I colori dei componenti usano variabili semantiche `--theme-*` con fallback ai colori chiari originali; la palette scura e i token dei grafici si trovano in `frontend/src/theme.css`. I grafici usano variabili CSS anche negli elementi SVG e nei tooltip. Non sono necessarie modifiche al database, credenziali o migrazioni.

Verifiche: 21 test frontend superati; build Docker/frontend e prove Chromium su avvio prima di React, modalità automatiche/manuali, ripristino dopo ricarica, eventi tra schede, storage bloccato, filtri e bozze conservati, grafici/tooltip, fotografie e viewport da 320 e 390 px. Verificato contrasto di almeno 4,5:1 su corpo del testo, input e pulsanti principali nel tema scuro; non si tratta di una certificazione di accessibilità dell'intera applicazione.
