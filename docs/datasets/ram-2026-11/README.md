# RAM mancante — ricerca del 21 novembre 2026

L’esame della copia del dump fornito dall’operatore ha rilevato **408 sistemi
su 1.133 senza una quantità RAM riconoscibile**. La ricerca ha prodotto
**147 asserzioni per 147 sistemi**. Sulla copia di prova i sistemi con RAM
documentata passano da 725 a 872; ne restano **261** senza una quantità
utilizzabile. La ricerca non completa quindi tutto il catalogo.

## File e importazione sul Mac

- `ram-mancante.json`: pacchetto da caricare nell’importatore CSV/JSON.
- `fonti.json`: citazioni usate, modelli supportati, revisioni e hash delle
  evidenze consultate. Per il manuale Kaypro l’hash riguarda il testo OCR.
- `resoconto.json`: tutti i 261 casi residui, formulazioni alternative non
  importate automaticamente e limiti della ricerca.

Conserva prima un backup aggiornato, seguendo [Backup e trasferimento](../../BACKUP_TRANSFER.md).
Nel Terminale, dalla cartella del progetto:

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Usa il nome del progetto Compose con i tuoi dati se diverso da `hhe-import-test`.

1. Apri **Amministrazione → Importazioni**.
2. Seleziona **CSV / JSON autorizzato** e carica il file presente nella tua
   cartella del repository: `docs/datasets/ram-2026-11/ram-mancante.json`.
3. Conferma il diritto di utilizzare il dataset e prepara l’anteprima.
4. Verifica le diciture **Solo aggiornamenti a calcolatori esistenti** e
   **Solo RAM mancante**.
5. Controlla gli abbinamenti e applica le righe pronte.

I vincoli nel file sono `_metadata.import_mode=existing_only` e
`_metadata.enrichment_mode=missing_ram_only`. Il backend li applica anche
dal caricamento generico e nei retry. Una macchina cancellata non viene
ricreata. Un sistema che ha già una quantità RAM viene saltato: il controllo
avviene nuovamente all’applicazione, anche se la RAM è stata aggiunta dopo
l’anteprima. La ripetizione del pacchetto non aggiunge altre configurazioni,
specifiche o fonti.

Sul dump esaminato il primo passaggio restituisce **Aggiornata: 147**;
il secondo restituisce **Esclusa: 147** perché le quantità sono già presenti.
In questo caso «Esclusa» indica la protezione dei dati esistenti.

Non vengono modificati descrizioni, commercializzazioni, prezzi, categorie,
fotografie o specifiche già presenti. Per questo tipo di pacchetto non viene
eseguita la riclassificazione automatica delle categorie. Gli import normali
mantengono il proprio comportamento. Le nuove asserzioni restano **pending**:
la consultazione della fonte non costituisce una verifica storica indipendente.

## Fonti effettivamente usate

I seguenti conteggi indicano i modelli supportati dalla fonte scelta, non il
numero di richieste HTTP né il numero di URL distinti:

- **54 sistemi**: schede 1000bit già conservate nel dump dalle importazioni
  autorizzate dall’operatore. Sono stati riesaminati i 2.875 originali HTML
  disponibili, senza nuovo crawling. Le evidenze conservano hash, URL e campo
  della scheda. I nomi estesi dei produttori sono stati confrontati con quelli
  del catalogo; il pacchetto usa i nomi effettivi delle schede HHE, senza
  riscrivere globalmente produttori o regole di abbinamento.
- **83 sistemi**: passaggi specifici delle voci Wikipedia, recuperati tramite
  API ufficiali con revisione fissata, attribuzione e licenza CC BY-SA 4.0.
  Sono incluse voci di famiglia solo quando il passaggio identifica il modello
  o un insieme di modelli che comprende esplicitamente quello censito.
- **9 sistemi**: *Kaypro Technical Manual*, parte 1484-D, dicembre 1984,
  capitolo 3, consultato tramite il testo OCR pubblico di Internet Archive.
  Il capitolo 4 permette anche di identificare i modelli 2/83 e 4/83. Le
  capacità dei coprocessori opzionali non sono confuse con la RAM CP/M.
- **1 sistema**: tabella *NeXT 1991 Specifications* conservata nell’archivio
  di Simson Garfinkel, per i 12 MB della NeXTstation Color.

