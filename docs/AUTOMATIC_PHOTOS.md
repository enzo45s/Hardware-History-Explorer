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
confronti. La ricerca usa soltanto il nome del modello, senza aggiungere
nuovamente il produttore.

La coda iniziale contiene solo le schede senza foto in galleria e senza
copertina nel precedente campo `image_url`. Le foto esistenti non vengono
sostituite. Anche una foto inserita manualmente durante la ricerca viene
ricontrollata prima del salvataggio e conservata.

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
  `Retry-After` numerico, oppure una pausa di 30 secondi.
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
create al normale avvio dell'API senza modificare le tabelle esistenti.
Per una migrazione esplicita, a servizio fermo e con backup disponibile:

```bash
cd backend
python -m migrations.photo_jobs
```

Serve `DATABASE_URL` impostata sul database corretto; la migrazione è ripetibile.
Non viene avviata alcuna ricerca all'avvio o durante la migrazione.

API locali: `GET/POST /api/admin/photos`,
`POST /api/admin/photos/{id}/step`, `/pause` e `/resume`.
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
