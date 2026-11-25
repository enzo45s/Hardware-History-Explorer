# General Processor — ricerca e importazione del 24 novembre 2026

Il [pacchetto offline](../../../backend/app/importing/data/general-processor-v1.json)
aggiunge il produttore fiorentino, il suo profilo documentato e i prodotti
identificati nelle fonti consultate. Non ricrea il progetto, non introduce tabelle,
pannelli, code, scraping all’avvio o API a pagamento.

## Contenuto

**Profilo aziendale:** denominazione General Processor S.r.l., Italia, sedi
nell’area fiorentina, fondazione 1977, fondatori Gianni Becattini, Stefano Giusti
e Franco Pirri, descrizione italiana, logo e relativi crediti/condizioni. Il 1976
indicato in un archivio riguarda l’esperienza Micropi che precedette GP. Per la
cessazione viene riportato il 1985 del Museo di Prato; il testo conserva la
discrepanza con le ricostruzioni che indicano «circa 1984». Nessuna verifica
umana automatica e nessun sito archivistico presentato come sito ufficiale GP.

| Scheda | Dati documentati e allestimenti |
| --- | --- |
| Child 8 | Origine del progetto nel 1976, poi commercializzato da GP; scheda Child 8/BS del Kit 8 con Fairchild F8, 1 KB RAM, 1 KB ROM Fair-Bug, bus e terminali opzionali. Il 1975 dei prototipi non diventa un lancio commerciale. |
| Child Z | Presentato nel 1977; allestimento Sistema /05 del manuale 1979 con Z80, 16 KB RAM, 2 KB video e 3 KB EPROM separati, console, video, tastiera e cassette TRI-BIT. |
| Modello T | Famiglia del 1979: configurazione originale con Z80, 16 KB RAM espandibili a 32/48 KB, 4 KB EPROM, 1 KB video, CP/M nelle versioni a disco. Il MKIII del 1981, con 64 KB e tastiera separata, è una seconda configurazione della stessa scheda. |
| GPS4 | Presenza attestata nella pubblicità di maggio 1983, periferiche a disco, più postazioni e funzione di terminale intelligente. CPU, RAM, frequenza e sistema operativo non risultano accertati nelle fonti consultate. |
| GPS5 | Produzione 1985 secondo il Museo di Prato; Intel 80186, 128 KB RAM, opzioni fino a 512 KB nell’archivio secondario, CP/M-86, fino a cinque utenti e periferiche documentate. |

Sono **cinque schede, sei configurazioni, 79 specifiche con citazioni individuali**,
cinque descrizioni italiane originali e dodici note contestuali. Si coprono le sei
denominazioni Child 8, Child Z, Modello T, Model T MKIII, GPS4 e GPS5 senza creare
un doppione del Modello T per la sola variante. T/05, T/08, T/10 e T/20 restano
pacchetti di periferiche/prezzi, non quattro computer aggiuntivi.

Il G5 compare sotto GP in 1000bit, ma la ricostruzione specifica di ComputerHistory
ne documenta la vendita in kit da **SUMUS**, ditta di Gianni Becattini: non viene
attribuito automaticamente a General Processor. I numeri mancanti della serie
GPS non vengono ricavati per interpolazione; questi sono i prodotti verificabili
nelle fonti effettivamente consultate.

## Prezzi, date e RAM

Il listino di **ottobre 1979**, riportato da ComputerHistory con descrizione dei
pacchetti, permette cinque offerte distinte in **ITL, lire italiane, IVA esclusa**:

| Allestimento Modello T | Prezzo |
| --- | ---: |
| Unità centrale base | 1.731.000 ITL |
| T/05 con cassette | 2.212.000 ITL |
| T/08 con minidischi | da 3.289.000 ITL |
| T/10 con floppy da 8 pollici | da 4.572.000 ITL |
| T/20 con disco rigido | da 8.722.000 ITL |

Le offerte conservano la sigla del pacchetto e la data del listino nei dettagli
commerciali. Il 1979 è l’anno del modello, non un giorno di vendita ricavato
dall’anno. L’indicazione «da» e l’IVA esclusa restano visibili nelle note.
Il valore «3594 Euro» della scheda GPS5, senza un documento storico in lire a
supporto, è escluso. Valori zero/valute mancanti non diventano prezzi reali.

