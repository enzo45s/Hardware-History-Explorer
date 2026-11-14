# Fotografie automatiche Wikimedia Commons

## Uso locale

Sul branch `feat/historical-data-import`, aggiorna il progetto e ricostruisci
la tua istanza Compose, mantenendo l'eventuale nome progetto `-p` già utilizzato:

```powershell
git pull --ff-only
docker compose up --build -d
```

Apri **Amministrazione → Foto automatiche → Avvia ricerca automatica**.
Non occorre confermare ogni immagine: viene associato automaticamente il primo
risultato utilizzabile nell'ordine di rilevanza restituito da Commons.
Le foto compaiono anche nelle copertine del catalogo, nella timeline e nei
confronti. La ricerca usa **marca - modello**, per esempio
`Apple - Macintosh 128K` o `IBM - PC 5150`. I prefissi della marca già presenti
nel modello vengono rimossi tramite corrispondenze esplicite, comprese le
forme note `Apple Computer`, IBM e Commodore, senza cambiare i nomi nel catalogo.
La stessa stringa iniziale viene usata da **Gestisci fotografie** nella scheda.

Il normale **Avvia ricerca automatica** contiene solo le schede senza foto in galleria e senza
copertina nel precedente campo `image_url`. Le foto esistenti non vengono
sostituite. Anche una foto inserita manualmente durante la ricerca viene
ricontrollata prima del salvataggio e conservata.

### Ricominciare su tutto il catalogo e sostituire le copertine

Premi **Ricomincia su tutti e sostituisci le copertine**. La nuova coda riparte
da zero sui sistemi attualmente nel database, anche quelli già fotografati:
con 1.105 schede include esattamente 1.105 modelli. L'eventuale vecchia coda
viene contrassegnata come sostituita; esiti e riferimenti alle fonti restano
nello storico. Le nuove ricerche vengono rigenerate come **marca - modello**;
le vecchie stringhe conservate non vengono riutilizzate.

Per ogni risultato utilizzabile viene impostata la nuova copertina. La
copertina precedente e le altre immagini restano in galleria e possono essere
ripristinate da **Gestisci fotografie**. Se Commons restituisce la stessa
immagine già presente, viene riutilizzata senza duplicarla. **Copertine
aggiornate** conta i sistemi già fotografati; **Foto associate** quelli prima
senza foto. Il conteggio dei sistemi mancanti viene riletto dal database.

Se non esiste un risultato utilizzabile o Commons fallisce, la foto attuale
rimane disponibile. Una modifica manuale durante la richiesta viene rispettata
e il modello viene saltato, evitando di sovrascrivere una scelta appena fatta.
La modalità di sostituzione resta attiva dopo pausa, ricaricamento e riavvio.

Il nuovo avvio rispetta anche il cooldown e l'eventuale richiesta ancora in
corso della coda precedente; una risposta tardiva della vecchia coda non può
salvare immagini. Non è necessario svuotare il catalogo o eliminare i volumi.

### Pausa e ripresa

- Mantieni aperta questa sezione per proseguire. Non è un servizio in background.
- **Metti in pausa** interrompe l'avanzamento; una richiesta già partita può
  terminare e salvare la relativa immagine.
- Uscendo dalla sezione o chiudendo il browser non partono nuove richieste.
- Riapri il pannello e premi **Riprendi ricerca automatica**: coda ed esiti
  sono conservati nel database, anche dopo il riavvio dell'API.
- Ogni richiesta elabora una sola macchina; le richieste distano almeno due
  secondi. Per 1.139 ricerche occorrono almeno circa 38 minuti, oltre ai tempi
  di rete e alle eventuali pause.
- Errori di rete, timeout e limiti Commons fermano la coda sulla macchina
  corrente. Riprendendo viene ritentata la stessa macchina e viene rispettato
  `Retry-After` (secondi o data HTTP), oppure una pausa di 30 secondi.
- Il pannello mostra **Modello corrente** e il testo della ricerca. A ricerca
  ferma puoi **Salva ricerca per questo modello**, poi riprendere, oppure
  **Salta questo modello**. Il nome nella scheda e le foto esistenti non
  cambiano. Questi comandi conservano le pause richieste da Commons.
- Se Commons rifiuta la sintassi della ricerca (422), viene provata una sola
  semplificazione persistente del nome; per esempio `Apple ][` diventa
  `Apple II`. Se non è possibile semplificare ulteriormente, la macchina viene
  conteggiata come **Ricerca non valida** e la coda prosegue. Errori temporanei
  e risposte sconosciute restano invece in pausa, senza scartare il modello.
