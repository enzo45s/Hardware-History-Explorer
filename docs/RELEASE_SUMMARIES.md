# Commercializzazioni: sintesi di date, mercati e prezzi

Una scheda puo contenere una data del modello da una fonte e un prezzo regionale
da un'altra, importati in registrazioni separate. Il catalogo ora presenta una
sola commercializzazione quando l'abbinamento e univoco e i valori compatibili.
Si applica automaticamente anche ai dati gia presenti e alle nuove importazioni.

Per esempio:

| Registrazione originale | Data | Prezzo |
| --- | --- | --- |
| Non specificato dalla fonte | 1982 | assente |
| Stati Uniti | assente | 3298 USD |

La scheda mostra **Stati Uniti · 1982 · 3298 USD**, con le citazioni di entrambe
le registrazioni. **Provenienza dei dati accorpati** permette di consultare i
valori originali e le rispettive fonti. Se la data originale non specificava il
mercato, una nota indica che si tratta della **data del modello**: non diventa
una prova indipendente della disponibilita in quella regione o della data del
listino. Il tipo di prezzo rimane quello riportato dalla sua fonte.

## Quando vengono accorpati

- Una registrazione con data e senza prezzo puo completare una registrazione
  con prezzo, se esiste un solo abbinamento compatibile.
- Mercati esplicitamente uguali sono compatibili. Una data senza mercato puo
  accompagnare il prezzo dell'unico mercato noto del modello. Non si deduce
  un paese dalla valuta e non si assegna a un paese un prezzo senza mercato.
- Date, precisioni, valute e fine commercializzazione non devono essere in
  conflitto. Fonti concordi sulla stessa data possono essere riunite; la
  precisione non viene aumentata e il periodo non puo essere invertito.
- I placeholder noti dei mercati non specificati, compreso quello AppleDB,
  vengono riconosciuti. **Globale** rimane un mercato esplicito distinto.

## Cosa rimane separato

- Piu prezzi possibili, anche uguali: possono riferirsi a configurazioni diverse.
- Piu mercati conosciuti: la data generica non viene attribuita a uno arbitrariamente.
- Anni/date differenti o precisioni differenti tra le registrazioni.
- Un listino successivo senza data: non riceve l'anno di lancio del modello.
- Informazioni prive di un abbinamento sicuro; se nessuna fonte indica il
  mercato, la scheda mostra **Mercato non documentato**.

## Conservazione e aggiornamento

L'accorpamento e una vista di lettura, senza migrazioni o cancellazioni.
`GET /api/computers/{id}` e `GET /api/compare` aggiungono `display_releases`:
contiene sintesi, ID originali, provenienza dei campi e ambito della data.
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

## Verifiche

I test backend coprono l'esempio 1982/3298 USD, provenienza dei singoli campi,
originali immutati, prezzi zero, piu mercati/prezzi, date discordanti, listini
successivi, precisioni e ordine dei record. I test API controllano anche editor,
confronti e contesto AI. Il test browser usa API reali e dati sintetici locali:

```bash
cd frontend
npm run test:browser:releases
```

Controlla la sintesi, l'apertura degli originali con le fonti e i viewport
da 320 e 390 px; elimina soltanto il computer sintetico creato dalla prova.

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
