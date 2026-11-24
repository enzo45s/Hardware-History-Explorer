# Sun Microsystems: date e fotografie — 24 novembre 2026

[Pacchetto offline](../../../backend/app/importing/data/sun-dates-photos-v1.json)
limitato alle 24 schede Sun già presenti nel catalogo. Non crea computer,
produttori, configurazioni o prezzi e non modifica il contenuto delle note
originali. Nessun nuovo pannello, lavoro automatico all’avvio o richiesta di rete
durante l’applicazione.

## Date recuperate e rettificate

Nella copia fornita, sette modelli non avevano una data nelle commercializzazioni.
Il campo `Anno lancio` dei fatti **Contesto del prezzo** contiene diversi anni,
ma può riferirsi a un listino successivo. Il recupero conserva quindi la
provenienza e distingue un **anno riportato dalla ricerca** da un **lancio
storicamente documentato**. La presenza della data non certifica un controllo
umano né la vendita a quel prezzo in quell’anno.

| Scheda | Data applicata sulla copia | Tipo di evidenza |
| --- | --- | --- |
| SPARCstation SLC | 1990 | Anno dichiarato nel contesto prezzi; riferimento della ricerca, non nuova verifica della fonte UPI (403). |
| Sun 3/110 | 1986 | Presenza nel catalogo originale Sun di ottobre 1986; giorno del debutto non accertato. |
| Sun 3/260/280 | 1986 | Entrambi i modelli nel catalogo originale di ottobre 1986; il 1988 della nota riguarda un listino successivo. |
| Sun 3/50 | 1986 | Anno dichiarato nel contesto prezzi, conservato come riferimento. |
| Sun 3/E | 1988 | Anno della ricerca/listino; non viene certificato il primo lancio. |
| Sun 4/110 | 1988 | Anno dichiarato nel contesto prezzi, conservato come riferimento. |
| Sun 4/4x0 | 1989 | Riferimento dichiarato per la famiglia; la nota del prezzo 470GX non data tutte le varianti. |
| SPARCstation ELC | 1992 → 1991 | Tabella cronologica SPARCstation alla revisione Wikipedia consultata: luglio 1991. Precisione annuale. |
| Sun 3/60 | 1988 → 1987 | Rettifica del vecchio dato di base con l’anno esplicito della ricerca già importata; riferimento, non verifica indipendente. |
| Sun 4/3x0 | 1987 → 1989 | Stesso criterio, senza generalizzare il prezzo del solo 4/330 a tutta la famiglia. |
| Ultra 45 | 1996 → 2006 | Cronologia Sun Ultra consultata: Ultra 25 e 45 introdotte nel 2006; diversa da Ultra 450 e Ultra 3 mobile. |

Per gli anni recuperati dalle note, il pacchetto legge soltanto il campo
`Anno lancio: AAAA` separato da punto e virgola, associato alla scheda Sun e ad
almeno una fonte esterna. Anni futuri, note discordanti e fonti interne non
producono una data. Non interpreta numeri in prezzi, configurazioni o testo
libero. L’audit conserva identificativi, testo delle note e fonte dell’asserzione.

Le date mancanti vengono compilate sulle offerte esistenti. Solo se non esiste
alcuna commercializzazione è aggiunta una riga senza prezzo e senza mercato
inventato. Importi, valute, tipo di prezzo, mercato, varianti e date di fine
restano intatti. Sul clone sono necessarie **due righe senza prezzo**.

Le quattro rettifiche riguardano soltanto un valore esattamente riconducibile
all’asserzione non verificata del vecchio dataset di base. Una data diversa,
manuale o verificata viene conservata. La data del Sun 2/120 non è sostituita
con il 1986 del suo listino: anno del listino e debutto non sono equivalenti.

Le nuove asserzioni sono `pending`. Le date da note o da prova documentale di
presenza hanno `date_scope=reference`, evidenza `reference` e nota esplicativa;
ELC e Ultra45 hanno evidenza di introduzione del modello. Catalogo, timeline,
confronti e assistente usano le date native, senza una correzione solo grafica.

È corretta anche una regola del normalizzatore: un URL esterno non promuove da
solo un anno di riferimento a data documentata. La qualifica esplicita, la nota
e i suoi identificativi di fonte rimangono coerenti nelle proiezioni e dopo la
pulizia fisica del catalogo. I controlli coprono anche la lettura dall’API e
il riavvio del servizio.

