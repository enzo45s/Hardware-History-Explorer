# Ritiro degli strumenti di popolamento

Sono rimossi i due pannelli amministrativi della ricerca automatica dei cenni
storici e della revisione RAM/varianti, insieme a componenti React, endpoint,
ricerca Wikipedia, gestione delle code, modelli SQLAlchemy, comandi dedicati,
pacchetti di recupero e prove/fixture che esercitavano esclusivamente questi
strumenti. La CI e gli script npm non avviano più i tre flussi browser ritirati.

La rimozione comprende controllo/recupero RAM, analisi e accorpamento manuale
delle varianti, revisione delle unità, analisi/applicazione manuale della pulizia
fisica e controllo/ricostruzione manuale dei dati consolidati. Le rispettive
API sotto `/api/admin/history` e `/api/admin/catalog-quality` non sono registrate.

## Database e attribuzioni

La migrazione `migrations.retire_admin_tools`, eseguita all'avvio dell'API:

1. Conserva nell'audit generico le attribuzioni dei testi acquisiti, con titolo,
   URL, licenza, metodo e impronta del testo.
2. Contrassegna i vecchi lotti di ricerca come appartenenti a uno strumento
   ritirato. I file originali rimangono leggibili; un retry restituisce `410`.
3. Elimina fisicamente prima `history_research_items`, poi
   `history_research_jobs`, senza `CASCADE` sulle altre tabelle.

L'operazione è transazionale, ripetibile e usa il lock condiviso del catalogo
su PostgreSQL. Se un testo acquisito manca dei crediti necessari, viene
annullata prima di eliminare le tabelle. Le vecchie code non vengono ricreate.
Le attribuzioni vengono mostrate solo per il testo corrispondente; una
successiva riscrittura manuale non eredita i crediti del testo precedente.

Computer, configurazioni, RAM, descrizioni, fonti, prezzi, fotografie, originali
ETL e audit delle revisioni già applicate restano conservati. I risultati
negativi e gli stati operativi delle vecchie code sono eliminati insieme alle
tabelle dismesse.

## Funzioni condivise conservate

La rimozione dei pannelli non disattiva la normalizzazione del catalogo:
schede, confronti, importatori e assistente continuano a usare le stesse regole
per nomi, misure, configurazioni e commercializzazioni. Le identità condivise
sono ora in `app.catalog_identity`, senza codice di ricerca o rete. La
protezione dalle reimportazioni di capacità RAM già ritirate rimane nel motore
ETL e legge esclusivamente gli audit esistenti; non applica nuove revisioni.

Rimangono disponibili gli importatori ordinari, compreso il caricamento manuale
di descrizioni JSON, e la gestione di calcolatori, produttori, fonti, categorie,
foto e backup.

## Aggiornamento

Dalla cartella del progetto, con un backup recente:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait --wait-timeout 900
```

Non occorre reimportare il database. La migrazione agisce sull'istanza locale
solo quando avvii questa versione. La verifica cloud usa una copia isolata;
non accede al computer dell'utente.

## Verifiche del 23 novembre 2026

- Copia isolata del database: hash invariati su produttori, computer,
  configurazioni, specifiche, commercializzazioni, fonti, immagini, relazioni,
  fatti, vendite, recensioni e asserzioni ETL. Conservati 1.133 sistemi e
  tutti i 3.046 originali delle importazioni.
- Rimosse 2 code e 2.167 voci operative; conservate 105 attribuzioni e
  controllate le 100 ancora corrispondenti al testo attuale. Secondo avvio
  senza nuove modifiche né ricreazione delle tabelle eliminate.
- Suite SQLite: 820 test superati, due saltati. Controlli aggiuntivi della
  migrazione: 14 superati, compreso il rollback dopo un errore nel secondo
  `DROP TABLE`. PostgreSQL: gruppi mirati da 109 test di integrazione e 30
  verifiche di migrazione/importazione RAM, tutti superati.
- 45 test frontend, compilazione React, build/health Docker Compose e otto
  test degli archivi di backup superati. Browser Chromium: assenza dei due
  comandi rimossi, CRUD amministrativo e importazione manuale delle descrizioni
  JSON, revisione dei conflitti e reimportazione senza duplicati superati.

Gli script browser dedicati ai pannelli rimossi non sono più eseguiti; le
regressioni coprono invece le funzionalità che devono restare disponibili.
