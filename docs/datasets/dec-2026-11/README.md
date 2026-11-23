# Ricerca Digital Equipment Corporation — novembre 2026

Il pacchetto offline [dec-research-v1.json](../../../backend/app/importing/data/dec-research-v1.json)
arricchisce 19 schede DEC presenti nella copia del catalogo ricevuta e censisce
**VAX-11/780, VAX-11/750 e GIGI (VK100)**. Contiene 22 introduzioni italiane,
181 asserzioni tecniche con fonte ed evidenza individuale, 23 rettifiche puntuali
e una rettifica della categoria del DEC 2000 Model 300 AXP da workstation a server.
Non esegue ricerche online durante l’applicazione e non richiede chiavi API.

## Applicazione sul Mac o su Windows

Dalla cartella del repository, aggiornare il branch e ricostruire i servizi:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

È consigliabile conservare prima un normale backup del database locale con gli
strumenti di esportazione già disponibili. Un’anteprima **di sola lettura** mostra
i modelli riconosciuti, quelli nuovi, le rettifiche applicabili e i casi esclusi:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.dec_research
```

Per applicare il pacchetto al database usato da quel servizio API:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.dec_research --apply
```

Ricaricare l’interfaccia: i sistemi si trovano nel catalogo, nella pagina del
produttore, nella timeline e nel confronto. Le citazioni sono nelle schede e
nell’importazione `dec-research-v1.json` del pannello **Fonti e verifiche**.
Il pacchetto ha un formato operativo dedicato: usare questo comando, non caricare
il JSON completo come un generico file di descrizioni.

Il comando opera sul database del PC sul quale viene eseguito; il test nel cloud
non modifica il database del Mac. Non importa fotografie né nuovi prezzi.

## Comportamento e conservazione dei dati

- Solo i tre nuovi modelli esplicitamente richiesti possono essere creati.
  Le altre 19 schede, se eliminate dall’operatore, non vengono ricreate.
- Gli alias DEC/Digital e VAX con o senza trattino e GIGI/VK100 evitano doppioni.
  Due schede concorrenti o più configurazioni sostanziali vengono segnalate e
  saltate; non si decide arbitrariamente quale accorpare.
- Si arricchisce l’unica configurazione esistente conservandone nome e ID.
  Viene risolto anche il caso di una scheda tecnica riservata agli alias di
  vecchie varianti: non si tenta di creare una seconda configurazione omonima.
- Si sostituiscono solo descrizioni mancanti o il preciso vecchio testo generato.
  I testi già curati o verificati restano conservati; la nuova proposta rimane
  una normale asserzione in conflitto da consultare nelle verifiche.
- Le rettifiche richiedono corrispondenza esatta con il vecchio valore a sei campi.
  Valori modificati dall’operatore e asserzioni già verificate non vengono
  sostituiti. La categoria cambia solo se l’intero insieme precedente è esattamente
  `Workstation` e non c’è una verifica umana della categoria.
- Originali, fonti, evidenze e valori ritirati vengono conservati in ImportJob,
  ImportClaim e nell’audit `dec_research`. Nessun nuovo dato viene dichiarato
  automaticamente verificato. I crediti delle sintesi da Wikipedia restano visibili.
- L’intera applicazione è transazionale: qualsiasi riga fallita annulla anche
  tutte le rettifiche. Ripetere lo stesso pacchetto restituisce `already_applied`;
  non duplica dati e non ricrea neppure un nuovo modello eliminato dopo l’import.
- Il pacchetto si applica solo su richiesta esplicita, non a ogni avvio. Non
  reintroduce i pannelli di ricerca storica o RAM ritirati.

## Fonti realmente consultate e utilizzate

Ricerca del 23 novembre 2026: consultazione selettiva degli indici e dei manuali
DEC in Bitsavers e Internet Archive e delle voci enciclopediche tramite API
ufficiali Wikimedia. Le copie integrali dei documenti restano fuori dal repository:
si distribuiscono dati fattuali, brevi evidenze e riferimenti, senza presumere una
licenza libera sui manuali. Sono inclusi URL, SHA-256 dei PDF e, quando usato,
URL e SHA-256 dell’OCR. Le voci Wikipedia citano una revisione precisa e gli
autori con licenza CC BY-SA 4.0. In totale: **15 manuali e 9 revisioni Wikipedia**.

