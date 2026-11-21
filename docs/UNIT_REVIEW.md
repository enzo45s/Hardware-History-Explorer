# Verifica documentata delle unità di memoria — 21 novembre 2026

La revisione ordinaria conserva `Kb`, `KB` e `MB` quando la scala è incerta.
Questa procedura aggiunge **prove documentali per casi specifici** e permette
di applicare le relative correzioni con anteprima e audit. Non parte
automaticamente all’avvio e non richiede chiamate esterne o chiavi API.

## Risultato sulla copia del database

Dopo il pacchetto RAM, la copia del dump contiene **541 specifiche con unità
ancora ambigue su 372 sistemi**: RAM, ROM e una cache. Il set di prove
consente **147 correzioni su 101 sistemi**. Dopo l’applicazione restano
**394 specifiche da esaminare**. Il catalogo conserva tutti i 1.133 sistemi.

I confronti delle righe hanno verificato che:

- le 9.557 specifiche conservano i propri ID; vengono cambiati soltanto
  i campi che rappresentano la quantità e l’unità nei 147 casi riconosciuti;
- sistemi, produttori, configurazioni, categorie, prezzi, date, note,
  descrizioni, ricerche e originali delle importazioni restano invariati;
- sono conservate le 606 associazioni fotografiche; i file delle immagini
  locali non sono inclusi nel dump e non sono stati verificati;
- tutti i collegamenti specifica-fonte originali sono conservati. Tre
  evidenze vengono completate con il chiarimento dell’unità senza perdere
  il testo precedente; vengono aggiunti 151 collegamenti alle prove e
  15 riferimenti bibliografici nuovi;
- nessun precedente stato di verifica storica cambia. I nuovi collegamenti
  alle prove hanno stato `pending`;
- la visualizzazione riunisce altre **nove righe RAM equivalenti su nove
  sistemi**, mantenendo i relativi ID e tutte le citazioni nei dati;
- un nuovo esame propone zero correzioni e riconosce le 147 regole già
  applicate. Non crea un altro audit quando non vi sono modifiche.

La copertura RAM rimane 872 sistemi con una quantità documentata e 261 senza:
questo intervento chiarisce le unità dei valori presenti. Il risultato riguarda
la copia fornita e aggiornata con il pacchetto RAM, non un accesso remoto al Mac.

## Come si verifica un’unità

La presenza di un numero familiare, del nome della CPU o di una quantità
simile in un altro modello non dimostra la scala. Sono utilizzate quattro
forme di evidenza:

1. **Unità IEC esplicita**: per esempio una fonte scrive `640 KiB` per PPC640.
2. **Definizione nel documento**: il glossario del *Commodore 128 System
   Guide* definisce «Kilobyte (K): 1,024 bytes».
3. **Mappa con indirizzi di byte**: la RAM del Macintosh 128K fra `0x000000`
   e `0x01FFFF` misura 131.072 byte, cioè 128 KiB; una pagina CPC fra due
   confini distanti `0x4000` vale 16.384 byte.
4. **Calcolo esplicitamente supportato**: la RAM del Macintosh 512K viene
   descritta come quadrupla del 128K, quindi 4 × 131.072 = 524.288 byte.
   L’equivalenza dichiarata per il 512Ke riguarda la RAM, senza attribuirgli
   automaticamente la stessa ROM.

Il set comprende manuali Commodore, Acorn, Atari, la guida tecnica CPC di
Bob Taylor e Thomas Defoe, il riquadro *The Macintosh Memory Map* di BYTE
del febbraio 1984 e revisioni fissate di Wikipedia. Le prove contengono URL,
brevi citazioni, sezione, calcolo motivato e hash del testo consultato.
Gli hash dei manuali scansionati si riferiscono al testo OCR, non al PDF.
Wikipedia mantiene attribuzione e licenza CC BY-SA 4.0; non si presume una
licenza aperta per gli altri documenti e non vengono ripubblicati testi integrali.

### Casi MSX

Le regole MSX richiedono che la **stessa scheda 1000bit già archiviata**
dichiari MSX BASIC e la relativa generazione. Si conservano URL, identificazione
originale ed evidenza del sistema operativo della scheda.

Il *MSX Technical Data Book* descrive la ROM standard di 32K byte fra `0000H`
e `7FFFH`: sono 32.768 byte. Il *MSX2 Technical Handbook* distingue MAIN-ROM
da 32K e SUB-ROM da 16K e documenta pagine delimitate da `0000H`, `4000H`,
`8000H` e `C000H`: la ROM standard è quindi 48 KiB. Solo quantità dichiarate
esattamente corrispondenti vengono trattate da queste regole ROM.

Per la RAM non viene assegnata una dotazione usando il solo standard.
Nei casi selezionati viene conservato il numero già riportato e si verifica
se l’interpretazione in bit sia compatibile con il minimo documentato:
per esempio, su un sistema dichiarato MSX2, «128 Kb» letto come kilobit
significherebbe 16 KiB, meno dei 64 KiB minimi della RAM principale.
L’interpretazione in byte e la scala delle pagine sono documentate nella regola.
La VRAM viene controllata separatamente con il proprio minimo.

I casi per cui entrambe le letture rimangono possibili vengono esclusi,
come una RAM MSX1 indicata con «64 Kb»: 64 kilobit corrisponderebbero a 8 KiB,
che non è inferiore al minimo indicato retrospettivamente nel manuale MSX2.
Sono esclusi anche valori misti con SRAM/CMOS o parti non interpretabili.

