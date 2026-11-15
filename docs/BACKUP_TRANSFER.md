# Backup completo e trasferimento fra computer

`tools/Transfer-HheArchive.ps1` crea e ripristina un singolo archivio
**`.hhe-backup.tar.gz`** per PostgreSQL + fotografie. Funziona con Windows
PowerShell 5.1 incluso in Windows e PowerShell 7; occorre Docker Desktop con
container Linux. Non richiede Python, PostgreSQL o altri programmi sul PC.
Non aggiunge endpoint amministrativi esposti via HTTP.

## Cosa viene trasferito

- Tutte le tabelle PostgreSQL, sequenze e collegamenti: sistemi, produttori,
  categorie, configurazioni, specifiche, prezzi, mercati, fonti e verifiche.
- Originali delle importazioni, abbinamenti, decisioni sui conflitti,
  riconciliazioni, svuotamenti e stato delle ricerche Commons/1000bit.
- Tutti i file del volume `image_uploads`, compresi quelli conservati dopo
  cancellazioni di schede. Le fotografie Commons e gli altri URL esterni
  rimangono collegamenti con attribuzioni/licenze: il backup non scarica file remoti.

Non vengono trasferiti codice, immagini Docker, `.env`, chiavi OpenAI,
preferenze tema del browser o modifiche non salvate nelle pagine. Il formato
non e l'export CSV/JSON del catalogo e non passa dall'ETL: conserva ID e audit.
L'archivio non e cifrato; custodiscilo come il database originale. Le cartelle
`backups/` e i file `*.hhe-backup.tar.gz` sono esclusi da Git.

## Primo PC: esportazione

Apri PowerShell nella cartella del repository e aggiorna il branch di lavoro:

```powershell
git switch feat/historical-data-import
git pull --ff-only
docker compose ls -a
docker compose -p hhe-import-test ps -a
```

Usa **il nome progetto che contiene il tuo archivio**. Nei comandi qui sotto e
`hhe-import-test`; non confonderlo con `hardware-history-explorer` se hai
entrambe le istanze. I servizi devono essere gia creati e il database avviato.
Se occorre: `docker compose -p hhe-import-test up --build -d --wait`.
Metti in pausa le ricerche automatiche e chiudi le schede di amministrazione
che potrebbero continuare a inviare richieste.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Transfer-HheArchive.ps1 -Mode Export -ProjectName hhe-import-test
```

Il comando stampa il percorso del file, per esempio:
`backups\hhe-hhe-import-test-20261115-230000.hhe-backup.tar.gz`.
Puoi scegliere nome e destinazione (la cartella deve esistere):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Transfer-HheArchive.ps1 -Mode Export -ProjectName hhe-import-test -ArchivePath "E:\Trasferimenti\archivio.hhe-backup.tar.gz"
```

Il nome di un backup esistente non viene sovrascritto. Durante la copia API
e frontend vengono fermati brevemente; il database resta acceso. Alla fine,
anche in caso di normale errore, ripartono solo i servizi che erano gia accesi.
Il dump binario viene scritto nel container e copiato come file: evita la
corruzione delle redirezioni binarie di Windows PowerShell 5.1.
`-ExecutionPolicy Bypass` vale per questo processo, senza cambiare la policy
di sistema. In PowerShell 7 puoi invocare direttamente lo script con `&`.

## Secondo PC: ripristino

1. Copia il file tramite USB, rete locale o altro canale di tua scelta.
2. Installa Docker Desktop e porta il repository **alla stessa revisione Git**
   del primo PC: `git rev-parse HEAD` deve coincidere. Su un nuovo clone:

   ```powershell
   git fetch origin
   git switch --track origin/feat/historical-data-import
   ```

   Se il branch esiste gia: `git switch feat/historical-data-import` e
   `git pull --ff-only`. Configura separatamente `.env` se usi l'assistente AI.
3. Dalla cartella del repository:

   ```powershell
   docker compose -p hhe-import-test up --build -d --wait
   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Transfer-HheArchive.ps1 -Mode Restore -ProjectName hhe-import-test -ArchivePath "E:\Trasferimenti\archivio.hhe-backup.tar.gz" -ConfirmRestore
   ```

4. Attendi la conclusione e apri **http://localhost:8080**; se era gia aperto,
   ricarica completamente la pagina. Controlla una scheda con prezzo/fonti e
   una foto caricata. Le code vengono conservate con le pause e le scadenze
   originali; un'operazione interrotta puo attendere la scadenza della vecchia
   prenotazione (fino a 90 secondi per Commons o 180 per 1000bit).