## Undici immagini selezionate

| Scheda | Immagine e provenienza |
| --- | --- |
| SPARCstation 1 | Sistema 4/60 dall’archivio 1000bit; fotografia a risoluzione limitata ma identificata, al posto della scheda madre SPARCstation 10. |
| SPARCstation 1+ | Sistema completo su Commons: il file si chiama `SPARCstation 1.jpg`, ma descrizione e hardware identificano **1+**. |
| SPARCstation 2 | Sistema completo corretto da Commons, al posto della SPARCclassic X. |
| SPARCstation IPC | Sistema lunchbox da Commons. |
| SPARCstation IPX | Sistema di serie da Commons, senza usare la foto del prototipo IPC/IPX. |
| Sun 3/110 | Fotografia pubblica dell’esemplare Prism su Recycled Goods. |
| Sun 3/50 | Scheda madre specifica con espansione Helios, al posto della CPU Sun 2/50. Didascalia esplicita: componente, non vista del contenitore. |
| Sun 3/60 | Workstation con dischi e nastro. Lo screenshot X11 già presente rimane una foto secondaria pertinente. |
| Sun 3/75/140/150/160/180 | Scheda CPU Carrera comune alla famiglia; didascalia del componente, senza presentarla come l’intero sistema. |
| Sun 3/80 | Workstation corretta, al posto del badge Sun-1. |
| Sun 4/3x0 | Scheda madre 4/330 del MIH/Università di Saragozza, rappresentante esplicitamente identificata della famiglia. |

Sono ritirati soltanto **sette abbinamenti automatici specifici**, identificati
per modello, pagina fonte esatta e didascalia `Scelta automatica Commons ·`.
Oltre a quelli sostituiti, vengono tolti il campus Sun dalla 3/E e il portatile
Ultra 3 dalla Ultra45. I metadati delle immagini ritirate rimangono nell’audit.
Foto manuali, altre immagini e copertine curate non sono cancellate. Le nuove
foto possono diventare copertina quando quella precedente era automatica;
una copertina scelta manualmente mantiene la precedenza.

### Crediti e condizioni

Ogni immagine conserva autore dichiarato, URL della fonte e condizioni del
singolo file. Le foto Commons hanno licenze CC o dichiarazioni di pubblico
dominio, tratte da `imageinfo`/`extmetadata`; revisioni e descrizioni sono
conservate nel pacchetto. Non si deduce l’identità del modello dal solo titolo
del file e non si assegnano foto solari/NASA o di altre workstation.