| Gruppo | Documentazione impiegata |
| --- | --- |
| GIGI | [VK100 Technical Manual, aprile 1982](https://bitsavers.org/pdf/dec/terminal/gigi/EK-VK100-TM-001_VK100_Technical_Manual_Apr82.pdf); voce ReGIS per il contesto storico |
| VAX-11/780 | [Hardware User’s Guide, febbraio 1979](https://bitsavers.org/pdf/dec/vax/780/EK-11780-UG-001_VAX-11_780_Hardware_Users_Guide_197902.pdf); Technical Description MM780, aprile 1978, per la cache |
| VAX-11/750 | [CPU Technical Description, marzo 1981](https://bitsavers.org/pdf/dec/vax/750/EK-KA750-TD-002_VAX_750_CPU_Technical_Description_198103.pdf) |
| VAX-11/785 | [Hardware User’s Guide, 1984](https://bitsavers.org/pdf/dec/vax/785/EK-11785-UG-PRE_VAX-11_785_Hardware_Users_Guide_1984.pdf) |
| MicroVAX I / II | Technical Description KD32-A, agosto 1984; User’s Guide KA630, febbraio 1986 |
| MicroVAX 3100 / 3400 / 3500 | Owner’s Manual 3100, agosto 1989; Technical Information 3400, settembre 1988; KA650 Technical Manual, marzo 1989 |
| PDP-1 / PDP-11 | PDP-1 Handbook, giugno 1963; PDP-11 Architecture Handbook, 1983 |
| Rainbow | Technical Manual Addendum PC100-A, PC100-B e Rainbow 100+, dicembre 1984 |
| DECmate II | [DECmate II Owner’s Manual](https://archive.org/details/decmate-ii-owners-manual), appendice delle specifiche |
| DECstation 2100 / 3100 | Functional Specification DS3100, revisione 3.1, agosto 1990; voce DECstation per i modelli |
| DECmate III, DECstation 5000/133, DECpc/DEC 2000 AXP | Voci DECmate, DECstation e DECpc AXP 150; i manuali Alpha specifici non sono stati reperiti nella ricerca e non si dichiara una conferma primaria |

La FAQ PDP-8 di faqs.org ha restituito un blocco/challenge HTTP 429: non è stata
usata né aggirata. Gli indici 1000bit e la raccolta Columbia consultati non
alimentano questo pacchetto. Il manifesto contiene tutti gli URL effettivamente
citati, senza dipendenze da questi siti durante l’importazione.

## Distinzioni tecniche e limiti

- DECmate II: **64K parole da 12 bit**, non 64 KB; i coprocessori hanno memoria
  distinta. La capacità del DECmate III rimane irrisolta perché le fonti secondarie
  confondono byte e parole e gli schemi consultati non bastano a risolverla.
- GIGI: 16 KB di RAM indirizzata dal processore (intervallo 8000–BFFF), distinta
  dallo spazio disponibile a BASIC e dalla memoria grafica. CPU Intel 8085A,
  ReGIS, BASIC, 768 × 240; classificato come terminale programmabile.
- MicroVAX II: ciclo di microistruzione 200 ns, frequenza operativa 5 MHz; non
  si usa come frequenza CPU l’oscillatore a 40 MHz. Per KA650 si distinguono il
  ciclo di 90 ns e il dato operativo di 11,11 MHz dal clock d’ingresso.
- VAX-11/785: processore KA785, non il T11 della console. Le risoluzioni dei
  terminali esterni non diventano una grafica nativa di VAX o PDP-11.
- VAX-11/780: il manuale MM780, §1.10, documenta una cache di **2048 longword**,
  cioè 8192 byte. Si importano quindi 8 KB, scartando il dato secondario di 2 KB
  che confonde il numero di longword con i byte.
- PDP-11 è attualmente una scheda di famiglia: non si inventa una CPU, frequenza
  o dotazione RAM universale. PDP-1 mantiene parole a 18 bit e CRT opzionale a punti.
- Nei Rainbow il secondo processore Z80A e la grafica opzionale hanno campi
  esplicitamente distinti dal processore principale e dalla modalità testuale.
  I dettagli esclusivi dell’allestimento 190-B non sono documentati a sufficienza.
- I limiti di memoria di lancio, le opzioni successive e una quantità installata
  non sono intercambiabili. Per MicroVAX I/3500 e VAX-11/785 sono documentate
  opzioni o limiti; una dotazione iniziale unica non viene inventata.
- Date e prezzi delle schede già presenti restano invariati. Eventuali divergenze
  degli anni legacy, per esempio MicroVAX II 1984 rispetto all’introduzione 1985
  citata nella nuova descrizione, richiedono una revisione distinta delle offerte.

## Verifica sulla copia del catalogo

L’importazione viene provata su un clone PostgreSQL separato della copia ricevuta,
senza intervenire sul dump originale o sul Mac. Il resoconto con i conteggi
effettivi e le verifiche si trova in [verification.json](verification.json).

Test automatici: `backend/tests/test_dec_research.py` e regressione sul riuso della
configurazione in `backend/tests/test_catalog_cleanup.py`; vengono esercitati
il pacchetto reale, gli alias, i valori già verificati, l’atomicità, l’anteprima
di sola lettura, la conservazione delle foto e la ripetizione dopo una cancellazione.
