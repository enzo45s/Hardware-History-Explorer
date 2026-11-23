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

Le API CRUD `/api/manufacturers` e `/api/manufacturers/{id}` restano compatibili
con i vecchi campi. La PUT conserva i campi e le fonti omessi; un valore `null`
o una lista `source_ids` vuota ne richiedono la cancellazione esplicita.
`GET /api/manufacturers/{id}/profile` aggiunge il periodo dei sistemi censiti.
I nuovi collegamenti alle fonti sono conservati anche nelle riconciliazioni
e negli snapshot di eliminazione. Un produttore con computer associati non
può essere eliminato.

## Verifiche

Sulla copia isolata del dump: **184 produttori e 1.133 sistemi**, profili API
tutti consultabili; colonne aziendali preesistenti e hash delle tabelle dei
sistemi, specifiche, commercializzazioni, fonti e foto invariati. Nessun profilo
editoriale aggiunto automaticamente e nessun accesso al database sul Mac.

Il test browser `npm run test:browser:manufacturers` crea esclusivamente dati
sintetici su un'istanza locale di prova e li elimina al termine. Controlla
modifica amministrativa, date parziali, fonti, logo, ricerca, filtri,
collegamenti azienda/sistemi, temi chiaro/scuro e viewport 320/390 px.

Verifica del 23 novembre 2026: **947 test SQLite superati, due saltati;
106 test mirati PostgreSQL e 45 test frontend superati**. Build React,
build/health Docker Compose, nuovo flusso Chromium e regressione del pannello
amministrativo riusciti. La prova include il segnaposto di un logo non
raggiungibile e la conservazione dei profili/fonti nelle riconciliazioni.
Rimangono l'avviso Vite sul bundle oltre 500 kB e la deprecazione
Starlette/httpx preesistenti. Il primo tentativo di regressione ha incontrato
un esaurimento del disco del cloud: dopo la pulizia della cache di build,
la suite completa è stata rieseguita con l'esito sopra riportato.
