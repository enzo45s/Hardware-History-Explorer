# Hardware History Explorer — versione 1.1 (fotografie)

Web app per esplorare la storia dei calcolatori commerciali: timeline, catalogo, gallerie fotografiche, schede, confronti, statistiche e assistente AI basato sui dati archiviati.

La sezione [Produttori](docs/MANUFACTURERS.md) permette di esplorare le aziende
con logo, profilo storico, fonti e sistemi censiti. Le schede sono collegate
ai computer e si arricchiscono da Amministrazione → Produttori.

È inclusa una [raccolta documentata dei profili](docs/MANUFACTURER_RESEARCH.md):
148 descrizioni italiane e 84 loghi per i 184 nomi esaminati, oltre ai dati
aziendali disponibili. Al primo avvio vengono completati solo i campi vuoti;
non servono chiavi API né una reimportazione del catalogo. In **Amministrazione
→ Produttori** puoi riapplicare la raccolta e scaricare il resoconto delle lacune.

La navigazione fra sezioni, l'apertura/chiusura delle schede e il cambio di
sezione amministrativa riportano la pagina in cima. Aggiornamenti dei dati e
ricerche nella stessa vista conservano la posizione di lettura.

Il [pacchetto RAM mancante](docs/datasets/ram-2026-11/README.md) aggiunge
quantità documentate per 147 sistemi della copia di catalogo esaminata.
L’importazione aggiorna solo schede esistenti ancora prive di una quantità
RAM, conserva i dati già presenti e include fonti e resoconto dei casi residui.

