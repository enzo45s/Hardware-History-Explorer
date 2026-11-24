# Benvenuto nel museo digitale

La pagina iniziale **Benvenuto** introduce il catalogo esistente, mantenendo la
barra laterale, i loghi configurati e i temi Chiaro / Fosfori verdi / Sistema.
Font e dimensioni restano gli stessi passando da un tema all’altro.

## Navigazione reale

- **Entra nel catalogo**, **Visita il catalogo** e **Il catalogo completo**
  aprono il catalogo esistente.
- **Percorri la timeline**, **Esplora la timeline** e **Inizia a esplorare**
  aprono la timeline esistente.
- **Esplora i produttori** e **Tutti i produttori** aprono l’indice aziendale;
  i nomi delle aziende aprono i rispettivi profili reali.
- Le frecce della vetrina e **Scopri la storia** aprono la scheda completa del
  computer. Tornando all’esplorazione dalla scheda aperta nella home si torna
  alla home; la barra laterale rimane sempre disponibile.
- **Confronta i sistemi** e **Interroga l’archivio** aprono confronto e assistente
  già presenti. La home non effettua chiamate AI.
- I quattro periodi aprono la timeline con gli intervalli 1950–1969, 1970–1979,
  1980–1989, dal 1990 in avanti. Questo percorso azzera ricerca, produttore e
  categoria precedenti, per esplorare l’intero intervallo. Gli altri accessi,
  come la barra laterale, conservano i filtri esistenti.

La stessa funzione di navigazione gestisce home e barra laterale. Restano
conservati sistemi selezionati per il confronto, opzioni delle configurazioni,
filtri e conferma di abbandono dei moduli amministrativi non salvati.
Una risposta tardiva all’apertura di una scheda non può riportare l’utente
indietro dopo che ha scelto un’altra sezione.

## Contenuti dal database

`GET /api/home` restituisce conteggi aggregati e al massimo tre sistemi.
Non carica l’intero catalogo nel browser, non applica pacchetti di dati e
non crea contenuti dimostrativi. Le analisi complete vengono richieste solo
nelle sezioni che le mostrano.

La selezione editoriale preferisce Commodore 64, Programma 101 e IBM PC 5150,
quando marca e modello corrispondono a record effettivamente presenti. Non
usa ID fissi, non accorpa modelli e non introduce regole di deduplicazione.
Quando un sistema manca o viene cancellato, il posto è occupato da un altro
record dell’archivio: prima quelli con foto, poi per prima commercializzazione
e ID. Le tre schede sono distinte; gli archivi piccoli non vengono riempiti
con dati inventati. Le schede sotto la vetrina sono ordinate per anno.

Conteggi e sistemi si ricaricano dopo le modifiche amministrative e quando
si torna alla home. Un archivio vuoto mostra un invito a iniziare; errori
recuperabili mostrano **Riprova** e mantengono disponibile la navigazione.

## Fotografie, testi e marchio

La home usa la copertina scelta nel database, con lo stesso criterio del
catalogo, e i suoi metadati. Non ricerca, scarica sul server o sostituisce foto.
La vetrina conserva autore, condizioni, collegamenti alla fonte e alla licenza
quando disponibili. Le immagini rimangono nei colori originali su fondo neutro;
un URL non raggiungibile mostra il segnaposto esistente.

Le brevi descrizioni provengono dalle schede e sono limitate a tre righe;
il testo completo rimane nella scheda. Le attribuzioni Wikipedia conservate
nell’archivio vengono esposte insieme ai relativi collegamenti e alla licenza.
Non vengono generate nuove descrizioni storiche.

Il componente del logo e i file locali `frontend/public/branding/logo-light.png`
e `logo-dark.png` continuano a funzionare come prima, compreso il segnaposto
quando un file manca. Nessuna nuova immagine o carattere viene incorporato nel
repository per questa pagina.

## Aggiornamento locale

Sul branch `feat/historical-data-import`, dalla cartella del progetto:

```bash
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Ricaricare poi HHE nel browser. Non serve eseguire importatori, ripristinare il
database o cancellare i volumi. La home usa soltanto dati già disponibili e
non introduce colonne, tabelle o migrazioni. La build API è necessaria per il
nuovo endpoint, oltre a quella del frontend. Il database del Mac non viene
raggiunto o aggiornato dall’ambiente cloud.

## Verifiche

- Suite backend SQLite: **886 test passati**, due test specifici PostgreSQL
  saltati. I quattro test home coprono archivio vuoto/piccolo, omonimi, ID
  reali, date parziali, copertine curate, attribuzioni e modelli cancellati.
- **49 test PostgreSQL** passati, inclusi home, API, profili produttori,
  catalogo/migrazioni e i due controlli esclusivi PostgreSQL.
- **45 test frontend** passati; compilazione React e build/avvio Docker di
  API, frontend e PostgreSQL riusciti.
- `npm run test:browser:home`: pagina iniziale, conteggi dal vero endpoint,
  tutti i collegamenti, schede e produttori, periodi, filtri e confronto,
  risposta tardiva delle schede, conferma dei moduli non salvati,
  errore/riprova e archivio vuoto. Layout 320/390/768/1440 px nei due temi,
  font invariati, nessun errore JavaScript.
- Controllo su copia PostgreSQL dopo il supplemento produttori: **1.152
  computer e 187 produttori**. Confronto di conteggi e impronte su tutte le
  **37 tabelle**: nessuna modifica ai dati dopo l’avvio e l’uso della home.

[Resoconto e impronte delle tabelle](HOME_VERIFICATION.json).

Il test browser automatico usa immagini SVG dichiaratamente sintetiche per
isolare la navigazione dalla rete. Le verifiche visive separate usano i file
originali scaricati dagli esatti URL delle copertine, serviti agli stessi URL,
e copie dei font correnti; non certificano il recupero diretto delle immagini
esterne dal Chromium cloud. Rimangono gli avvisi preesistenti sulla dimensione
del bundle Vite e sulla deprecazione Starlette/httpx nei test.

Il flusso browser home è incluso nella CI prima dei controlli delle importazioni.