**`-ConfirmRestore` autorizza la sostituzione completa del database e delle
fotografie del progetto indicato. Non effettua un'unione.** Prima salva sempre
un backup automatico dell'archivio di destinazione in
`backups\prima-del-ripristino-…hhe-backup.tar.gz`. Il progetto Docker sul secondo
PC puo avere un nome diverso: indica il suo nome, senza cambiare quello nella
copia esportata. Il primo PC non viene modificato dal ripristino sul secondo.

Lavora su un PC alla volta: prima di tornare all'altro ripeti esportazione e
ripristino nella direzione opposta. Due archivi modificati indipendentemente
non vengono riconciliati automaticamente. Non usare `docker compose down -v`.

## Controlli e gestione degli errori

L'archivio contiene un manifest con data UTC, progetto di origine, revisione
Git, versione principale PostgreSQL, dimensione e SHA-256 di ciascun file.
Prima di fermare i servizi, il ripristino verifica tutti gli hash e rifiuta
percorsi arbitrari, link, file mancanti/duplicati e nomi non portabili.
Gli hash rilevano danni accidentali, **non autenticano l'autore**: ripristina
soltanto backup prodotti da te. Un dump PostgreSQL e un file amministrativo.

Il database viene prima caricato interamente in un database temporaneo con
`pg_restore --single-transaction --exit-on-error`. In caso di errore del dump
il database e le fotografie di destinazione restano intatti. Dopo la copia
delle fotografie, due rinominazioni in un'unica transazione attivano il nuovo
database; il precedente viene eliminato solo dopo il riavvio dei servizi.
I normali errori durante il cambio dei file ripristinano le fotografie precedenti.

Serve spazio per l'archivio, l'estrazione, il backup di sicurezza, una seconda
copia delle foto e il database temporaneo. Il comando non elimina volumi Docker.
La cartella fotografie deve contenere file semplici, come quelli generati da
HHE: directory annidate e link vengono rifiutati, senza ignorarli in silenzio.

PostgreSQL deve avere la stessa versione principale (attualmente **16**).
La revisione Git deve coincidere e non devono esserci modifiche locali ai file
tracciati. Se hai valutato esplicitamente la compatibilita di due revisioni o
usi copie senza Git, `-AllowVersionMismatch` aggira solo il controllo del codice,
mai quello di PostgreSQL o gli hash.

In caso di interruzione del PC/Docker durante il ripristino, conserva il file
originale e il backup `prima-del-ripristino-…`: avvia solo il database, poi
riesegui il ripristino dal backup desiderato. Se lo script segnala file di
recupero `.hhe-restore-*` nel volume, non cancellarli: contengono le vecchie
foto e occorre recuperarle prima di riprovare. Un database
`hhe_previous_…` viene conservato se il riavvio fallisce; il database nuovo e
gia attivo e il backup precedente e disponibile. Controlla:

```powershell
docker compose -p hhe-import-test ps -a
docker compose -p hhe-import-test logs --tail 100 api web
```

Non eseguire contemporaneamente due trasferimenti o altre istanze che scrivono
sugli stessi volumi. Questa procedura copre l'installazione Compose locale del
repository; un'installazione SQLite senza Docker richiede una copia separata.

## Override Compose e verifiche automatiche

Gli script usano esplicitamente `docker-compose.yml` del repository. Con
override personali apri PowerShell ed esegui lo script direttamente per
passare un array (mantieni gli stessi file usati per avviare il progetto):

```powershell
& .\tools\Transfer-HheArchive.ps1 -Mode Export -ProjectName hhe-import-test -ComposeFile @('docker-compose.yml', 'docker-compose.local.yml')
```

Test offline del contenitore di backup, senza Docker o database:

```bash
python -m unittest discover -s tools/tests -v
```

Prova completa su **due progetti Docker nuovi e temporanei**, con immagini
gia compilate tramite `docker compose build` e PowerShell 7 disponibile:

```bash
python tools/tests/transfer_roundtrip.py
```

La prova confronta tutte le righe e sequenze del database, originali ETL,
prezzi/fonti/asserzioni pending, code in pausa e foto WebP servite da FastAPI;
verifica il recupero dal backup automatico e il rifiuto di un dump danneggiato.
Elimina esclusivamente i due progetti temporanei generati dalla prova.

Verifica locale del 15 novembre 2026: **8 test offline superati**, parsing
PowerShell riuscito e prova completa riuscita con **PowerShell 7.4.13 e
PostgreSQL 16 su Docker Linux**. Verificato anche che un archivio svuotato
rimanga vuoto dopo il riavvio, senza ricreare i sistemi dimostrativi.
L'esecuzione nativa su Windows PowerShell 5.1 non e stata possibile in questo
ambiente Linux; il workflow include un controllo sintattico dedicato su
`windows-latest`. La verifica CI remota va confermata su GitHub.