Nel [confronto e nelle schede tecniche](docs/TECHNICAL_SHEETS.md#ram-un-campo-principale-e-una-riga-per-le-opzioni)
la memoria compare in una riga **RAM**, con al massimo una seconda riga per
opzioni ed espansioni. Le diverse etichette delle fonti non creano più
caratteristiche separate. Le quantità RAM sono mostrate in KB/MB/GB;
originali, fonti e unità interne restano conservati.

La [pulizia fisica del catalogo](docs/PHYSICAL_CATALOG_CLEANUP.md) accorpa
configurazioni, specifiche e commercializzazioni direttamente nelle tabelle
principali. Dopo l'applicazione, gli originali accorpati restano nell'audit
e la precedente copia consolidata non viene più mantenuta. La normalizzazione
necessaria alle modifiche e alle importazioni rimane automatica.

La [normalizzazione della commercializzazione](docs/RELEASE_SUMMARIES.md) distingue
le date documentate dagli anni di riferimento delle varianti e accorpa date e
prezzi compatibili. Negli archivi già puliti, un aggiornamento delle regole
riesamina automaticamente tutte le schede nelle tabelle principali all'avvio.

Il precedente livello di [dati consolidati del catalogo](docs/CATALOG_CONSOLIDATION.md) è salvato
nel database e condivisi da schede, confronto e assistente. All'avvio l'API
esegue la migrazione additiva e il popolamento; modifiche e importazioni
aggiornano i sistemi interessati. Gli originali rimangono separati e tracciabili.
Gli strumenti amministrativi di manutenzione una tantum sono stati ritirati.

## Avvio con Docker

1. Installa Docker Desktop / Docker Engine e Docker Compose.
2. Estrai l'archivio e apri il terminale nella cartella `hardware-history-explorer`.
3. Facoltativo: copia `.env.example` in `.env` e configura `OPENAI_API_KEY` per l'assistente.
4. Esegui `docker compose up --build -d`.
5. Apri **http://localhost:8080**. API e documentazione Swagger: **http://localhost:8000/docs**.
6. Arresto: `docker compose down` (i dati e le fotografie caricate restano nei volumi Docker).

Se stai **aggiornando la versione 1.0**, scompatta la nuova versione in una cartella e assicurati di avviare Compose dallo **stesso progetto/cartella**, così Docker può riutilizzare i precedenti volumi. Per backup e migrazione tra cartelle Compose usa un nome progetto stabile (`docker compose -p hardware-history-explorer ...`) e verifica i volumi. Non eseguire `docker compose down -v` perché elimina i volumi, incluse le immagini.

## Trasferire l'archivio fra due computer (Windows e Mac)

Con Docker Desktop avviato, dalla cartella del progetto in PowerShell:

```powershell
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Transfer-HheArchive.ps1 -Mode Export -ProjectName hhe-import-test
```

Il file creato in **`backups\`** contiene l'intero database PostgreSQL e le foto
caricate. Copialo sul secondo PC. Con la stessa versione Git del progetto:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Transfer-HheArchive.ps1 -Mode Restore -ProjectName hhe-import-test -ArchivePath ".\backups\NOME-FILE.hhe-backup.tar.gz" -ConfirmRestore
```

Il ripristino **sostituisce l'archivio del secondo PC**, dopo averne creato
automaticamente un backup `prima-del-ripristino-…` in `backups\`. Conserva prezzi,
fonti, originali e stato delle importazioni. `.env` e chiavi API restano locali.
Il nome progetto deve corrispondere all'istanza con i tuoi dati: controlla
`docker compose ls -a`. [Guida completa, recupero e verifiche](docs/BACKUP_TRANSFER.md).

Sul **Mac Intel con macOS Sonoma**, installa Docker Desktop per Intel e
PowerShell 7 dal pacchetto ufficiale **`osx-x64.pkg`** indicato nella
[guida Microsoft](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-macos).
In alternativa, Homebrew usa la formula `brew install powershell`, senza
`--cask`; su Intel puo richiedere la compilazione. Sonoma non figura piu
nell'elenco attuale dei sistemi ufficialmente supportati da PowerShell:
l'esecuzione nativa su questo sistema non e stata verificata qui. Nel Terminale,
con la stessa revisione Git di Windows e il backup copiato in `backups/`:

```bash
docker compose -p hhe-import-test up --build -d --wait
pwsh -NoProfile -File ./tools/Transfer-HheArchive.ps1 -Mode Restore -ProjectName hhe-import-test -ArchivePath "./backups/NOME-FILE.hhe-backup.tar.gz" -ConfirmRestore
```

Puoi trasferire il backup fra Windows e Mac senza convertirlo. Per esportare
dal Mac usa lo stesso comando con `-Mode Export`, senza `-ArchivePath` e
senza `-ConfirmRestore`.

## Importare le introduzioni storiche

Puoi caricare descrizioni preparate esternamente da **Amministrazione →
Importazioni → Fonte dati → Descrizioni storiche (JSON)**. L'anteprima mostra
testi, fonti e abbinamenti; aggiorna solo schede esistenti, completa i testi
preimpostati e conserva quelli già curati salvo revisione esplicita dei conflitti.
[Formato del JSON e istruzioni](docs/DESCRIPTION_IMPORT.md).

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

Le entità del catalogo sono affiancate dalle tabelle fotografiche, di importazione, di ricerca e dagli alias approvati. Il campo storico `computers.image_url` resta per compatibilità con database esistenti. I media vengono restituiti tramite `/media/<nome>.webp` e non sono inclusi nelle risposte testuali dell'assistente AI.

## Altre funzionalità

- Timeline ordinata per primo lancio commerciale, con precisione storica delle date.
- Catalogo filtrabile per nome, produttore, categoria e anni.
- Schede con specifiche, configurazioni, mercati, dati di vendita, recensioni, fatti e fonti.
- Profili regionali europei identici riuniti in **Europa** nelle schede e nei
  confronti; offerte europee raggruppate senza perdere date, prezzi, valute o
  revisioni differenti. [Criteri geografici e verifica della build](docs/EUROPE_GROUPING.md).
- Commercializzazioni normalizzate su tutto il catalogo: una data generale
  univoca accompagna i prezzi compatibili anche con più mercati o più offerte.
  Prezzi e valute restano distinti; date regionali, originali e citazioni sono
  conservati. I listini successivi senza data non ricevono l'anno di lancio.
  [Regole ed esempi](docs/RELEASE_SUMMARIES.md).
- Recupero automatico dei prezzi rimasti nelle note di vecchie importazioni
  Excel, usando soltanto i campi originali completi e la fonte già associata.
  Il recupero conserva note e dati esistenti e produce un resoconto verificabile.
  [Regole del recupero prezzi](docs/HISTORICAL_PRICES.md#recupero-automatico-dei-prezzi-già-presenti-nelle-note).
- Una citazione per offerta e nessun riquadro di provenienza;
  le fonti MAME e le autocitazioni HHE sono escluse dal catalogo, dal pannello
  Fonti e dal contesto AI. RetroFlops resta visibile solo se ancora collegato
  a dati del catalogo. Dati tecnici e originali interni delle importazioni restano
  conservati. [Politica delle fonti](docs/SOURCE_POLICY.md).
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
con indice di copertura e originali. La provenienza di CPU, clock e RAM
è registrata nelle fonti, distinta dalle specifiche storiche verificate. Non contiene prezzi
né costituisce un catalogo commerciale completo: tutte le asserzioni restano da revisionare.

Il pannello **Importazioni** mostra caricamento, anteprima ed esito del lotto
corrente, con **Svuota archivio** in fondo. Le sezioni di storico, duplicati e
manutenzione del catalogo non sono più esposte nell'interfaccia; i dati già
registrati e l'audit restano conservati.
Per 1000bit puoi [arricchire automaticamente tutto il catalogo](docs/1000BIT_BULK.md)
con un solo avvio: visita dei collegamenti, abbinamenti conservativi e coda
riprendibile. Il caricamento di singole schede resta facoltativo.
L'abbinamento 1000bit usa insieme marca e modello, normalizzando paesi tra
parentesi e spazi/trattini equivalenti: `Fujitsu (Japan) · FM 11 EX` corrisponde
a `Fujitsu · FM-11 EX`. **Riprova le pagine non abbinate** permette di
recuperare gli scarti precedenti conservando gli aggiornamenti già riusciti.

Per una ricerca prezzi in Excel, scegli **Prezzi storici (Excel / CSV / JSON)**:
legge il foglio **Prezzi per modello**, mostra l'anteprima e aggiorna solo
sistemi esistenti. Conserva URL, mercato, valuta e contesto della configurazione;
prezzi e affidabilità dichiarata restano da verificare. Non usa l'anno del
foglio come data di lancio. Vedi [istruzioni e verifica del file prezzi](docs/HISTORICAL_PRICES.md).
In **Amministrazione → Foto automatiche** puoi associare il primo risultato
Wikimedia utilizzabile ai sistemi senza foto, senza conferme per singola immagine:
[istruzioni, pausa/ripresa e correzione delle immagini](docs/AUTOMATIC_PHOTOS.md).
Il comando **Ricomincia su tutti e sostituisci le copertine** crea una nuova
coda sull'intero catalogo attuale, comprese le schede già fotografate. Una
foto utilizzabile diventa la nuova copertina; la galleria e le foto prive di
un risultato sostitutivo restano conservate.

Le [categorie del catalogo](docs/CLASSIFICATION.md) vengono completate
automaticamente all’avvio e dopo le importazioni, per le famiglie riconosciute.
Le categorie specifiche già curate restano conservate; «Calcolatore» viene
rimosso quando ridondante. In **Amministrazione → Categorie** trovi conteggi,
proposte e sistemi da classificare manualmente. Non occorre svuotare il database.
La precedente [rifinitura del catalogo](docs/CATALOG_REFINEMENT.md) resta
documentata come riferimento tecnico; il relativo pannello è stato rimosso.

Per le 81 schede Olivetti dell’HTML fornito è disponibile un
[pacchetto tecnico documentato](docs/datasets/olivetti-2026-11/README.md):
513 specifiche per 62 modelli, con resoconto delle lacune. Il JSON limita
l’applicazione ai sistemi già presenti e conserva i valori discordanti
finché non vengono revisionati.

Le [etichette delle schede e dei confronti](docs/CATALOG_PRESENTATION.md) descrivono
l'hardware; la provenienza del dataset resta nelle fonti e nell'audit, senza
dover reimportare le schede esistenti.

Sul pacchetto di base, 34 schede regionali vengono accorpate conservandone le
configurazioni, con 1.105 sistemi risultanti. Lo snapshot aggiunge dati AppleDB
e documentazione MAME, comprese cinque voci di prezzo IBM RT; la copertura
storica resta parziale e gli originali delle fonti restano disponibili nell'audit.

Dal menu **Amministrazione** puoi inserire e modificare calcolatori e fonti bibliografiche, aggiungere produttori/categorie/mercati e aggiornare commercializzazioni e specifiche tecniche. Le schede conservano fotografie e altri dati storici già archiviati. Le modifiche sono applicate con il pulsante Salva; il pannello segnala quelle non salvate.

La sezione **Produttori** permette di aggiungere, modificare ed eliminare
produttori, con paese, data di fondazione, sito e conteggio delle schede
associate. Un produttore utilizzato richiede prima la riassegnazione dei
calcolatori. In **Calcolatori**, **Elimina calcolatore** rimuove la scheda dopo
conferma, aggiornando catalogo e confronti; fonti e storico delle importazioni
restano conservati. I dettagli sono nella [guida amministrativa](docs/ADMIN.md).

La gestione delle fotografie resta disponibile nella normale scheda del calcolatore, raggiungibile anche dal pannello. Non serve una migrazione aggiuntiva del database. Vedi [la guida del pannello](docs/ADMIN.md) per campi, date, fonti e API. Il pannello segue la modalità locale single-user del progetto.

### Problemi nella ricerca Wikimedia Commons

La ricerca parte da **marca e modello separati da uno spazio**: per esempio
`Apple Macintosh 128K` o `IBM PC 5150`, senza trattino separatore. I prefissi noti già presenti nel modello vengono rimossi
per evitare ripetizioni della marca. Il testo resta modificabile, sia nelle
ricerche singole sia nel modello corrente della coda automatica.
Le vecchie query automatiche ancora in attesa vengono aggiornate alla ripresa,
senza azzerare la coda, cambiare la modalità di sostituzione o modificare foto.
Le ricerche personalizzate restano invariate; i trattini propri di nomi come
System-80 e PDP-11 vengono conservati.

La ricerca Commons è gratuita e non usa la chiave OpenAI. Il backend si identifica con lo User-Agent `HardwareHistoryExplorer/1.2 (https://github.com/enzo45s/Hardware-History-Explorer)`, richiede esplicitamente il formato JSON con pagine indicizzate e attende fino a 30 secondi per ciascuna fase della richiesta HTTP.

Gli errori distinguono ora timeout (504), limitazione/sovraccarico Wikimedia (503, conservando `Retry-After` anche come data HTTP), ricerche non valide (422), HTTP 403, problemi del proxy, certificati HTTPS e risposte inattese. Un risultato senza fotografie rimane una ricerca riuscita con elenco vuoto. Non disabilitare la verifica TLS: per una CA privata usa l'override proxy descritto sopra.

Se una miniatura causa l'errore API `urlparamnormal`, il backend ritenta una
volta la stessa ricerca senza ridimensionamento, mantenendo i controlli su
immagini, attribuzione e licenza. Nel pannello automatico puoi vedere il
modello corrente, correggere il testo o saltare esplicitamente quella ricerca.
Coda ed immagini già associate restano conservate; vedi la
[guida alla ripresa e alle istanze Compose](docs/AUTOMATIC_PHOTOS.md#ripresa-di-unistanza-esistente).

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

## Ritiro degli strumenti di popolamento

Gli strumenti **Cenni storici** e **RAM e varianti** sono stati rimossi da
interfaccia, API e processi dedicati. Non sono più disponibili la ricerca
Wikipedia automatica e i comandi manuali di revisione RAM/unità, accorpamento
varianti o ricostruzione del catalogo. Le normali importazioni e le regole
condivise per schede, confronti e normalizzazione rimangono disponibili.

All’avvio una migrazione transazionale e ripetibile elimina fisicamente le
vecchie tabelle di coda, trasferendo nell’audit le attribuzioni necessarie ai
testi già acquisiti. Descrizioni, RAM, configurazioni, fonti, prezzi, fotografie
e originali delle importazioni restano conservati.
[Dettagli del ritiro e aggiornamento](docs/ADMIN_TOOLS_RETIREMENT.md).

## Arricchimento Digital / DEC

È disponibile un pacchetto documentato per 19 schede DEC esistenti e per i nuovi
VAX-11/780, VAX-11/750 e GIGI (VK100): descrizioni italiane, specifiche e rettifiche
puntuali con citazioni. Dopo l’aggiornamento dei container, applicarlo al database
locale con `docker compose -p hhe-import-test exec api python -m app.importing.dec_research --apply`.
Senza `--apply` il comando mostra solo un’anteprima; lo stesso pacchetto non si
applica due volte. [Fonti, limiti, test e istruzioni](docs/datasets/dec-2026-11/README.md).

## Nomi commerciali e schede IBM PS

Il pacchetto IBM rinomina i codici PS/2 nei nomi commerciali, conserva i codici come
alias con gli allestimenti originali e arricchisce le caratteristiche. Aggiunge
quattro famiglie PS/1 e quattro notebook PS/2 Note / PS/note se assenti.
Dopo l’aggiornamento dei container: `docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research --apply`.
Senza `--apply` mostra un’anteprima di sola lettura; l’importazione è esplicita,
transazionale e ripetibile senza duplicati.
Per completare soltanto le date dopo un import IBM già eseguito:
`docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research --dates-only --apply`.
Il supplemento conserva prezzi, mercati e date curate; distingue annuncio e
introduzione, mantenendo la precisione documentata all’anno, mese o giorno.
[Mappature, fonti e limiti](docs/datasets/ibm-ps-2026-11/README.md).

## Revisione EarthStation-I e Mistrum

Aggiornamento documentato delle due schede esistenti: 44 specifiche, descrizioni
italiane e fotografie attribuite. Corregge CPU e RAM dell’EarthStation-I e
documenta la RAM fisica del Mistrum, separandola dalla memoria video.
Dopo l’aggiornamento dei container:
`docker compose -p hhe-import-test exec api python -m app.importing.earthstation_mistrum --apply`.
Senza `--apply` mostra un’anteprima; non crea nuovi sistemi né modifica le offerte.
[Fonti, fotografie, condizioni d’uso e verifica](docs/datasets/earthstation-mistrum-2026-11/README.md).

## General Processor

Profilo aziendale fiorentino con logo, storia e fonti, più Child 8, Child Z,
Modello T (originale e MKIII nella stessa scheda), GPS4 e GPS5: 79 specifiche,
fotografie attribuite e cinque prezzi documentati in lire italiane.
Dopo aver aggiornato i container:
`docker compose -p hhe-import-test exec api python -m app.importing.general_processor --apply`.
Senza `--apply`: anteprima. [Fonti, limiti e verifica](docs/datasets/general-processor-2026-11/README.md).

## NewBrain, Micro-Professor I e Robotron

Pacchetto documentato per NewBrain, Micro-Professor I e tre sistemi Robotron:
KC 85/1 (comprende Z9001), KC 87 e A 5105. Cinque schede, 87 specifiche,
fotografie Commons e profili di Robotron e Grundy Business Systems.
Dopo aver aggiornato i container:
`docker compose -p hhe-import-test exec api python -m app.importing.microcomputer_research --apply`.
Senza `--apply`: anteprima. [Fonti, prezzi, limiti e istruzioni](docs/datasets/microcomputers-2026-11/README.md).

## Revisione Sun: anni e fotografie

Il supplemento recupera gli anni dichiarati nei contesti di prezzo delle schede
Sun, distingue riferimenti e lanci documentati, corregge vecchi anni non verificati
e aggiunge immagini selezionate anche da fonti esterne a Commons. Prezzi, testi,
specifiche e copertine manuali restano conservati; le lacune fotografiche sono
esplicitate. Dopo aggiornamento dei container:
`docker compose -p hhe-import-test exec api python -m app.importing.sun_research --apply`.
Senza `--apply`: anteprima. [Fonti, limiti e verifica](docs/datasets/sun-2026-11/README.md).

## Anteprime dei sistemi

Il catalogo e l’elenco dei sistemi nella pagina di un produttore usano lo stesso
riquadro uniforme: immagine ingrandita, categoria, titolo, produttore/data e
quattro righe di descrizione. Titoli lunghi e testi estesi vengono troncati; l’altezza rimane
uniforme anche quando mancano fotografia o descrizione. **Dettagli** apre la
scheda con il testo completo. Il confronto e il collegamento al produttore
rimangono disponibili nel catalogo.

La griglia si adatta alla larghezza dello schermo e usa gli stessi caratteri e
dimensioni nei temi chiaro e scuro. Le anteprime condivise sono implementate in
`frontend/src/ComputerCard.jsx` e `frontend/src/computer-card.css`; non richiedono
migrazioni o importazioni. Il test browser dei produttori verifica entrambe le
viste, altezze e pulsanti allineati, testo corto/lungo/mancante, immagini,
apertura della descrizione integrale e viewport 320/390/768/1440 px nei due temi.

## Produttori: descrizioni e loghi aggiuntivi

Il supplemento di ricerca estende le fonti fuori da Commons e arricchisce
30 profili esistenti con 14 descrizioni italiane e 18 loghi, conservando i
contenuti già curati. Dopo aggiornamento del branch e ricostruzione dell’API:
`docker compose -p hhe-import-test exec api python -m app.manufacturer_enrichment --package app/importing/data/manufacturers-deep-2026-11-v1.json`.
Il comando applica il pacchetto; ripeterlo non duplica fonti o sostituisce
valori esistenti. [Fonti, diritti, lacune e istruzioni per il Mac](docs/datasets/manufacturers-deep-2026-11/README.md).

## Pagina di benvenuto: museo digitale

HHE si apre su **Benvenuto**, con una macchina in vetrina, percorsi verso catalogo,
timeline e produttori, sistemi selezionati e conteggi letti dal database locale.
La barra laterale continua a raggiungere tutte le sezioni; **Benvenuto** riapre
la home. I collegamenti aprono le schede reali e i periodi della timeline.

L’aggiornamento richiede soltanto la ricostruzione di API e frontend, senza import
o migrazioni del database:

```bash
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

[Selezione dei sistemi, navigazione, fotografie e verifiche](docs/HOME_PAGE.md).

## Revisione NEC, NeXT, Kaypro, SGI, Daewoo e Fenner

Il supplemento documentato del 25 novembre comprende 101 schede da arricchire,
H/H Tiger incluso, e aggiunge soltanto **Sol-20** e **Video Technology Laser 500**.
Usa fonti per modello, immagini con attribuzione e rettifiche legacy puntuali;
conserva descrizioni curate, copertine, prezzi e configurazioni sostanziali.

Dopo il pull e la ricostruzione dell’API, l’anteprima è:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.catalog_research
```

Per applicare, aggiungi `--apply` allo stesso comando. L’avvio dei container
non importa il pacchetto automaticamente.
[Fonti, risultati verificati, lacune e istruzioni](docs/datasets/catalog-research-2026-11/README.md).
