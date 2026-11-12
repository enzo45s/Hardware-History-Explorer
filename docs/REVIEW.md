# Revisione tecnica e correzioni

Verifica dell'11 novembre 2026, a partire da `6f96f2b79bc2a6dd59e419e2a1037ccbd6b5ded2`. Le correzioni conservano timeline, catalogo, dettagli, confronto, statistiche, assistente opzionale e tutte le modalità di gestione delle fotografie.

## Architettura

React 18/Vite comunica con FastAPI tramite i proxy `/api` e `/media` di Nginx in Docker o Vite in sviluppo. SQLAlchemy usa PostgreSQL 16 in Compose e SQLite localmente. Lo schema contiene 19 tabelle e 10 sistemi dimostrativi. Database e fotografie hanno volumi distinti. Pillow converte gli upload in WebP; le immagini esterne restano URL con metadati. La ricerca Commons contatta un host fisso. OpenAI è opzionale: riceve dati limitati, senza accesso arbitrario a SQL.

## Difetti corretti

| Area | Problema riprodotto | Correzione |
| --- | --- | --- |
| API | Anni negativi o oltre 9999 causavano 500 | Validazione 422 e controllo dell'ordine degli estremi |
| Catalogo | Estremi temporali soddisfatti da commercializzazioni diverse | Filtro sulla prima commercializzazione, coerente con la timeline |
| Catalogo | Tutti i dati caricati prima della paginazione | Conteggio, ordinamento e limit/offset SQL; relazioni limitate a quelle necessarie |
| Confronto | Ordine non rispettato e ID mancanti ignorati | Ordine della selezione e 404 per sistemi inesistenti |
| Fonti | Input valido per Pydantic ma troppo lungo per PostgreSQL | Limiti allineati alle colonne e validazione URL prima dei limiti |
| SQLite | Chiavi esterne disabilitate | `PRAGMA foreign_keys=ON` per ogni connessione |
| Recensioni | CHECK accettava un punteggio senza scala | Vincolo corretto e migrazione esplicita per database esistenti |
| React | Vecchie risposte sovrascrivevano la ricerca corrente | Annullamento e controllo delle risposte obsolete, anche nel confronto |
| React | Catalogo limitato ai primi 100 sistemi | Lettura di tutte le pagine con filtri e cancellazione |
| Fotografie | WebP servite come `application/octet-stream` nel container | MIME esplicito, indipendente dal database MIME del sistema |
| Fotografie | URL controllati solo tramite prefisso; conversione sull'event loop | URL HTTPS validi senza credenziali; conversione nel thread pool |
| Fotografie | Possibile copertina obsoleta con modifiche concorrenti PostgreSQL | Lock del computer prima delle operazioni immagini |
| Commons | Errori in risposte HTTP 200 trattati come ricerca vuota | Risposta upstream controllata, errori 502 e filtraggio media/URL invalidi |
| Docker | Porte su tutte le interfacce per un'app senza autenticazione | Binding localhost e readiness API prima dell'avvio web |
| Docker | Dipendenze/output host nel contesto | `.dockerignore` e `npm ci` |
| Dipendenze | Versioni non riproducibili; advisory Pillow 12.3.0 | Lock npm/Python e Pillow 13.0.0 |
| Test | Database persistente e ordine di import significativo | Database/upload temporanei e PostgreSQL dedicato |

La migrazione `python -m migrations.review_score` non viene eseguita automaticamente sui dati dell'utente. Il README descrive backup e arresto necessari. È ripetibile, conserva righe/riferimenti/indici e rifiuta dati invalidi o schemi inattesi invece di correggerli o cancellarli implicitamente.

## Sicurezza e dipendenze

`npm audit` non segnala vulnerabilità note. `pip-audit` sul lock iniziale ha segnalato 40 advisory associati a Pillow 12.3.0; non tutti i percorsi vulnerabili erano necessariamente raggiungibili dall'applicazione. Dopo l'aggiornamento a Pillow 13.0.0, l'audit dei 33 pacchetti del lock non segnala vulnerabilità note. `pip check` non rileva dipendenze incompatibili o mancanti.

La verifica TLS rimane attiva. I Dockerfile accettano una CA opzionale tramite secret BuildKit; `docker-compose.proxy.yml` fornisce anche un bundle affidabile al runtime API, senza copiarlo nell'immagine. Le immagini base usano ancora tag aggiornabili; non è stata eseguita una scansione completa delle vulnerabilità del loro sistema operativo.

Gli upload sono verificati, limitati in dimensione, convertiti in WebP statico e privati dei metadati incorporati. Nomi file casuali impediscono di scegliere percorsi arbitrari. SVG e altri formati non supportati sono scartati; i metadati HTML Commons diventano testo. L'app resta single-user: autenticazione, autorizzazione, rate limiting e backup automatici restano requisiti per un'eventuale distribuzione pubblica.

## Verifiche eseguite

| Controllo | Risultato |
| --- | --- |
| Dipendenze Python e `pip check` | Installazione riuscita, dipendenze coerenti |
| Backend SQLite, Python 3.12 | 30 superati, 1 saltato: migrazione specifica PostgreSQL |
| Backend nel container su PostgreSQL dedicato | 31 superati, nessun test saltato |
| Frontend `npm test` | 5 superati: risposte obsolete, cancellazione, oltre 100 record, multipart e messaggi di validazione |
| `npm ci` e `npm run build` | Riusciti; avviso sul bundle JS di circa 574 kB non compresso |
| Docker Compose standard e override CA | Configurazioni valide; build e avvio completi con TLS verificato |
| HTTP attraverso Nginx/PostgreSQL | Health, catalogo, 422 per input invalidi, confronto, upload, MIME WebP, cancellazione e successivo 404 |
| Chromium/Playwright | Timeline, ricerca, dettagli, upload/anteprima/cancellazione, grafici, fallback AI, risposte fuori ordine e confronto di due sistemi |
| Commons simulato | Ricerca, metadati/autore/licenza, import, filtraggio e gestione errore upstream |
| Migrazione | Schema SQLite storico con evidenze/indice, rollback su dati invalidi e aggiornamento ripetibile PostgreSQL |

La suite conserva un avviso di deprecazione Starlette/httpx, senza nasconderlo. La build conserva l'avviso sulle dimensioni del bundle, senza eliminare funzionalità. La CI aggiunta ripete test SQLite/PostgreSQL, test/build frontend e build Docker; l'esecuzione remota GitHub non è verificata in questa sessione.

## Limiti della verifica

- L'accesso live a `commons.wikimedia.org` è stato bloccato dal proxy cloud con HTTP 403. I test simulati non dimostrano il funzionamento della ricerca online nella policy attuale.
- OpenAI non ha una chiave configurata: verificato il fallback, non una risposta del modello. Nessuna chiave è stata richiesta in chat.
- L'API GitHub (`api.github.com`) è bloccata con HTTP 403. Il trasporto Git HTTPS è distinto e consente il push del branch; l'apertura remota della PR richiede accesso API e autenticazione valida per quell'operazione.
- Non sono state apportate modifiche alla bozza/configurazione cloud né eseguite pubblicazioni. I dati di sviluppo preesistenti sono conservati; i test ricreano solo database temporanei o PostgreSQL dedicato con suffisso `_test`.
- Analytics continua a leggere il campione in memoria e il frontend conserva il catalogo per timeline e confronto. Archivi molto grandi richiederanno aggregazioni SQL, paginazione dell'interfaccia e/o virtualizzazione.
- La migrazione mirata non sostituisce un sistema generale di migrazioni come Alembic. Non sono state eliminate funzionalità per aggirare test o problemi.