La foto SPARCstation 1 è un collegamento a
[1000bit, scheda 331](https://www.1000bit.it/scheda.asp?id=331), nel perimetro
dell’autorizzazione al recupero già fornita dall’utente. Condizioni per studio e
ricerca, diritti dei titolari; fotografo non dichiarato, nessuna licenza libera
inventata.

La foto Sun 3/110 è un collegamento all’immagine pubblica della
[scheda commerciale Recycled Goods](https://recycledgoods.com/sun-3-110-prism-16-67mhz-unix-computer-600-2051/),
con attribuzione alla fonte e **diritti riservati**. La fonte non dichiara una
licenza libera e il pacchetto non la inventa, né presenta l’utente come titolare
dei diritti. La foto è usata come riferimento visivo nel catalogo locale;
il prezzo attuale del venditore e le date di costruzione di quell’esemplare
non diventano prezzo o data di lancio. Nessuna immagine viene redistribuita
nel repository: sono memorizzati solo i collegamenti e i metadati.

## Lacune rimaste

Otto schede restano senza un’immagine pertinente associata:
**SPARCstation ELC, SPARCstation SLC, Sun 3/260/280, Sun 3/460/470/480,
Sun 3/E, Sun 4/110, Sun 4/4x0 e Ultra45**. Sono stati cercati anche archivi
esterni, ma non sono state usate foto di modelli simili o immagini da manuali
che vietano la riproduzione. I componenti fotografati sono etichettati come tali.

La Ultra45 presenta inoltre valori CPU/frequenza del vecchio dataset incoerenti
con il modello reale. Questa operazione riguarda **date e immagini**: non cambia
le specifiche tecniche. Il problema è registrato nel resoconto di ricerca, senza
presentare la scheda come completamente revisionata.

## Fonti e limiti di accesso

- [Sun-3 Product Family Configuration Guide, ottobre 1986](https://archive.org/details/bitsavers_sunsun3SunOct86_5356402):
  metadati e OCR letti; elenchi 3/110, 3/260 e 3/280. Consultato anche il manuale
  d’installazione 3/260, revisione del 10 ottobre 1986, per riscontro.
- Wikipedia: revisioni fissate nel pacchetto di **SPARCstation** e **Sun Ultra**;
  consultate anche le pagine Sun-3, Sun-4, IPC e IPX. Le pagine con titoli
  inesistenti non sono diventate fonti.
- Sun Hardware Reference e Sun3 Archive: consultazione selettiva per
  identificare famiglie, schede e contenitori, senza trasformare una specifica
  tecnica in una data di lancio.
- Commons: API ufficiali, categorie e metadati dei soli file selezionati.
- 1000bit e Recycled Goods: schede specifiche e fotografie pubbliche sopra citate.

Robots verificati, nessuno scraping massivo o API AI a pagamento. UPI e Openverse
hanno restituito 403; nessun aggiramento. Sun3zoo/Obsolyte non accessibili (503).
L’annuncio SunHELP Ultra45 e l’API WordPress hanno restituito 500: non diventano
nuove prove cronologiche. La ricerca DuckDuckGo è stata interrotta al primo
202/challenge; risultati Bing estranei scartati. Documentazione Oracle e altri
archivi sono stati consultati per identificazione, senza copiarne immagini o
attribuirgli condizioni libere. Non sono ridistribuiti PDF, ROM o fotografie.

## Applicazione locale

Dalla cartella del progetto sul Mac:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima senza scritture:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.sun_research
```

Applicazione esplicita:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.sun_research --apply
```

Ricaricare il sito. Il comando opera soltanto sulle schede esistenti; non ricrea
modelli cancellati e non ripete gli import precedenti. Produttori o modelli
ambigui sono segnalati senza abbinamenti forzati. Un errore annulla insieme date,
immagini, citazioni e audit. Ripetendo su dati già aggiornati: zero modifiche e
nessun nuovo lavoro ETL. Il piano viene ricalcolato a ogni invocazione esplicita,
così una nuova nota sul proprio database può essere presa in considerazione.

## Verifica su copia dell’archivio

[verification.json](verification.json) riporta i controlli sul clone PostgreSQL
successivo alle aggiunte NewBrain/MPF-I/Robotron:

- **24 schede Sun, tutte con un anno nativo**; 18 schede aggiornate.
- Sette date mancanti compilate, quattro vecchi anni rettificati, due sole
  commercializzazioni aggiunte senza prezzo. Tutti gli importi, le valute,
  i mercati, i tipi di prezzo e le date di fine precedenti intatti.
- Undici immagini aggiunte, sette associazioni automatiche estranee ritirate;
  restano 17 immagini su 16 modelli Sun e otto modelli senza immagine.
- **1.152 computer, 187 produttori, 1.190 configurazioni e 7.456 specifiche
  invariati**. Nessuna modifica a note, vendite, recensioni, originali ETL,
  claim preesistenti, alias o dati degli altri produttori. Foto manuali protette.
- Ripetizione: zero modifiche e nessun nuovo lavoro ETL.

Controlli eseguiti sul codice finale:

- Backend: **888 passati, due saltati perché esclusivi PostgreSQL**, sette
  subtest passati. Anche i 14 controlli mirati Sun/ruoli cronologici passano.
- PostgreSQL: **49 passati** su recupero Sun, contesti prezzi, cronologia e
  normalizzazione delle commercializzazioni.
- Frontend: **45 passati**, compilazione React riuscita; avviso Vite già
  presente sulla dimensione del bundle.
- Docker Compose: build API e health riuscite. API catalogo, confronto,
  cronologia, analisi e recupero del contesto dell’assistente verificati senza
  chiamate AI a pagamento. La qualifica `reference` permane dopo l’avvio.
- Chromium sulla build di produzione: 24 riquadri datati, SLC/Ultra45 con anni
  e prezzi corretti, foto Commons e dei due siti esterni, didascalie dei
  componenti, screenshot secondario pertinente conservato, mobile a 390 px
  senza overflow o errori JavaScript. Gli URL esatti delle nuove immagini sono
  stati serviti con i file realmente scaricati dalle fonti via HTTPS; il
  caricamento remoto diretto dal Chromium cloud non è certificato.

La verifica cloud non accede al database del Mac e non effettua merge su main.