Non sono stati usati nuovi dati MAME né chiamate OpenAI a pagamento. I testi
integrali delle schede e dei manuali non vengono ripubblicati nel repository;
il pacchetto contiene fatti selezionati e brevi evidenze con riferimenti.
Il dump originale e i relativi identificativi interni non sono pubblicati.

## Distinzioni mantenute

- La RAM principale è separata da ROM, VRAM, cache, dischi e SRAM di servizio.
  Ad esempio Amiga 4000 conserva la distinzione fra Chip RAM e memoria
  aggiuntiva; non viene inventata una dotazione standard sommando le opzioni.
- Dotazioni, intervalli, capacità massime e memoria disponibile al software
  restano esplicitamente etichettati. Per gli SGI Indigo R4000/R4400 viene
  documentato il massimo, senza inventare la RAM installata di fabbrica.
- Il PDP-1 mantiene **4096 parole da 18 bit**, non 4096 byte. I registri di
  Programma 101/P102/P203 e le posizioni alfanumeriche dell’Elea 9003, già
  documentati nella sezione Memoria, non diventano falsa RAM convenzionale.
- `Kb`, `KB` e `KiB` non sono scambiati. Le notazioni storiche ambigue di
  1000bit restano come riportate; la presenza di una quantità non implica
  che sia stata verificata la scala binaria. Le quantità conservano la
  notazione documentata dalla fonte.
- Non si estende il dato di un modello a suffissi regionali, modelli vicini
  o revisioni solo perché il nome è simile. Le formulazioni alternative sono
  elencate nel resoconto senza generare righe ripetute nella scheda.

## Limiti e casi residui

Per alcuni MSX regionali e sistemi meno documentati non è stato trovato un
passaggio sufficientemente preciso nelle fonti consultate. MSX Resource Center
ha l’API disabilitata e condizioni che non autorizzano il riutilizzo generalizzato:
non è stata eseguita una raccolta massiva del sito. Il permesso dell’operatore
per 1000bit non è stato esteso ad altri archivi. HP Computer Museum e Bitsavers
hanno restituito HTTP 403; il manuale Kaypro è stato reperito nel distinto
archivio pubblico Internet Archive, senza aggirare i blocchi dei siti.

DECmate II/III restano da verificare su documentazione primaria per le
formulazioni discordanti fra parole a 12 bit e byte. Altre quantità
documentate possono riguardare espansioni o revisioni successive: sono
conservati l’ambito e la fonte selezionata. Il resoconto non dichiara che
nessuna fonte esista per i 261 casi residui, ma che non è stata acquisita
un’evidenza utilizzabile in questa ricerca.

## Verifiche sulla copia del dump

L’importazione ha aggiornato 147 sistemi e conservato tutti i 1.133 ID. I
confronti delle righe confermano la conservazione integrale di descrizioni,
prezzi, date, mercati, categorie, produttori, associazioni fotografiche, note, ricerche e
asserzioni precedenti. Tutte le 9.410 specifiche preesistenti e le relative
attribuzioni sono invariate; vengono aggiunte 147 specifiche RAM con le loro
fonti. Nessuna ricerca esterna o coda fotografica è stata avviata sul dump.
La ripetizione ha saltato tutte le 147 righe, senza nuove specifiche o fonti.

Questa prova usa un database isolato. Per aggiornare il Mac occorre importare
il file sul computer che contiene l’archivio effettivo. Eventuali cambiamenti
successivi all’esportazione del dump possono ridurre il numero di righe
applicate: il controllo «Solo RAM mancante» protegge quei dati.

## Test del codice

- Backend SQLite: **840 test superati**, uno riservato a PostgreSQL saltato.
- PostgreSQL 16: **46 test superati** per RAM, importazioni e migrazioni,
  incluso il test esclusivo PostgreSQL.
- Frontend: **31 test superati** e compilazione React riuscita; resta
  l’avviso Vite sul bundle JavaScript principale superiore a 500 kB.
- Docker Compose: compilazione, avvio e health check riusciti.
- Chromium, catalogo sintetico isolato: caricamento del file reale da 147
  righe, vincoli visibili nell’anteprima, applicazione esplicita, ripetizione
  con 147 righe escluse, layout 320/390 px e nessun errore JavaScript.
