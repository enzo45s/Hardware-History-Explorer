# Commercializzazioni: sintesi di date, mercati e prezzi

Una scheda puo contenere una data del modello da una fonte e un prezzo regionale
da un'altra, importati in registrazioni separate. Il catalogo presenta anno e
prezzo insieme quando i valori sono compatibili, anche con più offerte e mercati.
Si applica automaticamente anche ai dati gia presenti e alle nuove importazioni.

Per esempio:

| Registrazione originale | Data | Prezzo |
| --- | --- | --- |
| Non specificato dalla fonte | 1982 | assente |
| Stati Uniti | assente | 3298 USD |

La scheda mostra **Stati Uniti · 1982 · 3298 USD**, con una sola citazione,
privilegiando la fonte del prezzo quando disponibile. Il riquadro di provenienza
e la nota tecnica sull'accorpamento sono stati rimossi dall'interfaccia.
L'anno resta un dato del modello: l'accorpamento non certifica una data di
listino o una disponibilita regionale non documentata. Il tipo di prezzo
rimane quello riportato dalla sua fonte; i valori originali e il loro ambito
restano nel database e nei campi tecnici API.

Le citazioni MAME non compaiono nella bibliografia della scheda o nel pannello
Fonti; lo storico interno delle importazioni viene conservato, come descritto
nella [politica delle fonti](SOURCE_POLICY.md).

## Quando vengono accorpati

- Una registrazione con data e senza prezzo può completare una o più offerte
  compatibili dello stesso modello. Tutte le fonti pertinenti devono concordare
  sulla data: non viene scelta una delle date in base all'ordine dei record.
- Mercati esplicitamente uguali sono compatibili. Una data senza mercato può
  accompagnare i prezzi di più mercati come contesto del modello. Non si deduce
  un paese dalla valuta e non si assegna a un paese un prezzo senza mercato.
- Una data regionale può completare più prezzi nel medesimo mercato, senza
  essere estesa a paesi differenti. Configurazioni sostanziali con un ambito
  distinto restano separate. Prezzi differenti o ripetuti nello stesso paese
  rimangono offerte distinte, ciascuna con il proprio identificativo.
- Le precisioni compatibili vengono riunite: `1990`, `1990-10` e `1990-10-15`
  indicano una stessa data con dettaglio crescente. La sintesi sceglie soltanto
  una data effettivamente presente nelle fonti, senza inventare mese o giorno.
  Le fonti dell'anno non vengono presentate come supporto del giorno esatto.
  Una data regionale già associata a un prezzo conserva la propria precisione.
- Date realmente discordanti, valute e fine commercializzazione non devono
  essere in conflitto. Un intervallo non può essere invertito; una fine indicata
  soltanto come anno o mese viene trattata come intervallo, senza creare un giorno.
- I placeholder noti dei mercati non specificati, compreso quello AppleDB,
  vengono riconosciuti. **Globale** rimane un mercato esplicito distinto.

## Cosa rimane separato

- Più prezzi possibili nello stesso paese, anche uguali: possono riferirsi a
  configurazioni diverse. Ora possono condividere il contesto della data,
  senza essere ridotti a un solo importo.
- Più aree geografiche mantengono prezzi e valute propri. La data generale resta
  del modello, senza certificare la disponibilità locale del sistema o un
  listino a quella data.
- Anni, mesi o giorni discordanti. Una differenza nella sola precisione non
  costituisce un conflitto: `1990` e `1990-10-15` sono compatibili, mentre
  `1990-10-15` e `1990-10-16` rimangono distinti.
- Un listino successivo senza data: non riceve l'anno di lancio del modello.
- Informazioni prive di un abbinamento sicuro; se nessuna fonte indica il
  mercato, la scheda mostra **Mercato non documentato**.

Le [regioni europee](EUROPE_GROUPING.md) vengono presentate sotto **Europa**.
Offerte con tutti i dati uguali e ripetute in paesi europei differenti possono
essere riunite; importi, valute e date differenti restano offerte distinte
nello stesso riquadro. Non si equiparano prezzi privi di valuta.

## Conservazione e aggiornamento

