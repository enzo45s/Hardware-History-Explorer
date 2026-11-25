# Prezzi da un Excel di ricerca

È disponibile la fonte **Prezzi storici (Excel / CSV / JSON)**. Puoi caricare
direttamente l'Excel ricevuto, senza trascrivere prezzi o numeri delle schede.
Non sono richieste nuove dipendenze, migrazioni o chiavi API.

## Aggiornamento e caricamento su Windows

```powershell
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d
```

Conserva il nome del progetto Compose che contiene il tuo database. Poi:

1. Premi Ctrl+F5 e apri **Amministrazione → Importazioni**.
2. Scegli **Prezzi storici (Excel / CSV / JSON)**.
3. Seleziona `prezzi_lancio_computer_storici_ricerca_estesa.xlsx` e conferma il
   diritto di importare la ricerca e conservarne i riferimenti.
4. Premi **Prepara anteprima dal file**. Il riepilogo mostra prezzi, note,
   righe senza importo, correzioni delle colonne e righe invalide.
5. Controlla gli abbinamenti, poi **Applica le righe pronte all'archivio**.
   Le righe senza un sistema esistente vengono escluse; le ambiguità richiedono
   una scelta esplicita. Nessun nuovo computer viene creato.
6. Usa **Fonti e verifiche** per esaminare asserzioni e conflitti. Prezzi e
   metadati discordanti conservano il valore già archiviato.

Gli ID dell'Excel sono ordinali della ricerca, **non ID del database**.
L'abbinamento usa insieme produttore e modello, con normalizzazione dei
prefissi e compatibilità con i nomi dell'elenco esportato precedentemente.
I nomi del catalogo restano invariati. Anche le collisioni tra abbreviazioni
vengono segnalate, senza scegliere automaticamente una delle schede.

## Interpretazione dei dati

L'importatore legge solo il foglio **Prezzi per modello** e le sue tredici
colonne. I fogli di ricerca, riepilogo e mancanti non vengono sommati: nel file
ricevuto i risultati delle quattro ricerche sono già presenti nel foglio
principale. Per gli aggiornamenti futuri, riporta lì i nuovi risultati.

| Stato nel foglio | Trattamento |
| --- | --- |
| Prezzo con fonte | Importo, valuta e mercato; tipo `prezzo riportato` |
| Prezzo di/al lancio verificato, documentato, confermato o con fonte | Stesso trattamento numerico, senza attribuire una verifica umana nell'app |
| Listino d'epoca, non lancio | Importo separatamente qualificato come `listino successivo` |
| Prezzo di famiglia/variante diversa, solo indicativo, base senza accessorio o indizio | Solo nota contestuale, senza prezzo numerico assegnato al modello |
| Senza importo | Riga esclusa dal lotto |

**Anno lancio** viene conservato come dato dichiarato nel foglio, non usato per
impostare `release_date`: l'anno può riferirsi a un listino successivo o a una
configurazione diversa. Non viene inventata una data di prezzo o di lancio.
Le date già archiviate restano conservate. Non si convertono valute, imposte
o prezzi in moneta corrente e non si estraggono automaticamente altre cifre
dalla colonna delle varianti.

Nel catalogo una [sintesi delle commercializzazioni](RELEASE_SUMMARIES.md)
puo affiancare anno e prezzo quando l'abbinamento e univoco, mostrando una sola
fonte e privilegiando quella del prezzo. Le registrazioni originali, l'ambito
geografico della data e il
prezzo senza data restano invariati; i listini successivi non ereditano l'anno
di lancio.

Configurazione, monitor/accessori, imposte, altri listini, affidabilità dichiarata
e note restano in **Contesto del prezzo**, con fonte e riferimento alla riga.
Nelle schede e nelle note fornite all'assistente viene omesso il vecchio prefisso
**Ricerca da verificare.** Questo vale anche per le note già importate, senza
ricaricare l'Excel. Testi originali nell'archivio, fonti e stati di verifica
restano invariati; ripetere l'importazione non duplica le note.
Le colonne URL/affidabilità/varianti vengono riallineate soltanto per il formato
inequivocabile riscontrato nel file; casi ambigui restano invalidi.

La presenza di un URL o dell'etichetta **Alta** non verifica la cifra. Ogni
asserzione nasce `pending`, senza consultazione automatica della pagina.
Le citazioni sono di tipo `research_reference` e non ricevono automaticamente
una data di consultazione. Gli URL non vengono aperti dal parser.

## Recupero automatico dei prezzi già presenti nelle note

Alcuni Excel successivi usano la dicitura **Prezzo di lancio verificato**:
il vecchio parser non la riconosceva e conservava la riga soltanto in
**Contesto del prezzo**. Ora le nuove importazioni riconoscono queste etichette.
All'avvio dell'API viene inoltre eseguito un recupero dei dati già archiviati;
i JSON canonici contenenti vecchie note Excel vengono recuperati anche subito
dopo l'applicazione. Non occorre ricaricare l'Excel o svuotare il catalogo.