- L'errore API `urlparamnormal` riguarda il ridimensionamento dei file, non
  l'assenza di risultati. La stessa ricerca viene ritentata una sola volta
  senza richiedere miniature, dopo almeno due secondi. Restano i filtri su
  formato, attribuzione e licenza; per i risultati utilizzabili si usa l'URL
  originale anche come anteprima. Le altre ricerche mantengono miniature a
  500 px. Se il secondo tentativo fallisce, la macchina resta in attesa.
  Un `Retry-After` superiore a cinque secondi rinvia il tentativo alla ripresa
  della coda, evitando di tenere occupata la richiesta API durante lunghe pause.
- Dopo un'interruzione improvvisa, una richiesta bloccata viene resa di nuovo
  disponibile alla scadenza della prenotazione di 90 secondi.

I modelli senza risultati utilizzabili vengono conteggiati separatamente.
A ricerca completata, un nuovo avvio include le nuove schede e ritenta quelle
ancora prive di foto. Gli esiti già salvati restano nello storico interno.

## Scelta e correzione delle immagini

L'associazione automatica **non verifica che l'immagine raffiguri il modello
corretto**. Nessuna revisione umana viene registrata automaticamente.

Sono considerati i primi 12 risultati: immagini JPEG/PNG/WebP/GIF valide,
con attribuzione, pagina della fonte e una licenza libera riconoscibile
(CC BY, CC BY-SA, CC0 o pubblico dominio). Un risultato privo di questi
metadati viene saltato; non viene salvata una licenza inventata. Sono esclusi
metadati che dichiarano clausole NC/ND. Questa selezione non certifica la
correttezza legale dei metadati pubblicati dagli autori su Commons.

La didascalia inizia con **Scelta automatica Commons**. Autore, nome della
licenza, relativo URL quando disponibile e pagina del file vengono conservati.
Gli originali restano su Wikimedia: il programma salva collegamenti esterni,
non scarica i file nel volume fotografico.

Per correggere un'associazione, apri la scheda del calcolatore e scegli
**Gestisci fotografie**: puoi eliminare l'immagine errata, cercarne un'altra,
caricare una tua foto e cambiare copertina con i controlli già presenti.

## Implementazione e aggiornamento database

Due tabelle additive, `commons_photo_jobs` e `commons_photo_items`, conservano
coda, prenotazione della richiesta, esiti e riferimenti alle immagini. Sono
create al normale avvio dell'API senza cambiare i dati storici del catalogo.
L'avvio aggiunge in modo ripetibile la colonna booleana `replace_existing`
alle code precedenti: il valore predefinito `false` mantiene il loro comportamento
finché l'operatore sceglie il nuovo comando di riavvio completo.
Per una migrazione esplicita, a servizio fermo e con backup disponibile:

```bash
cd backend
python -m migrations.photo_jobs
```

Serve `DATABASE_URL` impostata sul database corretto; la migrazione è ripetibile.
Non viene avviata alcuna ricerca all'avvio o durante la migrazione.

API locali: `GET/POST /api/admin/photos`,
`POST /api/admin/photos/{id}/step`, `/pause`, `/resume`, `/query` e `/skip`.
Gli ultimi due richiedono `item_id` del modello corrente; `/query` richiede
anche `query` (2–90 caratteri). Una selezione obsoleta o una richiesta ancora
in corso produce 409. `POST /api/admin/photos/restart` richiede
`{"expected_job_id": ID_ULTIMA_CODA}` (oppure `null` se non esiste una coda)
e crea la nuova coda completa con sostituzione. Un ID superato produce 409,
senza creare due nuove code per un doppio invio. La migrazione sopra aggiorna
anche gli schemi precedenti all'introduzione della modalità di sostituzione.
Una prenotazione atomica impedisce due elaborazioni contemporanee anche con
più processi API. Le transazioni database non rimangono aperte durante la
richiesta a Wikimedia. Lo svuotamento dell'archivio archivia anche le code,
impedendo che una risposta tardiva venga associata a nuove schede.

Il pannello segue la modalità single-user locale delle altre funzioni
amministrative. Richiede accesso HTTPS a `commons.wikimedia.org` per la ricerca
e a `upload.wikimedia.org` per mostrare le immagini nel browser.

## Verifica del 14 novembre 2026

Test automatici su SQLite e PostgreSQL: ordine di rilevanza, licenza e crediti,
assenza di sovrascritture, pausa/ripresa, coda persistente, attesa tra richieste,
`Retry-After`, scadenza delle prenotazioni, reset durante una richiesta e
migrazione ripetibile. Le fixture Commons sono sintetiche.