Si mantengono distinte presentazione, pubblicazione di un manuale, produzione
musealmente documentata e primo lancio. Per Child 8, GPS4 e GPS5 la
commercializzazione è qualificata come riferimento documentale. I dati del GPS4
non sono copiati dal GPS5. Le frequenze non sono dedotte dal solo tipo di CPU.
Il mercato Italia è associato al listino in lire; per i riferimenti senza prezzo
il mercato rimane non documentato, senza dedurlo dalla sede del produttore.

Ogni configurazione ha una sola RAM principale, con eventuali opzioni a parte;
ROM, memoria video e spazio di indirizzamento non vengono sommati alla RAM.
I 64 KB complessivi indirizzabili del Sistema /05 includono memorie di tipi diversi.
KB mantiene la notazione storica, senza conversioni indiscriminate in byte.

## Fonti effettivamente consultate

- [ComputerHistory.it — azienda GP](https://www.computerhistory.it/storia/aziende/general-processor),
  [Child 8](https://www.computerhistory.it/computer/general-processor/child-8),
  [Child Z](https://www.computerhistory.it/computer/general-processor/child-z),
  [Modello T e listino](https://www.computerhistory.it/computer/general-processor/modello-t),
  [G5 e SUMUS](https://www.computerhistory.it/computer/becattini/g5): ricostruzioni
  di Luigi Serrantoni, con documentazione, pubblicità e testimonianze citate.
- [Il manuale del Kit 8](https://archive.org/details/kit8manuale),
  [Child Z Sistema /05](https://archive.org/details/childzsistema05),
  [depliant Modello T](https://archive.org/details/gpmodellotdepliant),
  [manuale Modello T](https://archive.org/details/gpmodellotmanuale): documentazione
  originale General Processor resa consultabile da Internet Archive. Consultati
  metadati ed esportazioni OCR; non redistribuiti i documenti.
- [Museo del Calcolatore di Prato, Modello T](https://www.museodelcalcolatore.it/singolo.php?cod=263)
  e [GPS5](https://www.museodelcalcolatore.it/singolo.php?cod=266): schede museali
  e informazioni sui rispettivi esemplari.
- [Apulia Retrocomputing](https://www.apuliaretrocomputing.it/wordpress/2021/03/08/modello-t-general-processor-di-firenze/),
  articolo di Alessandro Liberalato; [StoriaInformatica.it](https://www.storiainformatica.it/computers/informatica-italiana?view=article&id=372:general-processor-pionieri-dellhome-computing-made-in-italy).
- [Testimonianza di Franco Pirri conservata su VintageSBC](https://www.vintagesbc.it/vintage-computer-board/collezione/general-processor/general-processor-modello-t/storia-e-modelli/storia-della-gp-secondo-pirri/).
- [1000bit, produttore 95](https://www.1000bit.it/database2.asp?id=95) e schede
  specifiche: [Child 8](https://www.1000bit.it/scheda.asp?id=1518),
  [Child Z](https://www.1000bit.it/scheda.asp?id=1519),
  [Modello T](https://www.1000bit.it/scheda.asp?id=576),
  [MKIII](https://www.1000bit.it/scheda.asp?id=1528),
  [GPS4](https://www.1000bit.it/scheda.asp?id=351),
  [GPS5](https://www.1000bit.it/scheda.asp?id=171),
  [G5](https://www.1000bit.it/scheda.asp?id=2091). I dati controversi non vengono
  trasferiti automaticamente perché presenti nell’archivio.

Letture selettive, senza scraping massivo. Robots consultati. Rispettata
l’esclusione `/images/` di ComputerHistory: nessuna foto scaricata da quel
percorso; documenti originali tramite l’esportazione Archive.org. Wikipedia
non ha fornito una voce utile. Google 429 non ritentato e challenge di ricerca
non aggirato; risultati di ricerca non sostituiscono le fonti lette.

## Logo e fotografie

Il logo aziendale e le immagini Modello T/MKIII e GPS5 sono collegamenti a
1000bit, nel perimetro dell’autorizzazione al recupero già fornita dall’utente,
con le condizioni dichiarate per studio e ricerca. **Non hanno una licenza
libera presunta**. Gli autori non indicati non sono inventati; la galleria
collega alla scheda originale. Non sono copiati file fotografici nel repository.

La [pubblicità GPS-4 su Commons](https://commons.wikimedia.org/wiki/File:Gp_gps4_ad_mc19_mag83.jpg)
ha attribuzione dichiarata **G.becattini, CC BY-SA 3.0**; il titolo la riferisce
a MCmicrocomputer 19, maggio 1983. Il caricamento 2013 non è la data del computer.

Quattro immagini nelle gallerie: Modello T originale, MKIII, pubblicità GPS4 e
GPS5. Non sono associate foto a Child 8 e Child Z in assenza di un riscontro
sufficiente sulle condizioni di riutilizzo. Le foto curate già presenti non
vengono sostituite e restano copertine se così impostate.

## Applicazione sul proprio computer

Dalla cartella del progetto, su Mac o Windows:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima di sola lettura:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.general_processor
```

Applicazione esplicita del produttore e dei modelli:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.general_processor --apply
```

Ricaricare il sito: il produttore appare nella sezione Produttori e i sistemi
nel catalogo, nella timeline, nei confronti e nei dati forniti all’assistente.
Il pacchetto operativo va applicato con questo comando, non caricato come JSON
generico, perché comprende profilo aziendale, offerte e alias con ambito.

Alias espliciti di produttore e grafia, senza confondere Data General o un
abbreviato «GP». `Model T`, `Model T MKIII` e `Modello T MKIII` rimandano alla
famiglia e alle rispettive configurazioni. Le reimportazioni 1000bit non creano
un’altra macchina o una terza scheda tecnica per questi nomi.

Profili esistenti aggiornati solo nei campi mancanti; testi, loghi, dati manuali
e valori tecnici già documentati sono conservati. Le schede preesistenti che
hanno offerte mantengono importi e date: il pacchetto non ricostruisce le loro
commercializzazioni. I valori alternativi restano nei claim conflittuali.
Produttori ambigui bloccano la transazione; schede duplicate o configurazioni
multiple non riconosciute sono segnalate e saltate senza accorpamenti forzati.

Il marker di checksum impedisce di ripetere il pacchetto e di ricreare sistemi
cancellati successivamente. Un errore annulla insieme profilo, computer,
fonti, prezzi, fotografie e alias. Raw ETL, citazioni per campo e audit
`gp_research` conservano la provenienza. Nuove asserzioni e associazioni
bibliografiche `pending`, senza dichiarazioni automatiche di verifica.

## Verifica

[verification.json](verification.json) riporta la prova su una copia PostgreSQL
dell’archivio: un produttore e cinque schede aggiunti, sei configurazioni,
79 specifiche, dieci commercializzazioni (cinque prezzi), dodici note e quattro
fotografie. I 1.142 sistemi precedenti, prezzi, fonti e originali ETL rimangono
intatti. I test coprono anche i due ambiti del Modello T nelle reimportazioni,
i prezzi di pacchetti differenti, i campi curati e il rollback dopo gli alias.
La prova cloud non aggiorna il database del Mac.

Verifiche eseguite:

- Backend: **862 test passati, due saltati perché esclusivi PostgreSQL**;
  **34 controlli PostgreSQL passati**, inclusi normalizzazione, produttori,
  pacchetto GP e concorrenza/migrazione. Dopo gli ultimi aggiustamenti alle
  citazioni del dataset, ripetuti tutti gli otto test GP su entrambi i database.
- Frontend: **45 test passati**, build React di produzione riuscita. Rimane
  l’avviso Vite sulla dimensione del bundle, già presente.
- Docker Compose: ricompilazione e health dell’API riuscite sulla copia isolata.
  Controllati API del catalogo, cronologia, produttore, analisi e confronto;
  il prezzo GPS5 non documentato rimane assente anche dopo l’avvio dell’API.
- Chromium sulla build di produzione: profilo, logo, fonti, cinque schede,
  due configurazioni Modello T, cinque offerte distinte, galleria e ricerca
  MKIII; nessun errore JavaScript o overflow mobile a 390 px. In browser le
  immagini sono state servite agli URL esatti con gli stessi file scaricati
  dalle fonti via HTTPS: non è una verifica del caricamento remoto diretto
  da Chromium nel cloud.
- Contesto dell’assistente: recupero dei nuovi modelli con specifiche e
  citazioni, senza chiamate a servizi AI a pagamento.