Il recupero usa i campi originali della riga conservati nell'audit JSON:
**Prezzo al lancio**, **Valuta**, **Mercato / Paese** e **Stato ricerca**.
Non cerca numeri nel testo libero. Per Enterprise Sixty Four, i campi indicano
249 GBP e Regno Unito: vengono aggiunti a Commercializzazione con la stessa
fonte. Il Regno Unito viene presentato sotto Europa, secondo il raggruppamento
geografico già previsto. Il riferimento a circa £180 nel giugno 1985 rimane
una nota; la cautela sul prezzo annunciato e sulla data di consegna resta
conservata. Nessuna data di consegna viene ricavata da quelle frasi o dall'anno
del foglio. L'eventuale anno affiancato al prezzo è il contesto del modello
già presente nel catalogo.

Il recupero conserva note, file originali, fonti e precedenti asserzioni. Genera
un nuovo lavoro d'importazione `recupero-prezzi-note.json`, in lotti di massimo
100 righe, con riferimenti alle asserzioni originarie. Riavvii concorrenti o
successivi non duplicano il recupero. Le operazioni archiviate dopo lo
svuotamento non ripristinano dati eliminati.

Un dato rifiutato, stimato, modificato manualmente, privo di fonte o dei campi
originali non viene promosso automaticamente. Restano solo note anche gli
importi di famiglia/variante diversa, le stime e i valori parziali. Un prezzo
già presente e differente rimane conservato: viene registrata una proposta
in conflitto. La dicitura «verificato» dell'Excel resta una dichiarazione della
ricerca, non una verifica registrata nell'app; le nuove asserzioni sono `pending`.

In **Amministrazione → Importazioni → Prezzi storici** compare
**Controlla prezzi recuperati** per aprire il resoconto e le consuete **Fonti e
verifiche**. Il riepilogo è disponibile anche con
`GET /api/admin/imports/price-context-recovery`. Non vengono introdotte nuove
tabelle o dipendenze, né richieste a siti o servizi AI.

L'Excel originale viene conservato integralmente in Base64 nell'audit esistente,
con SHA-256 e riga del foglio per ogni record. **Scarica originale conservato**
restituisce gli stessi byte in un `.xlsx`. Formule, macro e collegamenti esterni
non vengono eseguiti. Archivi troppo grandi e XML non ammesso sono rifiutati.
Limiti: 8 MB compressi, 64 MB decompressi, 10.000 righe lette e 1.000 record
con prezzo o indicazioni da importare. Il file attuale rientra nei limiti.

## Preparazione offline facoltativa

Con le dipendenze backend installate puoi ottenere anche JSON canonico e report:

```bash
python tools/prepare_historical_prices.py ricerca.xlsx --output prezzi.json --report rapporto.json
```

Questo comando non scrive nel database e non contatta i siti. Il JSON si può
caricare scegliendo la stessa fonte prezzi; rimane attiva la protezione che
consente solo aggiornamenti. L'originale conservato sarà quello caricato.

## Verifica del file ricevuto il 15 novembre 2026

SHA-256: `1735b5ac89d7ae33bb7448873f385446a19f05dc581c6a1c295f1df0df29e534`.

- 1.105 sistemi nel foglio principale.
- 569 righe dichiarate **Prezzo con fonte** e 22 listini successivi: 591 prezzi numerici.
- 12 indicazioni trattate solo come note e 502 righe senza importo escluse.
- 19 disallineamenti delle colonne corretti; nessuna riga invalida.
- I quattro fogli delle ricerche successive coincidono con le rispettive
  righe del foglio principale; non vengono duplicati.

Sul corpus PostgreSQL isolato, tutte le 603 righe trovano un sistema. La prova
applica 603 aggiornamenti e aggiunge 591 righe prezzo, poi ripete l'importazione:
603 invariati, nessun duplicato di prezzi o note. Confrontati gli hash delle
tabelle computer, produttori, categorie, configurazioni, specifiche, immagini,
vendite e recensioni: invariati. Le 3.594 nuove asserzioni sono tutte pending.
Il totale resta 1.106, comprendente 1.105 modelli del dataset e una fixture
precedente estranea al lotto. La transazione viene annullata al termine:
nessun cambiamento persistente nel catalogo di prova e nessun accesso al
database Windows dell'operatore.

Sono passati 394 test PostgreSQL, 393 SQLite con uno specifico PostgreSQL
saltato e 27 frontend. Verificati anche parsing, rotazioni delle colonne,
formule rifiutate, originali e retry, ID ordinali, alias Apple/Data General,
ambiguità, conservazione dei prezzi discordanti, contesto e replay. Build React
e Docker riuscite; nel browser su frontend compilato, anteprima Excel,
download dell'originale, applicazione, riapplicazione e layout 320/390 px.
Ripetuti i 27 test specifici dei prezzi su entrambi i database dopo l'ultimo
controllo sui numeri troppo piccoli per essere rappresentati senza diventare zero.
La nuova suite browser è inclusa in CI. L'elenco testuale esportato nel
repository conserva ora anche gli slash delle sigle Apple; l'Excel già
ricevuto continua ad abbinarsi grazie alla compatibilità con il vecchio elenco.

I tentativi di accesso a Wikipedia, Computing History e World Radio History
dal cloud sono bloccati dal proxy. Non è stata verificata la veridicità dei
prezzi sulle pagine: tutti i valori restano riferimenti di ricerca da controllare.
L'Excel ricevuto non viene aggiunto al repository; i test usano prezzi sintetici.
