# EarthStation-I e Mistrum — revisione del 24 novembre 2026

Aggiornamento offline di **due schede già esistenti**, richiesto dall’utente.
La voce catalogata con produttore «Amaterske RADIO» è il **Mistrum**;
non viene creata una macchina chiamata «Amaterske RADIO».

Il [pacchetto](../../../backend/app/importing/data/earthstation-mistrum-v1.json)
contiene due descrizioni italiane originali, **44 asserzioni tecniche** con
citazioni individuali, nove note contestuali, otto rettifiche puntuali e quattro
fotografie collegate per URL. Non introduce tabelle, pannelli, code o ricerche
all’avvio. Non richiede API a pagamento né collegamenti esterni durante l’import.

## Fonti consultate

- [Jozef Bogin, ALLOY EarthStation-I](https://boginjr.com/electronics/old/earthstation/),
  pubblicato il 21 aprile 2020, aggiornato il 17 agosto 2020: articolo, foto e
  distinzione fra macchina, esperimenti moderni e modelli successivi.
- [Manuale EarthStation-I, pp. 24–25 fotografate nell’articolo](https://boginjr.com/wp-content/uploads/earthstation-9.jpg):
  fonte primaria per CPU, RAM di base/espansione, ROM, connessioni, dimensioni,
  alimentazione e condizioni operative. L’autore dell’articolo distingue
  correttamente la modalità Hi-Res CGA dall’etichetta MCGA usata nel manuale.
- [Speccy4ever, Amaterske RADIO](https://speccy4ever.speccy.org/_AR.htm):
  indice di quattro immagini ROM e collegamenti a documentazione e repliche.
- [Amatérské radio, serie B, n. 1/1989, PDF collegato dall’indice](https://speccy4ever.speccy.org/doc/Mistrum.pdf):
  sezione Mistrum dalla pagina stampata 12 (pagina 14 del PDF). Tabella tecnica,
  architettura, mappa memoria e costruzione del progetto storico. PDF scansionato,
  consultato con OCR e controllo visivo delle tabelle; non redistribuito.
- [Repository della replica di Lazarus Long](https://github.com/Lazarus-L-o-n-g/Mistrum/blob/aa26429e2c25ac1d110006df405b51f3f540dad2/README.md),
  con [licenza nella stessa revisione](https://github.com/Lazarus-L-o-n-g/Mistrum/blob/aa26429e2c25ac1d110006df405b51f3f540dad2/LICENSE):
  fotografia della replica e contesto del progetto moderno. Tastiera Cherry MX
  e adattatore video moderni non diventano dotazione del Mistrum storico.

Consultazione selettiva delle pagine indicate dall’utente e dei documenti da esse
collegati. Robots di boginjr.com consultato: nessuna esclusione delle pagine usate.
Speccy4ever non espone un robots.txt (404). Nessuno scraping massivo, download
ROM o ripubblicazione dei manuali. Hash dei documenti e revisione del repository
sono conservati nel pacchetto e nell’audit. Tutte le nuove asserzioni sono
`pending`, senza certificazione storica automatica.

## Rettifiche principali

| Scheda | Rettifica e contenuto |
| --- | --- |
| EarthStation-I | NEC **V40** a 8 MHz, non V20; **256 KB** di base, espandibili a **768 KB**; NCR 7280; ARCnet, porte seriale/parallela, ROM, tastiera e specifiche del manuale. Categoria Workstation al posto della precedente categoria Personal computer, se non verificata o modificata. |
| Mistrum | **UA880D (Z80A)** a 3,5 MHz, come scritto nel documento; **64 KB RAM fisica**, **16 KB EPROM**, **8 KB SRAM video separata**. La EPROM può essere disattivata via software per accedere a tutta la RAM. Non si conserva la falsa scelta RAM 16/48 KB ereditata dalla classificazione Spectrum. |

Le quantità KB sono trascritte nella notazione storica del documento: nessuna
conversione indiscriminata da 1000 a 1024. La RAM resta un solo campo principale;
gli 8 KB video del Mistrum non sono sommati alla RAM generale.

La data 1987 dell’esemplare EarthStation-I non viene trasformata in un giorno di
lancio. Il fascicolo Mistrum 1/1989 documenta la pubblicazione del progetto, non
una prima vendita. Il riferimento preesistente 1988 resta intatto. Non si
importano come prezzo del computer i 5 Kčs della rivista, il prezzo di una
replica o quello del Didaktik citato in un ricordo personale. L’indicazione
«oltre 1.000 dollari nel 1991» dell’articolo EarthStation-I resta un’affermazione
contestuale, non un prezzo esatto o di lancio. **Offerte, mercati e date esistenti
non vengono modificati.**

## Fotografie e crediti

- EarthStation-I: vista con accessori, pannello posteriore e scheda madre,
  **Jozef Bogin**. Il [disclaimer](https://boginjr.com/disclaimer/) riserva i
  diritti; l’utente ha confermato in chat il **24 novembre 2026** l’autorizzazione
  dell’autore all’uso delle foto in HHE. Questa autorizzazione è conservata con
  i metadati; **non viene dichiarata una licenza libera**. Nessun file fotografico
  è copiato nel repository.
- Mistrum: foto della **replica moderna** nel README di Lazarus Long,
  attribuzione e **CC BY-NC-SA 4.0** secondo la licenza del repository. Didascalia
  esplicita: non un esemplare originale del 1989. Provenienza e condizioni sono
  collegate nella galleria.

Le precedenti foto dell’uragano dalla stazione spaziale e della cantante sono
ritirate **solo** se corrispondono agli URL esatti e conservano la didascalia
«Scelta automatica Commons». I loro metadati vengono conservati nell’audit.
Le altre foto e le copertine curate a mano restano presenti; una nuova copertina
è assegnata solo in assenza di una copertina manuale.

## Applicazione sul computer locale

Dalla cartella del repository, sul Mac o su Windows:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima di sola lettura:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.earthstation_mistrum
```

Applicazione esplicita al database collegato all’API:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.earthstation_mistrum --apply
```

Ricaricare il sito. Il pacchetto operativo va applicato con questo comando,
non caricato come JSON generico: le rettifiche e le foto sono operazioni ulteriori
rispetto al normale staging di dati. Nessuna applicazione automatica al riavvio.

Abbinamento per produttore e modello, senza ID predefiniti. Schede assenti,
ambigue o con più configurazioni sostanziali sono saltate. Non vengono creati
calcolatori, produttori o doppie schede tecniche. I valori verificati e le
modifiche che non coincidono esattamente con il dato precedente previsto sono
conservati; le alternative restano asserzioni conflittuali. I testi curati non
sono sostituiti: si aggiornano descrizioni mancanti o i vecchi testi preimpostati.

Operazione transazionale: un errore annulla anche rettifiche, fonti e foto.
La seconda applicazione restituisce `already_applied`, non duplica dati e non
ricrea schede o immagini successivamente eliminate. Gli originali ETL e gli
audit precedenti restano intatti. Audit specifico: `targeted_research`.

## Verifica

[verification.json](verification.json) documenta l’applicazione su una copia
PostgreSQL dell’archivio: 2 schede aggiornate, 7 specifiche rettificate e una
ritirata; 44 specifiche complessive nelle due schede, 9 fatti contestuali e 5
nuove fonti. Tre foto EarthStation-I e una replica Mistrum sostituiscono i due
abbinamenti automatici estranei. Restano 1.142 sistemi e 1.179 configurazioni;
le 1.144 commercializzazioni e tutti i dati degli altri 1.140 sistemi sono
invariati. Ripetizione senza modifiche.

I test in `backend/tests/test_earthstation_mistrum.py` controllano identità,
fonti, RAM fisica, offerte, fotografie e relativi crediti, idempotenza, dati
verificati/manuali, schede assenti o ambigue e rollback anche dopo la modifica
delle immagini. Le prove cloud non aggiornano il database del Mac.

Validazione finale: **854 test backend SQLite superati**, due controlli esclusivi
PostgreSQL saltati su SQLite ed eseguiti tra i **25 test PostgreSQL superati**.
API e contesto dell’assistente leggono le nuove capacità con le fonti. Browser
sulla build React di produzione: entrambe le schede, un solo campo RAM
principale, foto/crediti/licenze e layout desktop/mobile verificati, senza errori
JavaScript. Per il rendering nel browser cloud sono stati serviti gli stessi
JPEG scaricati dagli URL HTTPS citati, senza modificare le API o i metadati.
