# Revisione del catalogo e delle unità — 21 novembre 2026

La procedura esamina il database effettivo, produce un’anteprima e applica
solo modifiche di rappresentazione documentate. Non parte automaticamente
all’avvio. Le fonti, gli originali delle importazioni e gli stati di revisione
restano conservati. Non interroga fonti esterne e non richiede chiavi API.

## Risultati sulla copia fornita dall’operatore

Il dump PostgreSQL 16 è stato ricomposto in ordine `aa`, `ab` e ripristinato
in un database separato, mantenendo una seconda copia originale. Contiene
1.133 sistemi, 186 produttori, 1.566 configurazioni, 9.396 specifiche,
7.209 fonti, 1.783 commercializzazioni e 606 associazioni fotografiche.

La revisione sulla copia di lavoro ha prodotto:

- **450 specifiche normalizzate**: spaziatura delle unità, quantità scalari
  esplicite, distinzione del modello CPU dalla frequenza incorporata.
- **14 nuovi campi frequenza**, ricavati dal testo già documentato e collegati
  alle stesse fonti. Nessuna frequenza stimata dal nome del processore.
- **2 produttori accorpati**: Hewlett-Packard in HP e ASEM S.p.A. in ASEM;
  metadati e precedenti riferimenti conservati nell’audit.
- **162 righe ridondanti eliminate dalla visualizzazione di 158 sistemi**,
  unendo capacità RAM equivalenti e l’unica opzione coincidente. Le 231
  configurazioni interessate nei dati originali possono già essere raggruppate
  nella vista: il conteggio delle righe visibili è quindi diverso.

I 1.133 sistemi conservano i propri ID; i produttori diventano 184 e le
specifiche 9.410 per l’aggiunta dei 14 campi separati. Tutte le 9.396
specifiche originali restano presenti. La pulizia visiva conserva ID e fonti
di ogni dichiarazione accorpata e non elimina banchi di memoria fisicamente
distinti, configurazioni reali, intervalli o limiti minimi/massimi.

Controlli mediante hash delle righe e confronti dei campi hanno confermato la
conservazione di immagini, descrizioni, prezzi, date, mercati, categorie,
configurazioni, fonti, note, originali delle importazioni e ricerche. Le
asserzioni di importazione mantengono stato, evidenza e riferimenti, salvo
l’aggiornamento degli ID equivalenti dei due produttori. I 9.396 collegamenti
originali specifica-fonte sono invariati; i 14 nuovi campi hanno una copia
della relativa attribuzione. Nessuno stato di verifica viene elevato.
Il dump conserva i riferimenti alle immagini, ma non include i file fotografici
locali: la conservazione verificata qui riguarda le associazioni nel database.

Un secondo esame della copia corretta propone **zero modifiche**. Restano
398 voci con prefissi storici o bit/byte ambigui; vengono elencate per il
controllo. I 36 gruppi di commercializzazioni identiche vengono segnalati e
conservati con i loro ID: la vista già li riunisce e non è necessario perdere
le asserzioni che li citano.

Questi risultati riguardano la copia ricevuta, non un collegamento remoto al
Mac. Eventuali modifiche locali successive saranno incluse solo preparando
un’anteprima aggiornata sul computer dell’operatore. Il dump e il piano con
i dati del catalogo non vengono inseriti nel repository.

## Regole sulle misure

- Le frequenze CPU/GPU esplicite vengono espresse in **MHz**, conservandone
  la quantità: 1.000 kHz diventa 1 MHz.
- Byte ed espliciti prefissi IEC possono essere convertiti esattamente in
  **KiB**: 1.024 B = 1 KiB e 1 MiB = 1.024 KiB.
- `KB`, `MB`, `Kb`, `Mb`, indicazioni senza unità e stringhe storiche non
  dimostrano da sole una scala binaria. La procedura non trasforma 1 MB in
  1 MiB e non scambia bit e byte. Anche `mHz` resta distinto da `MHz`.
- Intervalli e alternative rimangono tali. `8-16 Mhz` diventa un campo
  «Frequenze riportate» con `8 - 16 MHz`, non una frequenza standard di 8 MHz.
- `6502A - 1.79Mhz Mhz` viene separato in modello `6502A` e frequenza
  `1,79 MHz`. Se una frequenza già registrata è incompatibile, il caso viene
  segnalato e non sovrascritto.

## Applicazione sul Mac

Con Docker Desktop avviato, apri il Terminale nella cartella del progetto.
Usa il nome del progetto Compose con i tuoi dati se diverso da
`hhe-import-test`.

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Conserva un backup aggiornato del database prima di applicare la revisione:

```sh
mkdir -p backups
docker compose -p hhe-import-test exec -T db pg_dump -U history -d hardware_history --format=custom --no-owner --no-privileges --file=/tmp/hhe-prima-normalizzazione.dump
docker compose -p hhe-import-test cp db:/tmp/hhe-prima-normalizzazione.dump "./backups/hhe-prima-normalizzazione-$(date +%Y%m%d-%H%M%S).dump"
```

Prepara e copia l’anteprima sul Mac:

```sh
docker compose -p hhe-import-test exec -T api python -m app.catalog_revision preview --output /tmp/hhe-normalizzazione.json
docker compose -p hhe-import-test cp api:/tmp/hhe-normalizzazione.json ./backups/hhe-normalizzazione.json
```

Il terminale mostra il riepilogo; il JSON contiene valori prima/dopo e casi
da esaminare. Per una nuova anteprima usa un nome di file diverso, così la
copia già esaminata resta conservata. Per applicare quel piano:

```sh
docker compose -p hhe-import-test exec -T api python -m app.catalog_revision apply --plan /tmp/hhe-normalizzazione.json
```

Ricarica il sito dopo l’applicazione. Il comando restituisce il numero di
modifiche e l’ID dell’audit. L’operazione è atomica e usa il lock comune del
catalogo. Se sistemi, produttori, configurazioni, specifiche o attribuzioni
sono cambiati, il piano viene rifiutato e occorre una nuova anteprima. Il
motore ricalcola le operazioni sotto lock, senza eseguire istruzioni alterate
nel file JSON. Una nuova anteprima dopo l’applicazione non propone di nuovo
le stesse modifiche.

Le modifiche sono registrate in `catalog_reconciliations` come
`entity=normalization`, con valori originali, campi creati e attribuzioni;
gli accorpamenti dei produttori hanno il proprio audit completo. Non è
necessaria una migrazione di schema. Il backup precedente consente un
ripristino integrale, se necessario.

## Verifiche eseguite

- Backend SQLite: 824 test superati; il test riservato a PostgreSQL viene
  saltato in questa esecuzione.
- Backend PostgreSQL 16: 120 test mirati superati su normalizzazione,
  riconciliazione, alias, parser 1000bit e schede tecniche; superati anche
  i tre test di migrazione, incluso quello esclusivo di PostgreSQL.
- Frontend: 31 test superati e compilazione React riuscita. Vite segnala
  il bundle JavaScript principale superiore a 500 kB.
- Docker Compose: compilazione, avvio e health check riusciti.
- Chromium: suite qualità e verifica della scheda BBC Master 128 sul database
  ricevuto, usando API in sola lettura; nessuna opzione RAM identica ripetuta,
  conservazione delle unità ambigue distinte, layout a 320/390 px e assenza
  di errori JavaScript. Le richieste alle immagini esterne erano bloccate:
  questa prova non verifica la disponibilità dei relativi file.
