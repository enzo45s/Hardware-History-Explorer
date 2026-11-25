# Revisione NEC, NeXT, Kaypro, SGI, Daewoo, Fenner e H/H

Ricerca del **25 novembre 2026**. Il pacchetto offline contiene **103 schede**:
42 NEC PC-88/PC-98 e derivati, 15 Daewoo, 15 Silicon Graphics, 16 Kaypro/NLS,
8 NeXT, 4 Fenner, H/H Tiger e i due nuovi sistemi richiesti:
**Processor Technology Sol-20** e **Video Technology Laser 500**.

Non viene eseguito alcun recupero di rete durante l’importazione. I dati sono
scritti nelle tabelle principali, con fonti per le specifiche e asserzioni
`pending`; non si tratta di sostituzioni nel frontend. Catalogo, timeline,
confronti, analisi e contesto dell’assistente utilizzano gli stessi record.

## Applicazione sul database locale

Dalla cartella del progetto, sullo stesso branch aggiornato:

```bash
git pull
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima di sola lettura:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.catalog_research
```

Applicazione esplicita:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.catalog_research --apply
```

Il codice non applica automaticamente questo supplemento all’avvio. Non occorre
reimportare un dump, svuotare l’archivio o caricare il JSON nel modulo generico.
Usare il comando dedicato: comprende rettifiche, alias, immagini e tutele che
il caricamento generico del solo elenco `records` non applica.

L’operazione è transazionale. Il secondo avvio restituisce `already_applied`
senza duplicare righe; non ricrea una scheda eliminata dopo l’applicazione.
Le schede esistenti assenti o ambigue vengono segnalate e non ricreate.
Soltanto Sol-20 e Laser 500 possono essere creati. I nomi noti del produttore
VTech/Video Technology vengono riconosciuti per questo supplemento, senza
accorpare le aziende presenti nell’archivio.

## Fonti e scelte editoriali

| Fonte | Uso effettivo | Limiti |
|---|---|---|
| MSX Resource Center | Schede dei singoli Daewoo e Fenner: RAM, VRAM, controller, audio, tastiera, supporti e contesto | Ignorata la sezione sull’emulazione. RAM e VRAM non vengono confuse. Le foto senza condizioni documentate non sono copiate. |
| PC-9800.net | Trascrizioni di schede NEC per modello e allestimento | Conservati i suffissi. Segnalati i valori discordanti di alcune versioni V20/Xa16 e la cronologia HANDY98. Nessuna estensione di una dotazione a tutta la famiglia. |
| SGIstuff | CPU, bus, memoria e opzioni delle singole generazioni SGI | Non vengono assegnati i limiti dell’Octane più recente alla prima scheda madre. Per Indy si conserva la scheda generale e le tre configurazioni CPU esistenti. La fonte HTTP è pubblicamente leggibile; la versione HTTPS non forniva le pagine utili. |
| retrocmp | Revisioni Kaypro, differenze 4X/4+88 e unità disco | Il 4X non viene assimilato alla versione con processore DOS aggiuntivo. Omni II richiede una fonte autonoma. |
| 1000bit | Schede tecniche, immagini o illustrazioni specifiche e dati dei due nuovi sistemi | Riutilizzo dei dati già autorizzato dall’utente. Le immagini restano collegamenti esterni per studio/ricerca locale, secondo il footer dell’archivio; nessuna licenza libera o autorizzazione generale alla pubblicazione viene inventata. |
| Wikipedia | Tabelle PC-8800, differenze NeXT e NeXTdimension, H/H Tiger, Sol-20 e modi video MSX | Revisioni fissate tramite `oldid`. Sintesi italiane, citazioni e attribuzione CC BY-SA conservate per i testi che utilizzano queste voci. |
| Wikimedia Commons | Immagini identificate per nome e descrizione del soggetto | Autore, pagina del file e licenza conservati; risultati non pertinenti scartati. La posizione nella ricerca non è un criterio di accettazione. |

Sono state consultate le regole robots prima delle raccolte mirate; per
1000bit esiste già l’autorizzazione dell’utente. Non è stato utilizzato
l’archivio Jurassic/SGI Techpubs, che vietava l’accesso a ChatGPT-User/GPTBot.
Nessuna API a pagamento e nessuna generazione AI di dati mancanti.

Inventario delle schede: [MODELS.md](MODELS.md). Citazioni, immagini,
attribuzioni, condizioni e lacune: [sources-and-images.json](sources-and-images.json).

## Correzioni e conservazione

- **NeXTcube**: corretto il vecchio 68030 nel 68040 documentato; le frequenze dei
  modelli Turbo sono distinte. L’allestimento prima chiamato
  **NeXTcube Turbo Color** diventa **NeXTcube Turbo con NeXTdimension**.
- **Kaypro PC** sostituisce il nome poco riconoscibile **PC**. Entrambe le
  rinomine mantengono ID, collegamenti e vecchio nome come alias.
- Per MSX, Kaypro e Tiger vengono rettificati o rimossi soltanto gli esatti
  raster legacy non verificati, sostituendoli con modi grafici o testo
  documentati. Il Tiger conserva separati CPU principale, processore I/O,
  memoria RAM e memoria video.
- PC-8801FA, MA, MA2, MC, MH e VA non ricevono tutti la stessa memoria o lo stesso
  audio. Per PC-9801F si distinguono i 128 KB di F1/F2 dai 256 KB del successivo
  F3; il Ra20 utilizza un **Pentium Pro**, non un Pentium generico.
- Le rettifiche richiedono una corrispondenza esatta con i valori precedenti,
  fonti esclusivamente legacy e assenza di verifiche. Se le asserzioni legacy
  conservate non corrispondono più alla quantità corrente, il valore è protetto:
  una modifica manuale non perde questa tutela solo perché conserva una vecchia
  citazione bibliografica. I valori ritirati rimangono nell’audit.
- Descrizioni curate, fonti manuali, copertine e tutte le commercializzazioni
  esistenti sono conservate. Le immagini selezionate si aggiungono alla galleria;
  diventano copertina soltanto quando non ne esiste già una. Lo stesso file
  Commons non viene aggiunto di nuovo solo perché cambia la risoluzione dell’URL.
- Il Sol-20 riporta la RAM del kit da 2 KB come allestimento documentato, con
  espansioni separate. Non viene inventata una dotazione unica per tutte le
  macchine assemblate. Non sono importati prezzi derivati da intervalli o da
  allestimenti non univoci.

## Esito e lacune

La verifica su una copia da **1.152 computer** ha aggiornato **101 schede** e
creato soltanto i **due nuovi modelli**, arrivando a **1.154**. Sono state
inserite o migliorate **47 descrizioni**, conservate **30 descrizioni curate**,
aggiunte **31 immagini** da 32 proposte, eseguite **130 rettifiche tecniche**
e ritirate **15 rappresentazioni legacy** non documentate.

Il pacchetto propone **514 asserzioni tecniche**. La normalizzazione fisica
preesistente consolida le rappresentazioni equivalenti: il saldo effettivo è
**+272 righe Specification**. I contatori del CLI distinguono righe allocate,
righe nuove rimaste e righe consolidate; non sono il numero di computer.

Restano **20 discordanze** di memoria conservate come conflitti: comprendono
quantità già curate e differenze di rappresentazione KB/KiB. Non vengono
risolte reinterpretando silenziosamente le unità. Non ci sono duplicazioni del
campo RAM principale per aggirare il conflitto.

Per **DPC-200E**, **Omni II Logic Analyzer** e il suffisso **PC-H98S model 8/U8**
le fonti consultate non consentono ancora una scheda tecnica completa e certa.
Anche alcune immagini delle varianti NEC, NeXT e MSX rimangono mancanti.
Le denominazioni commerciali valide sono conservate: rinominare una variante
in un modello più famoso non renderebbe attendibile una foto o una specifica.
Le immagini Personal IRIS che illustrano la famiglia riportano esplicitamente
che il preciso allestimento fotografato non è identificato.

Il resoconto [verification.json](verification.json) documenta anche:
nessuna modifica agli altri **1.051 computer**, conservazione delle **98
asserzioni già verificate**, di tutte le commercializzazioni/vendite/recensioni
esistenti e delle quattro configurazioni Indy; ripetizione senza modifiche
alle tabelle ORM e recupero dei due nuovi sistemi nel contesto dell’assistente.

Questi numeri descrivono la copia verificata nel cloud. Sul Mac i risultati
possono differire se hai già aggiunto foto, modificato dati o eliminato schede;
il database locale viene aggiornato soltanto dal comando `--apply`.

## Verifiche eseguite

- Suite generale backend: **902 test riusciti, 2 saltati**. Dopo le ultime tutele:
  **15 test mirati su SQLite** e **35 su PostgreSQL**, includendo gli importatori
  DEC e microcomputer già presenti.
- Preview senza scritture, conservazione di dati/fonti manuali e verificati,
  alias, schede CPU multiple, assenza di duplicati, rollback anticipato e finale,
  deduplicazione dello stesso file Commons anche con URL di risoluzione diversi.
- API reali per cinque schede, confronto, analisi e recupero del contesto AI;
  navigazione browser in sola lettura per Sol-20, Laser 500 e H/H Tiger.
- Docker Compose con immagini ricostruite e servizi database/API/web sani.
- **32 URL di immagini** scaricati e decodificati, con controllo visivo delle
  proposte. Tre candidati sbagliati sono stati scartati; due risposte Commons
  429 temporanee sono state ritentate più tardi con esito positivo.

Le 71 righe dell’inventario prive di una nuova immagine non sono necessariamente
schede senza foto: alcune ne avevano già una da conservare. Il resoconto riporta
separatamente l’elenco effettivo `remaining_without_image` della copia verificata.
Non è stato modificato né raggiunto il database del Mac durante queste prove.
