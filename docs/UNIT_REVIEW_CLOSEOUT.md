# Standardizzazione della memoria — 22 novembre 2026

La seconda revisione tratta tutte le **394 specifiche residue su 291 sistemi**
della copia del dump già aggiornata con RAM e prima revisione delle unità:

| Esito | Specifiche |
| --- | ---: |
| Notazione chiarita e resa IEC | 365 |
| Quantità o organizzazione corrette mediante un riscontro documentale | 20 |
| Indicazione non quantificabile, conservata come annotazione | 9 |

Dopo l’applicazione il campione non contiene più le notazioni legacy segnalate
come ambigue. Questo **non significa catalogo interamente verificato o completo**:
restano le [nove indicazioni non quantificabili e sei specifiche parziali](UNIT_REVIEW_PENDING.md),
oltre alle altre lacune storiche già note. Il pannello mostra questi conteggi
separatamente dal numero delle unità ambigue, anche dopo aver applicato il piano.

## Uso dal pannello amministrativo

Sul Mac, nella cartella del progetto e con Docker Desktop avviato:

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Conserva un backup come indicato in [Applicazione sul Mac](UNIT_REVIEW.md#applicazione-sul-mac).
Apri **Amministrazione → RAM e varianti → Unità di memoria**, quindi:

1. Premi **Controlla unità di memoria**.
2. Esamina i valori prima/dopo, filtrabili per modello, e le fonti. Le
   annotazioni non quantificabili e i dati parziali hanno elenchi separati.
3. Scarica il resoconto con originali, motivazioni e prove.
4. Premi **Applica la revisione documentata delle unità**.

Il numero proposto dipende dai dati effettivi. Se non hai applicato la prima
revisione, il set include anche le sue 147 regole, per 541 casi complessivi su
372 sistemi. Modelli, valori, configurazioni o attribuzioni diversi restano
fuori dalle regole; non vengono forzati per ottenere un conteggio di zero.
Una nuova analisi non ripete le modifiche già applicate. Se il catalogo cambia
fra anteprima e applicazione, l’operazione viene rifiutata e serve una nuova analisi.

Resta disponibile la CLI `python -m app.unit_review preview --output ...` e
`python -m app.unit_review apply --plan ...`, con la stessa logica e gli stessi
controlli. I vecchi piani v1 richiedono una nuova anteprima v2.

## Criteri adottati

La normalizzazione ordinaria continua a conservare i prefissi incerti.
Le nuove decisioni sono limitate a identità, configurazione, valori e URL
esatti in `backend/app/importing/data/unit-proofs-v2.json`; il file estende
il precedente set v1. Non esiste una conversione globale da Kb/KB a KiB.

Per la memoria a semiconduttori viene esplicitamente adottata la convenzione
storica JEDEC: K = 1024, M = 1048576 e G = 1073741824. La convenzione è
riportata nella revisione fissata dell’articolo *JEDEC memory standards* e
viene espressa con i prefissi IEC, oggi preferibili. Dove necessario, un
riscontro del modello o della famiglia chiarisce il significato byte; per
le asserzioni già espresse con B maiuscola viene esplicitata la convenzione
sui soli record riesaminati. **Una convenzione di normalizzazione non certifica
la dotazione storica riportata dalla fonte.** Non si applica a dischi, reti,
bit, parole o caratteri di larghezza diversa da otto bit.

Alcune letture RAM sono disambiguate dai requisiti minimi dell’ambiente
operativo dichiarato dalla medesima scheda: per esempio 4 megabit non
basterebbero per il minimo di Windows 3.1. Le prove conservano anche questa
premessa; non si assegna una dotazione usando il solo sistema operativo.

I riscontri comprendono revisioni Wikipedia con attribuzione/licenza e
manuali o prospetti pubblici Commodore, Olivetti, Sharp e Morrow. È stato
consultato il manuale Olivetti *Personal Computer Pocket Service Guide*,
Volume 1, sesta edizione. Il prospetto M22 è stato reperito dal collegamento
nella scheda 1000bit autorizzata; le cifre sono state controllate anche sulle
immagini del documento. Le altre schede 1000bit già archiviate sono state
riutilizzate senza un nuovo scraping del sito. Sono inclusi solo estratti
pertinenti e metadati delle prove, non copie integrali dei documenti.

I checksum distinguono testo OCR, testo estratto dal PDF, revisione wikitesto
e asserzione già archiviata. Quest’ultimo caso **non è una nuova consultazione
del documento** e non viene presentato come riscontro indipendente della
quantità. Nessuna nuova quantità è ricavata da codice di emulatori.

## Correzioni significative

- **Commodore 116:** 16 KiB fisici, distinti dai circa 12 KiB disponibili al BASIC.
- **Olivetti M20 BC/ST:** 64 kilobit di ROM corrispondono a 8192 byte, cioè
  8 KiB; quattro dispositivi da 16 kilobit non sono quattro da 16 kilobyte.
- **M111:** il manuale originale documenta esplicitamente 640 KB di RAM; la
  notazione viene chiarita in 640 KiB senza introdurre una nuova dotazione.
- **KIM-1:** i due MCS6530 comprendono 2048 byte di ROM complessivi, non 1 KiB.
- **CBM 8296-D:** il prospetto del produttore documenta 128 KiB, sostituendo
  l’asserzione precedente con punto interrogativo e conservandola nell’audit.
- **P6060:** il prospetto distingue 16 KiB iniziali per l’utente e massimo
  fisico di 80 KiB. La capacità ROM non viene dedotta dalla RAM che ospita il
  sistema operativo.
- **M22:** il prospetto descrive tre aree ROM da 32 KiB, con funzioni distinte;
  il precedente valore da 16 Kb viene sostituito dalla descrizione degli ambiti.
- **Toshiba T1000:** 512 + 768 = 1280 KiB con la scheda documentata; il numero
  arrotondato «1.2» non diventa un valore binario esatto inventato.
- **ELEA 6001:** da 10.000 a 100.000 posizioni, ciascuna con quattro bit di dato
  e due di controllo. Le posizioni non vengono equiparate a byte moderni.
- **P652:** la fonte descrive 4096 unità RAM da quattro bit, distinte dalla
  ROM da sedici bit; le estensioni non vengono ricavate dal vecchio intervallo.
- **PC-1245:** sono riportati i 1486 byte disponibili per programmi e dati
  documentati nel manuale; la capacità fisica complessiva resta non determinata
  dal precedente valore arrotondato «2,2 Kb».

- **Acorn System 2/3/4:** configurazioni base da 4, 8 e 16 KiB riportate nei
  rispettivi paragrafi del riferimento, sostituendo la somma RAM/CMOS priva di ambito.
- **Altair 680:** il catalogo MITS dichiara 1024 parole RAM; la larghezza della
  parola non viene inventata per convertirle in byte.

## Conservazione dei dati e ripetibilità

Sulla copia isolata il confronto delle righe conferma:

- tutti i 1133 sistemi, 1713 configurazioni e 9557 ID delle specifiche conservati;
  nessuna creazione o eliminazione di specifiche;
- cambiati soltanto quantità, testo, unità e, per le nove annotazioni, la proprietà;
- produttori, categorie, prezzi, date, descrizioni, note, originali delle
  importazioni e 606 associazioni fotografiche invariati;
- tutte le attribuzioni originali conservate; 110 evidenze integrate senza
  perdere il testo precedente; 97 fonti e 665 collegamenti nuovi;
- stati di verifica precedenti conservati, nuovi collegamenti `pending`;
- audit con valori prima/dopo e prove; secondo passaggio senza nuove operazioni;
- altre 25 righe equivalenti riunite nella vista, mantenendo gli ID nei dati.

La copertura RAM passa da 872 a **867 sistemi con una quantità dichiarata**:
**266** risultano senza quantità, rispetto ai precedenti 261. Cinque indicazioni
insufficienti non vengono più contate come RAM disponibile solo perché contenevano
un numero. Le organizzazioni native documentate di ELEA/P652 restano quantità
valide, senza diventare conteggi di byte per i confronti.

Il reimport della stessa asserzione ritirata registra un conflitto sul dato
originario e non ricrea una capacità. Anche il recupero automatico RAM evita
quel valore. Il controllo riguarda una decisione già applicata, la stessa
configurazione e fonte e il medesimo originale; una nuova fonte o una modifica
manuale segue le normali regole di revisione.

Le nuove prove possono completare un’annotazione già applicata: il motore
riconosce l’asserzione originale nell’audit e richiede che annotazione, modello,
configurazione e fonte siano ancora invariati. Un’annotazione modificata a mano
non viene sovrascritta. Un aggiornamento del set non nasconde annotazioni prive
di una regola corrente. Questo passaggio è stato verificato anche sul M111
della copia precedentemente annotata.

Le prove sono eseguite su copie isolate. Il Mac non è stato modificato da remoto.

## Verifiche eseguite

- Backend completo SQLite: **867 test superati**, una verifica riservata a
  PostgreSQL saltata. PostgreSQL: **64 test mirati superati**, comprendenti
  migrazione, revisione, RAM, visualizzazione, API e reimportazioni.
- Frontend: **31 test superati**, compilazione React riuscita. Resta l’avviso
  Vite, già presente, sulla dimensione del bundle.
- Chromium su catalogo sintetico isolato: anteprima, filtro per modello,
  download e contenuto del resoconto, applicazione, correzione ROM KIM-1,
  annotazione BCS 2030, conservazione del modello sconosciuto, ripetizione e
  layout a 320/390 px senza errori JavaScript. La prova è inclusa nel workflow CI.
- Chromium sulla copia effettiva, con API in sola lettura: pannello con zero
  nuove operazioni, nove indicazioni non quantificabili e sei parziali; scheda
  BBC Master 128 con 128 KiB e manuale citato, senza errori JavaScript o overflow.
  Immagini e font esterni bloccati durante questa prova.
- Copia PostgreSQL del dump: applicazione di 394 decisioni, confronto delle
  righe, stessi ID, stati conservati e secondo passaggio senza operazioni.
  Su una copia precedente alla v1 sono riconosciute tutte le 541 regole.
- Docker Compose: compilazione, avvio e health check riusciti; CLI verificata
  anche nel contenitore. Un primo tentativo aveva esaurito il disco del cloud;
  è bastato rimuovere cache di compilazione inutilizzata, senza toccare volumi.

I file fotografici non erano nel dump e non sono stati verificati. Questa
revisione non certifica l’intero catalogo né completa le 266 lacune RAM. La
matrice delle unità scalari della copia conserva CPU in MHz e RAM/ROM/cache
in KiB; unità native, intervalli e dotazioni articolate mantengono il proprio
ambito. Capacità dei dischi/floppy e frequenze video non sono convertite
usando convenzioni della RAM.