L'accorpamento e una vista di lettura, senza migrazioni o cancellazioni.
`GET /api/computers/{id}` e `GET /api/compare` aggiungono `display_releases`:
contiene sintesi, ID originali, provenienza dei campi e ambito della data.
Se una data supporta più offerte, il suo ID può comparire in più elenchi
`release_ids`; gli ID delle sintesi restano univoci. `date_scope: model` distingue
il contesto del modello dalla data regionale. Il testo sulla data offre una
spiegazione al passaggio del puntatore, senza nuovi riquadri di provenienza.
`releases` conserva i valori originali e gli ID utilizzati da amministrazione,
importatori e revisioni delle asserzioni. L'assistente AI continua a ricevere
queste evidenze originali, senza trasformare un prezzo senza data in un prezzo
documentato al lancio. Nessun dato viene verificato automaticamente.

Per aggiornare l'installazione locale, dalla cartella del repository sul branch
`feat/historical-data-import`:

```bash
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait
```

Ricarica la pagina del catalogo. Non occorre importare nuovamente i dati o
svuotare l'archivio. Mantieni il nome Compose della tua istanza se diverso.

Questa regola si applica a ogni lettura del catalogo: vale per tutto il database
esistente, i confronti e i successivi caricamenti Excel, senza procedure da
eseguire scheda per scheda. I prezzi importati senza una data rimangono tali
nell'editor e nei dati originali: la sintesi non riscrive la storia dei mercati.

## Verifiche

I test backend coprono l'esempio 1982/3298 USD, provenienza dei singoli campi,
originali immutati, prezzi zero, piu mercati/prezzi, date discordanti, listini
successivi, precisioni e ordine dei record. I test API controllano anche editor,
confronti e contesto AI. Il test browser usa API reali e dati sintetici locali:

```bash
cd frontend
npm run test:browser:releases
```

Controlla la sintesi con una sola fonte del prezzo, l'assenza del riquadro di
provenienza e delle fonti MAME anche dopo una nuova importazione, il pannello
Fonti e i viewport da 320 e 390 px; elimina soltanto il computer sintetico
creato dalla prova. Gli originali rimangono conservati internamente.

Verifiche del 17 novembre 2026: **411 test SQLite superati e uno specifico
PostgreSQL saltato; 412 test PostgreSQL superati; 27 test frontend superati**.
Build React e avvio Docker Compose riusciti; test Chromium delle
commercializzazioni e regressione dell'importazione Excel riusciti. Vite
segnala il bundle oltre 500 kB, avviso gia presente prima della modifica.

Prova aggiuntiva con l'Excel originale e il corpus PostgreSQL di sviluppo
(1.106 schede, compresa una fixture preesistente), caricando i 591 prezzi in
una transazione poi annullata: **512 gruppi data/prezzo accorpati**. Tutti gli
ID originali, importi e collegamenti alle fonti sono conservati; la vista non
modifica le righe originali. Nessuna importazione persistente del file e
nessun accesso al database locale Windows/Mac dell'utente.

Verifica del 19 novembre 2026: **738 test SQLite superati, uno specifico
PostgreSQL saltato; 135 test mirati PostgreSQL e 31 test frontend superati**.
La regressione comprende due modelli con anno distinto e successive importazioni
Excel su Stati Uniti, Giappone e Regno Unito: tutte le offerte compatibili
ricevono il contesto corretto, senza riscrivere le date originali o confondere
gli identificativi delle offerte.

Su un database SQLite temporaneo con i cinque lotti del catalogo e il foglio
Excel allegato in precedenza sono state controllate **1.073 schede e 1.641
commercializzazioni originali**. Sei ulteriori schede sono normalizzate dalla
regola per più offerte; 27 mantengono dati separati: cinque hanno anni discordanti
e 22 riportano listini successivi senza data. Le 547 sintesi con data e prezzo
non alterano importi, date, ID o collegamenti alle fonti. Il database temporaneo
è stato eliminato; il nuovo Excel dell'utente non è stato allegato e non è stato
verificato direttamente.

La successiva regressione Macintosh LC riproduce i tre record segnalati:
`1990`, `1990-10-15` e il prezzo statunitense `2499 USD`. La sintesi mostra
**Stati Uniti · 1990-10-15 · 2499 USD**, usando soltanto AppleDB per sostenere
la precisione giornaliera e la fonte del prezzo per l'importo. La prova con
i record del dataset di base, l'arricchimento AppleDB e la riga dell'Excel
precedentemente allegato conferma il risultato su SQLite temporaneo, senza
alterare i tre record originali. Non è una verifica indipendente dei contenuti
delle fonti. La stessa regola si applica a tutto il catalogo, anche alle date
senza prezzo e alle offerte in più mercati. Verificati **747 test SQLite**
(uno saltato), **144 test mirati PostgreSQL**, 31 test frontend e Chromium
per commercializzazioni, prezzi ed Europa.
