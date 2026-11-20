# Arricchire automaticamente tutto il catalogo da 1000bit

Non servono HTML salvati o URL inseriti per ogni computer. La sessione visita
l'indice pubblico e i collegamenti alle schede, abbinandole al catalogo HHE.
Il permesso di recupero è già stato dichiarato dall'operatore.

## Avvio su Windows

Sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
```

L'esempio usa il progetto attivo `hhe-import-test` diagnosticato su Windows;
se la tua istanza ha un altro nome, conserva quello. Non svuotare il database né ricaricare
i lotti originali. Premi Ctrl+F5, poi:

1. **Amministrazione → Importazioni → Fonte dati → 1000bit**.
2. Nel pannello **Arricchisci tutto il catalogo da 1000bit**, premi
   **Avvia arricchimento di tutto il catalogo**.
3. Lascia aperta questa sezione: segue i collegamenti e applica automaticamente
   i dati delle corrispondenze univoche. Non devi confermare ogni sistema.

Il caricamento di file o singoli URL resta sotto **Importa singole schede o
file (facoltativo)**, utile per correzioni ed eccezioni.

## Pausa, ripresa e durata

La raccolta può durare ore. Una richiesta alla volta, con almeno cinque
secondi di pausa; eventuali Crawl-delay o Request-rate maggiori prevalgono.
La scadenza è controllata anche dal backend, non soltanto dal browser.

**Metti in pausa la raccolta** ferma i passi successivi; una richiesta già
partita può terminare. Uscendo dal pannello o chiudendo il browser, il resto
resta in coda. **Riprendi arricchimento del catalogo** continua anche dopo
un riavvio di Docker, senza riscaricare le pagine già elaborate.

Non c'è un worker che continui a browser chiuso. Un'interruzione durante una
richiesta può richiedere fino a tre minuti per la scadenza della prenotazione
prima della ripresa. Il sistema evita richieste concorrenti dalla stessa coda.

Un errore di rete o HTTP 429/503 mette in pausa e conserva la pagina corrente.
Il tempo Retry-After viene rispettato anche premendo subito Riprendi. La pagina
non è considerata elaborata. **Salta la pagina corrente** è un'azione esplicita
per una pagina problematica; **Termina questa sessione** conserva dati e audit,
liberando la possibilità di avviare una nuova visita.

Il limite predefinito è **20.000 richieste**, modificabile fino a 50.000.
Se viene raggiunto, aumenta il limite e riprendi la stessa coda. Non viene
segnalata una copertura conclusa e i sistemi ancora da cercare restano in
attesa. Lo spazio della coda è limitato a 50.000 URL distinti.

## Abbinamenti e dati conservati

La sessione fotografa tutti i sistemi presenti al suo avvio, senza il limite
di paginazione del catalogo. I sistemi aggiunti successivamente richiedono
una nuova sessione. Si riusano gli alias già definiti per produttori e modelli
e le identità esterne approvate. Non si usano somiglianze fuzzy per aggiornare
un modello automaticamente.

- Corrispondenza univoca: aggiornamento automatico del solo sistema esistente.
- Più corrispondenze: anteprima conservata in **Corrispondenze da controllare**;
  la visita continua sugli altri modelli. Puoi aprirla, scegliere la scheda
  corretta e applicarla con i controlli già esistenti.
- Nessun abbinamento: nessun nuovo calcolatore viene creato.
- Valori differenti: il dato attuale resta conservato e la nuova proposta
  diventa un conflitto. La raccolta continua senza richiedere conferme per
  ogni conflitto. Per esaminarli usa **Controlla fonti e dati** sulle pagine
  elaborate o gli ID delle importazioni nel resoconto completo.

Per 1000bit, marca e modello vengono confrontati insieme dopo una
normalizzazione deterministica. Si ignorano le annotazioni geografiche
riconosciute della marca, gli spazi/trattini equivalenti nel modello e il
prefisso della marca già contenuto nel nome. Gli alias espliciti già presenti
restano validi. Per esempio, la scheda
[935](https://www.1000bit.it/scheda.asp?id=935), indicata dall'operatore come
**Fujitsu (Japan) · FM 11 EX**, corrisponde a **Fujitsu · FM-11 EX**.
La regola vale anche per le importazioni singole con fonte 1000bit.

Numeri, sigle tecniche, `+`, `/`, punti e annotazioni non geografiche restano
significativi: `FM-11 EX` non corrisponde a `FM-11 AD` né alla sola famiglia
`FM-11`. Marche differenti e divisioni non riconosciute non vengono assimilate.
Se due schede del catalogo condividono la chiave normalizzata, entrambe vengono
proposte per revisione, anche se una delle scritture coincide esattamente.
Le altre fonti mantengono le proprie regole precedenti.

Il nome del modello e il produttore HHE restano conservati; non viene creato
un produttore duplicato soltanto perché la fonte aggiunge il paese. I nomi
originali della fonte rimangono nei dati grezzi e normalizzati, senza conflitti
artificiali per sole differenze di formattazione.

### Recuperare le pagine già non abbinate

Dopo l'aggiornamento, ricarica con Ctrl+F5 e riapri la sezione 1000bit.
Metti in pausa l'eventuale visita in corso e attendi che termini la richiesta
già partita, poi premi **Riprova le pagine non abbinate** e
**Riprendi arricchimento del catalogo**.

Vengono rimessi in coda soltanto gli URL con esito `unmatched`, inclusi quelli
di una visita terminata prima della correzione. Le pagine vengono recuperate
nuovamente rispettando robots.txt, pause e limite di richieste. Indici, pagine
già riuscite, snapshot del catalogo e decisioni umane restano conservati.
Non occorre ricominciare tutto il catalogo, fornire HTML o svuotare l'archivio.
Se serve, aumenta il limite richieste nel pannello prima di ritentare.

Un'altra sessione attiva, una richiesta ancora in corso o una sessione
archiviata/annullata impediscono la riattivazione. Dopo un annullamento si può
avviare una nuova visita incrementale con il pulsante normale. I casi con più
candidati restano in **Corrispondenze da controllare**.

Le nuove pagine senza corrispondenza conservano anche l'HTML originale e un
motivo leggibile con marca e modello. Non essere abbinata significa che manca
una corrispondenza sicura nello snapshot della sessione, non che la macchina
non esista su 1000bit. La nuova etichetta distingue questo esito dall'ambiguità.

Descrizioni esistenti, categorie, fotografie e prezzi non vengono cancellati.
Restano le regole dell'[adattatore 1000bit](1000BIT.md): date di produzione
separate dalle date commerciali, opzioni CPU nelle note, unità RAM ambigue
conservate e nessun prezzo inventato. Nessuna verifica storica è automatica.

## Copertura e resoconto

Il pannello mostra richieste, coda, sistemi aggiornati/invariati, corrispondenze
da controllare, conflitti e percorsi esclusi. **Scarica il resoconto completo**
esporta tutti i sistemi della sessione e gli esiti delle pagine, non solo
le prime 25 righe di esempio. Le importazioni abbinate conservano l'HTML
originale completo, la fonte e gli estratti per ogni dato tecnico.

**Non abbinato nelle pagine visitate** non significa che il computer non esista
su 1000bit. Può dipendere da nomi diversi, copertura della fonte o parti del
sito non raggiungibili con i collegamenti letti. Non si promette che 1000bit
contenga tutti i modelli di HHE o tutti i prezzi mancanti.

La visita parte da `database.asp?by=S_NOM` e dalla scheda nota 282: entrambi gli
indirizzi sono attestati nell'HTML fornito dall'operatore. Segue solo link
HTML a `database.asp`, `database2.asp`, `database4.asp` e `scheda.asp` sul sito
1000bit, deduplicando pagine e ordinamenti. Non enumera numeri di scheda,
compila moduli, esegue JavaScript, visita account, scarica media o segue siti
esterni. Parti accessibili soltanto tramite moduli/JavaScript richiedono una
successiva verifica del formato. Robots è letto prima delle pagine del sito.

## Persistenza e migrazione

Tre tabelle additive: `bit1000_bulk_jobs`, `bit1000_bulk_targets`,
`bit1000_bulk_pages`. L'avvio dell'API le crea senza modificare tabelle o dati
esistenti; la migrazione ripetibile `migrations.historical_imports` le include.
Ogni applicazione e avanzamento della pagina sono una transazione atomica:
un'interruzione non lascia dati importati a metà. Uno svuotamento dell'archivio
archivia la sessione e invalida la richiesta in corso, senza ricreare modelli.

## Verifiche e limiti dell'ambiente cloud

La navigazione è verificata con un sito HTTP sintetico: avvio singolo,
indici/collegamenti, pause, riapertura del browser, associazioni, replay, errori,
ambiguità, limiti, concorrenza e svuotamento durante una richiesta. Un catalogo
isolato da **1.105 sistemi** verifica che vengano inclusi anche gli ID oltre
la prima pagina; i due modelli con schede nel sito sintetico sono aggiornati,
gli altri segnalati, e il totale resta 1.105.

Il browser è provato a 320/390 px e la CI dispone di `test:browser:bulk` con
backend temporaneo isolato, senza chiamate al sito reale. Il sito sintetico è
solo in `backend/tests/browser_bulk_app.py`, escluso dall'immagine di produzione.

Il proxy cloud continua a bloccare 1000bit. La visita integrale del sito reale
non è stata eseguita: deve partire dal computer dell'operatore, dove il sito
è raggiungibile. Nessun dato storico nuovo è stato recuperato automaticamente
da 1000bit in questa fase. La precedente prova sul file reale Amiga 1200 è
documentata separatamente nella guida dell'adattatore.

Risultati finali: **268 test SQLite passati** e uno specifico PostgreSQL
saltato; **269 test PostgreSQL passati**, inclusi 20 casi per la raccolta
automatica; **25 test frontend passati**. Build React e avvio Compose riusciti.
Superate le prove browser di importazione singola, svuotamento e raccolta
automatica, anche sulla versione compilata del frontend. Resta l'avviso
preesistente Vite sul bundle oltre 500 kB.

La prova sul corpus PostgreSQL da 1.105 sistemi crea correttamente lo snapshot
completo; il primo accesso robots è rifiutato dal proxy e mette in pausa la
sessione con 1.105 sistemi ancora pending, senza falsi esiti «non trovato».
Il totale e le analisi del catalogo restano identici prima e dopo. Nessun
database Windows dell'operatore è stato raggiunto.

### Correzione degli abbinamenti marca-modello

Caso segnalato dall'operatore: URL `scheda.asp?id=935`, Nome `FM 11 EX`,
Costruttore `Fujitsu (Japan)`. La fixture dei test ricostruisce soltanto questi
campi e l'URL: non è un HTML scaricato e non contiene specifiche o prezzi
aggiunti. Il matcher precedente falliva sia per il paese nella marca sia
per il trattino nel nome HHE `FM-11 EX`.

Suite complete: 367 test PostgreSQL superati, 366 SQLite superati e uno
specifico PG saltato, 27 frontend; build React e Compose riusciti. Dopo
l'ultima protezione sulle collisioni aggiunte al catalogo durante una sessione,
ripetuti tutti i 48 test di matching/raccolta sia su SQLite sia su PostgreSQL.
Le prove includono upload, raccolta automatica, nomi originali conservati,
assenza di produttori duplicati, varianti tecniche distinte, ambiguità e
riattivazione limitata alle pagine non abbinate delle sessioni precedenti.

Analizzate le chiavi dei 1.105 modelli del dataset di base dopo la normalizzazione
regionale: zero collisioni. Nel catalogo PostgreSQL isolato, una verifica
in sola lettura trova un unico candidato Fujitsu FM-11 EX per i due valori
della scheda 935. Questo prova l'abbinamento sul catalogo, senza recuperare
o importare altre informazioni storiche della pagina.

Browser Chromium sul frontend compilato e sito sintetico: visita iniziale,
pausa/ricaricamento/ripresa, nuova sessione preesistente con il Fujitsu non
abbinato, comando di riprova, un solo URL nuovamente recuperato e risultati
precedenti conservati. Nome HHE e produttore rimangono gli stessi, la citazione
935 è associata senza nuovi calcolatori. Layout a 320/390 px e nessun errore
JavaScript. La suite browser già inclusa in CI copre anche questa regressione.

API: `POST /api/admin/1000bit/bulk/{id}/retry-unmatched`, con JSON `{}` oppure
`{"max_requests": 20000}`, rimette in pausa la sessione e ricoda gli scarti.
Segue il normale `/resume`. Nessuna nuova tabella o migrazione. Il proxy cloud
continua a impedire l'accesso live a 1000bit, compreso robots.txt; nessuna visita
reale completa o recupero di nuovi dati tecnici viene dichiarato.