Nel browser, con backend reale e risposte Commons sintetiche: dieci copertine
associate, pausa, ricaricamento della pagina e ripresa fino a completamento;
galleria ancora modificabile, pannelli a 320 px senza overflow e nessun errore
JavaScript. Ripetuta anche la suite browser preesistente di importazione,
conflitti, riconciliazione e confronto. Suite complete: 172 test SQLite e uno
specifico PostgreSQL saltato, 173 test PostgreSQL, 23 test frontend; build
React e Compose riuscite. Restano gli avvisi preesistenti sul bundle Vite
oltre 500 kB e sulla deprecazione Starlette TestClient/httpx.

La ricerca live dall'ambiente cloud è bloccata dal proxy: non è stato eseguito
un recupero reale delle foto per le 1.139 schede. La selezione effettiva delle
immagini andrà controllata sul computer dell'operatore.

## Ripresa di un'istanza esistente

Se `docker compose ls -a` mostra più progetti, usa quello che contiene il
catalogo effettivamente consultato. Nel caso diagnosticato su Windows il
progetto attivo è `hhe-import-test`; l'istanza predefinita ha API e web nello
stato `Created` e non è quella da aggiornare:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
docker compose -p hhe-import-test ps
```

Ricarica il browser con Ctrl+F5 e premi **Riprendi ricerca automatica**.
La coda già ferma a 304/1139, le 205 foto e tutti gli esiti rimangono nel
database: non svuotare l'archivio e non rimuovere i volumi. L'aggiornamento
non richiede una nuova coda. Per i log usa lo stesso nome progetto:
`docker compose -p hhe-import-test logs --tail=100 api`.

Il caso reale `MicroMainFrame 9000` ha restituito HTTP 200 con codice API
`urlparamnormal` dal computer dell'operatore. Il fallback, i limiti e la
conservazione delle foto sono verificati con risposte Commons sintetiche;
la verifica live dal cloud resta impedita dal proxy.

### Verifica della correzione della ripresa

303 test SQLite superati (uno specifico PostgreSQL saltato), 304 PostgreSQL
su database isolato e 26 frontend. Build React e avvio Compose riusciti;
catalogo PostgreSQL di prova conservato a 1.105 schede, API foto disponibile.
Restano gli avvisi preesistenti sul bundle Vite e Starlette TestClient/httpx.

Nel browser Chromium con backend reale e Commons simulato: ripresa di una
coda già in pausa, errore `urlparamnormal` seguito da successo senza miniature,
429 locale senza arresto della coda, pausa per indisponibilità remota, salto
esplicito, modifica della ricerca, ricaricamento e ripresa dopo il cooldown.
Due foto associate e una macchina saltata; la foto preesistente conservata.
Controllato anche il layout a 320 px, senza overflow né errori JavaScript.
I test coprono inoltre ritentativi limitati, filtro PDF, attribuzione e
licenza, `Retry-After` lungo e recupero senza cambiare ID o esiti della coda.

Il significato di `urlparamnormal` è riscontrabile nell'implementazione
ufficiale MediaWiki, metodo `checkParameterNormalise` di
[ApiQueryImageInfo](https://github.com/wikimedia/mediawiki/blob/master/includes/Api/ApiQueryImageInfo.php).

### Verifica del riavvio completo e delle copertine sostitutive

325 test SQLite superati (uno specifico PostgreSQL saltato), 326 PostgreSQL,
26 frontend e build React riuscita. Dopo l'ultimo aggiornamento dei metadati
delle immagini riutilizzate, ripetuti tutti i 46 test delle code fotografiche
sia su SQLite sia su PostgreSQL. Verificati anche la migrazione di una coda
senza la nuova colonna, il riavvio concorrente a una ricerca e il mantenimento
delle pause di Commons. Il test di scala include esattamente 1.105 sistemi,
sia con foto in galleria sia con copertine legacy.

Chromium con backend reale e Commons sintetico: nuova coda anche con zero
foto mancanti, copertine esistenti aggiornate, immagine precedente conservata
in galleria, ricerca senza risultati che conserva la foto, modalità completa
persistente dopo pausa/ricaricamento/ripresa, contatori e stringa iniziale della
ricerca manuale. Layout a 320 px senza overflow e nessun errore JavaScript.

Compose aggiornato sul catalogo PostgreSQL isolato: avvio riuscito, migrazione
automatica, nuova coda con 1.105 righe e query nel formato marca - modello.
Catalogo e copertine invariati durante la creazione; coda lasciata in pausa
senza avviare richieste Commons. Il database locale dell'operatore non è
raggiungibile dal cloud: il nuovo pulsante avvia la ricerca sulla sua istanza.
