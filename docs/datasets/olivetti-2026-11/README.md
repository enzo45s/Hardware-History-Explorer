# Arricchimento tecnico Olivetti — 20 novembre 2026

L’HTML del catalogo fornito dall’operatore contiene **81 schede Olivetti**.
Non contiene le specifiche già presenti nelle pagine di dettaglio e non dà
accesso al database locale. La ricerca ha prodotto **513 asserzioni tecniche
per 62 modelli**; non tutte le schede risultano complete. Gli altri **19**
sono elencati in `resoconto.json` e non vengono modificati dal pacchetto.

## File

- `olivetti-specifiche.json`: file da caricare nel normale importatore.
- `modelli.txt`: gli 81 nomi effettivamente presenti nell’HTML, senza aggiunte.
- `resoconto.json`: copertura per sistema, componenti ancora mancanti,
  differenze fra formulazioni delle fonti e limiti della ricerca.
- `fonti.json`: riferimenti, revisioni Wikipedia e hash dei documenti consultati
  o dei testi OCR utilizzati. Le schede 1000bit conservano inoltre l’hash
  dell’HTML originale nell’evidenza di ogni specifica.

## Importazione sul computer con il database

Aggiorna prima il codice: questa versione riconosce il vincolo del pacchetto
`_metadata.import_mode = existing_only`, anche nel caricamento generico.

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Usa il nome del progetto Compose che contiene il tuo archivio se diverso.
Il file si trova già nella cartella scaricata da Git:
`docs/datasets/olivetti-2026-11/olivetti-specifiche.json`.

1. Apri **Amministrazione → Importazioni**.
2. Seleziona **CSV / JSON autorizzato** e carica `olivetti-specifiche.json`.
3. Conferma il diritto di utilizzare i dati e prepara l’anteprima.
4. Verifica la dicitura **Solo aggiornamenti a calcolatori esistenti**.
5. Controlla gli abbinamenti e applica le righe pronte.
6. Esamina le differenze in **Fonti e verifiche**: un valore esistente
   discordante viene mantenuto finché non accetti esplicitamente quello nuovo.

Una macchina eliminata, non trovata o con abbinamento ambiguo non viene
ricreata automaticamente, neppure ritentando il lavoro. Il file non cambia
descrizioni, commercializzazioni, prezzi, categorie e fotografie. Il numero
effettivo di specifiche aggiunte dipende da quelle già presenti nel database;
513 è il numero di asserzioni nel pacchetto, non di nuovi valori garantiti.

## Fonti e criteri

Sono state consultate le schede pubbliche 1000bit di **41 corrispondenze
esatte** e quattro varianti documentate delle famiglie M300/M380. L’operatore
aveva già dichiarato l’autorizzazione al recupero dei dati 1000bit. Sono stati
verificati robots.txt e le condizioni del sito, rispettando almeno cinque
secondi fra richieste. I manuali riservati agli iscritti non sono stati
scaricati; non sono stati aggirati login o altri controlli di accesso.

L’arricchimento utilizza anche brochure Olivetti pubblicamente consultabili,
manuali e brochure conservati su Internet Archive, la scheda CH34739 del
Centre for Computing History e revisioni specifiche delle voci Wikipedia
italiane e inglesi, recuperate tramite le API ufficiali. Non sono stati
redistribuiti manuali, scansioni o fotografie: il pacchetto contiene dati
tecnici selezionati e brevi evidenze con citazioni. Non presume una licenza
aperta per la documentazione Olivetti; le fonti Wikipedia mantengono
attribuzione e riferimento alla revisione. Nessuna chiamata OpenAI.

Le varianti M300-28, M300/30P, M380 XP5, M380-40, M380/XP9 e LSX
5025E/5040E/5050 restano configurazioni delle rispettive schede di famiglia.
La RAM massima e la capacità massima dei dischi dei server non sono presentate
come dotazioni standard. Il M290S a 16 MHz è circoscritto alla versione della
brochure del marzo 1990, senza sostituire eventuali versioni precedenti.

Alcune cautele concrete:

- La memoria a registri di Programma 101/P102/P203 e le posizioni
  alfanumeriche dell’Elea 9003 non diventano quantità di RAM convenzionale.
- Il manuale M34/M44 documenta per l’M44 lo Z8001B a **8 MHz**. Un dato
  precedente a 4 MHz viene segnalato come conflitto, senza sovrascrittura.
- Il Centre for Computing History indica **Intel 8080** per BCS 3030;
  l’8008 riportato nella voce italiana non viene importato.
- La voce italiana Echos P75 contiene una formulazione anomala su USB/internet
  nel campo RAM: i suoi dati tecnici non sono usati nel pacchetto.
- Le brochure Echos P100/P120/P133, Echos 24/44/48 e Modulo M4-75/90
  consultate non giustificano l’attribuzione delle loro dotazioni ad altri
  modelli della stessa marca con nomi simili.

I valori rimangono **pending**. La consultazione di una fonte e la selezione
di un documento primario non equivalgono a una verifica indipendente di ogni
allestimento. Le differenze nel resoconto includono anche semplici differenze
di grafia o di ambito, non necessariamente errori storici.

## Sistemi ancora senza nuovi dati tecnici

BCS 2005, BCS 2010, BCS 2020, BCS 2035, M316, PCS 386, A12,
Echos 20, Echos P75, M28 SP, M4 40 Modulo, Notebook S20, PCS 42,
PCS 44, PCX 386, Philos 20, Philos 22, Philos 33 e Philos 45 Color.
Per questi modelli i materiali consultati non permettono un’attribuzione
tecnica sufficientemente precisa. Una menzione nel catalogo, l’anno o il
nome del processore suggerito dalla sigla non vengono usati come prova.

## Verifica del pacchetto

I test automatici validano i 62 record, le citazioni e il vincolo sui soli
modelli dell’HTML. Un database temporaneo verifica applicazione, ripetizione
invariata, esclusione di un modello eliminato, conservazione di foto/testi/
categorie e gestione del conflitto 4/8 MHz dell’M44. Nessun dato è stato
importato nel database locale dell’operatore da questa chat.

Validazione del 20 novembre 2026: 814 test SQLite superati (uno saltato),
56 test mirati PostgreSQL superati e 31 test frontend superati. Avvio Compose
con health check e prova Chromium del JSON reale riusciti: caricamento
generico, vincolo sui soli esistenti, applicazione, conteggio dei sistemi
invariato e layout mobile a 320/390 px.
