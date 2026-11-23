# Produttori: esplorazione e profili aziendali

La voce **Produttori** nella navigazione principale presenta tutte le aziende
censite, comprese quelle ancora senza descrizione o senza sistemi associati.
Le schede mostrano logo, nome, paese e numero di sistemi presenti in HHE;
ricerca per nome/denominazione storica, filtro per paese e ordinamento per
nome o numero di sistemi permettono di consultare l'elenco.

**Esplora** apre il profilo con descrizione italiana, dati aziendali, fonti,
attribuzione del logo e computer ordinati per prima commercializzazione.
Il periodo indicato accanto al conteggio riguarda i computer nell'archivio,
non la durata dell'azienda. Il nome del produttore è cliccabile anche nella
timeline, nel catalogo e nelle schede dei computer. Aprendo un sistema dal
profilo, il pulsante per tornare all'esplorazione riapre l'azienda.

## Completare o modificare una scheda

In **Amministrazione → Produttori**, scegli un'azienda oppure premi
**Nuovo produttore**. Sono disponibili:

- Nome, paese, denominazione storica, sede, fondatori e testo storico italiano.
- Fondazione e cessazione con precisione `AAAA`, `AAAA-MM` o `AAAA-MM-GG`.
- Sito web e URL HTTP(S) del logo, autore, condizioni d'uso e pagina della fonte.
- Fonti aziendali, ricercabili fra quelle presenti nella sezione **Fonti**.
- Autore/attribuzione, fonte e licenza del testo, quando necessari. Se riscrivi
  una descrizione, controlla anche questi campi; le citazioni della scheda
  restano associate finché non le rimuovi esplicitamente.

**Salva produttore** aggiorna il profilo pubblico e conserva l'identità e le
associazioni dei computer. Le informazioni non disponibili possono rimanere
vuote. Un produttore può esistere senza una descrizione: la migrazione non
inventa testi, date o loghi. L'associazione di una citazione non verifica
automaticamente i fatti. Un logo viene mostrato nei colori originali su un
riquadro bianco, in entrambi i temi; se manca o non è raggiungibile, viene
usato un segnaposto riconoscibile.

I loghi sono attualmente collegati tramite URL: non vengono scaricati nel
volume delle fotografie. Backup e trasferimenti conservano URL, attribuzioni
e fonti, mentre la disponibilità dell'immagine dipende dal sito remoto.

## Aggiornamento del progetto

Sul progetto Compose già utilizzato, dopo un backup recente:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait --wait-timeout 900
```

L'API aggiunge automaticamente le colonne nullable e la tabella
`manufacturer_sources`. Non occorre reimportare il database. Le date di
fondazione precedenti conservano la loro rappresentazione completa; le nuove
date parziali hanno una precisione esplicita. Nessun record del catalogo viene
ricreato o riassegnato dalla migrazione. Per uso offline, la migrazione è anche
eseguibile con `python -m migrations.manufacturer_profiles` nel contenitore API.

Al primo avvio viene applicata anche la [raccolta documentata dei
produttori](MANUFACTURER_RESEARCH.md), senza richieste di rete o chiamate AI.
Si riempiono esclusivamente i campi vuoti dei produttori riconosciuti per nome
esatto (normalizzati spazi e maiuscole); non si creano o uniscono produttori.
Ogni campo aggiunto ha una citazione e uno snapshot prima/dopo. Le nuove
associazioni bibliografiche sono `pending`, non verificate automaticamente.
Il pacchetto è applicato una volta per checksum: anche le cancellazioni manuali
successive sopravvivono ai normali riavvii con lo stesso pacchetto.

In **Amministrazione → Produttori**, **Completa profili documentati** consente
di riapplicarlo esplicitamente ai campi vuoti; **Scarica resoconto produttori**
esporta copertura, lacune, ambito delle identità e fonti consultate. I campi
già compilati restano protetti, anche quando discordano dalla raccolta. Una
nuova data incompatibile con una data esistente viene saltata e segnalata.
La raccolta non può attribuire i crediti del proprio testo o logo a un testo
o logo diverso già inserito a mano.

Per disabilitare l'applicazione iniziale, imposta nel `.env`
`HHE_MANUFACTURER_ENRICHMENT_AUTO=0` e ricrea il servizio API. L'azione manuale
resta disponibile. In alternativa, dal contenitore API:

```bash
docker compose -p hhe-import-test exec api python -m app.manufacturer_enrichment
```

Le API locali sono `GET /api/admin/manufacturers/enrichment/report` e
`POST /api/admin/manufacturers/enrichment/apply`. Come gli altri strumenti di
amministrazione, sono destinate all'istanza locale; Compose pubblica API e web
su loopback. Il pacchetto non accede al Mac da remoto.

Le API CRUD `/api/manufacturers` e `/api/manufacturers/{id}` restano compatibili
con i vecchi campi. La PUT conserva i campi e le fonti omessi; un valore `null`
o una lista `source_ids` vuota ne richiedono la cancellazione esplicita.
`GET /api/manufacturers/{id}/profile` aggiunge il periodo dei sistemi censiti.
I nuovi collegamenti alle fonti sono conservati anche nelle riconciliazioni
e negli snapshot di eliminazione. Un produttore con computer associati non
può essere eliminato.

## Verifiche

Sulla copia isolata del dump: **184 produttori e 1.133 sistemi**, tutti i profili
API consultabili. La raccolta ha aggiornato **148 profili**, aggiungendo
**148 descrizioni italiane, 84 loghi e 305 fonti**. Le informazioni già presenti
e tutte le fonti preesistenti sono rimaste identiche. Hash delle tabelle dei
sistemi, configurazioni, specifiche, commercializzazioni, foto e relativi
collegamenti invariati; nessun accesso al database sul Mac. Il secondo avvio
non ha duplicato le fonti. Le lacune rimaste sono documentate nel resoconto.

Il test browser `npm run test:browser:manufacturers` crea esclusivamente dati
sintetici su un'istanza locale di prova e li elimina al termine. Controlla
modifica amministrativa, date parziali, fonti, attribuzioni, logo, ricerca, filtri,
collegamenti azienda/sistemi, temi chiaro/scuro e viewport 320/390 px.

Verifica del 23 novembre 2026: **956 test SQLite superati, due saltati;
19 test mirati PostgreSQL e 45 test frontend superati**. La suite include
protezione dei campi manuali, atomicità, citazioni, cronologie discordanti,
nomi omonimi, applicazioni ripetute e conservazione delle cancellazioni manuali.
Build React, build e health Docker Compose superati. Chromium ha verificato
completamento dei profili, download e lettura del resoconto JSON, attribuzioni,
ricerca e navigazione, temi e viewport 320/390 px senza errori JavaScript.
Superata anche la regressione del pannello amministrativo su produttori e
cancellazione dei computer. Controllo dipendenze Python riuscito.
Rimangono l'avviso Vite sul bundle oltre 500 kB e la deprecazione
Starlette/httpx preesistenti.