Queste sono interpretazioni documentate della notazione. **La correttezza
storica di ogni dotazione, revisione e limite continua ad avere il proprio
stato di verifica**. Una quantità preesistente non diventa certificata perché
la sua unità è stata chiarita.

## Applicazione sul Mac

Apri il Terminale nella cartella del progetto, con Docker Desktop avviato.
Usa il nome del progetto Compose contenente i tuoi dati se diverso da
`hhe-import-test`. Esegui i comandi nella stessa finestra del Terminale.

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Conserva un nuovo backup:

```sh
mkdir -p backups
HHE_UNITS_TAG=$(date +%Y%m%d-%H%M%S)
docker compose -p hhe-import-test exec -T db pg_dump -U history -d hardware_history --format=custom --no-owner --no-privileges --file="/tmp/hhe-prima-unita-$HHE_UNITS_TAG.dump"
docker compose -p hhe-import-test cp "db:/tmp/hhe-prima-unita-$HHE_UNITS_TAG.dump" "./backups/hhe-prima-unita-$HHE_UNITS_TAG.dump"
```

Prepara e conserva l’anteprima:

```sh
docker compose -p hhe-import-test exec -T api python -m app.unit_review preview --output "/tmp/hhe-unita-$HHE_UNITS_TAG.json"
docker compose -p hhe-import-test cp "api:/tmp/hhe-unita-$HHE_UNITS_TAG.json" "./backups/hhe-unita-$HHE_UNITS_TAG.json"
```

Il riepilogo stampa `documented_corrections`, `affected_computers` e
`remaining_entries`. Il JSON contiene valori prima/dopo, prove e lista
residua con produttore, modello, configurazione, valore e citazioni.
Il nome del file deve essere nuovo per conservare le anteprime precedenti.

Per applicare il piano:

```sh
docker compose -p hhe-import-test exec -T api python -m app.unit_review apply --plan "/tmp/hhe-unita-$HHE_UNITS_TAG.json"
```

Ricarica il sito. Sulla copia esaminata il comando restituisce `updated: 147`.
`sources_linked` conta le associazioni alle prove elaborate, incluse quelle
già presenti la cui evidenza è completata; non è il numero di nuovi URL.
Un nuovo esame con un nome di output diverso restituisce zero correzioni e
147 regole già risolte. Le 394 voci ancora ambigue rimangono nel resoconto.

Il comando usa un set di prove installato con il codice, senza download a
runtime. Per i casi residui serviranno nuove evidenze e un aggiornamento del
set; rilanciare il comando invariato conserva quei valori.

## Garanzie e limiti

Le regole in `backend/app/importing/data/unit-proofs-v1.json` identificano
modello, configurazione, campi originali e URL di attribuzione esatti.
Non vengono applicate a tutti i prodotti di un marchio o a tutte le unità
KB del database. Quantità cambiate, configurazioni distinte e associazioni
diverse non vengono sovrascritte da una corrispondenza approssimativa.
Bit espliciti, punti interrogativi e testi incerti richiedono un altro esame.

L’applicazione è atomica e usa il lock comune del catalogo. Vengono ricalcolate
le operazioni sotto lock: modificare le operazioni nel JSON non altera ciò
che il motore esegue. Se specifiche, attribuzioni, identità rilevanti o set
di prove cambiano, serve una nuova anteprima. I valori originali e le evidenze
precedenti sono conservati in `catalog_reconciliations`, con `entity=unit_review`.
Non è richiesta una migrazione dello schema.

Restano casi che richiedono manuali più precisi, distinzione fra capacità
fisica e memoria disponibile al software o verifica della quantità stessa.
Il testo troncato della RAM Amiga 2000 e il valore con punto interrogativo del
CBM 8296-D sono lasciati da esaminare. Le parole da 12/18 bit e i registri non
vengono trasformati in capacità convenzionali a byte.

Sono state usate API pubbliche e consultazioni limitate di documenti accessibili.
CPC Wiki ha restituito HTTP 403; è stata usata una diversa guida tecnica
pubblicamente archiviata. Il volume *Macintosh Family Hardware Reference*
segnalato come riservato su Internet Archive non è stato scaricato. Nessun
blocco o controllo di accesso è stato aggirato.

## Verifiche eseguite

- Backend completo su SQLite: **854 test superati**, uno specifico PostgreSQL
  saltato. Su PostgreSQL: **51 test superati**, comprese migrazione, revisione,
  recupero RAM, visualizzazione e applicazione delle prove.
- Frontend: **31 test superati** e compilazione React riuscita. Rimane
  l’avviso Vite sulla dimensione del bundle, già presente.
- Docker Compose: immagini compilate, servizi avviati e health check superati;
  CLI provata anche nel contenitore API.
- Copia isolata del dump: anteprima, applicazione, conservazione delle righe e
  secondo passaggio senza nuove operazioni. I confronti comprendono le
  attribuzioni originali e i relativi stati di verifica.
- Chromium con API in sola lettura sulla copia corretta: BBC Master 128 mostra
  una sola riga RAM da 128 KiB con citazione del manuale; layout a 320 e 390 px
  senza overflow né errori JavaScript. Immagini e font esterni erano bloccati
  durante questa prova: la disponibilità delle immagini non è stata verificata.
