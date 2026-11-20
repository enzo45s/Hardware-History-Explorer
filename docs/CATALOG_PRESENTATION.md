# Etichette e provenienza del catalogo

Catalogo, timeline, schede, confronti ed editor amministrativo usano nomi
centrati sui calcolatori: **CPU · Modello**, **CPU · Frequenza**,
**Video · Risoluzione**, **Video · Frequenza di aggiornamento**,
**Audio · Chip audio**. Non ripetono il nome del dataset in ogni proprietà.

MAME rimane una fonte del dataset di base. I titoli e gli URL delle fonti
restano completi nella bibliografia; i collegamenti accanto ai singoli dati
sono abbreviati in **Fonte**, con titolo completo accessibile e al passaggio
del mouse. Originali, estratti, licenze, asserzioni e decisioni umane restano
nell'audit delle importazioni.

Le capacità predefinite della fonte sono visualizzate come **Capacità di
riferimento**, mantenendole separate da capacità minima, massima e opzioni
di memoria. L'etichetta non certifica che quel valore fosse una dotazione
commerciale ordinabile al lancio. Valori, unità e stati di verifica non cambiano.

I nomi delle configurazioni conservano le revisioni hardware; eventuali nomi
leggibili uguali sono distinti senza fondere configurazioni o cambiare ID.
Nei confronti le proprietà con la stessa etichetta vengono raggruppate
conservando tutti i valori distinti e le relative unità.

## Aggiornamento di un archivio esistente

```powershell
git pull --ff-only
docker compose up --build -d
```

Mantieni l'eventuale nome progetto `-p` della tua istanza e ricarica con
Ctrl+F5. Non occorrono reset, migrazioni o nuovi caricamenti del dataset.

## Compatibilità tecnica

`backend/app/catalog_display.py` definisce esclusivamente la presentazione.
Le API pubbliche aggiungono `display_description`, `display_name` nelle
configurazioni e `display` nelle specifiche, mantenendo i campi originali e
la vista `normalized`. Le regole ETL di identità e deduplicazione non cambiano.
L'assistente usa i testi leggibili conservando le prove e le citazioni.

L'API dell'editor mantiene il formato originale come comportamento predefinito.
Il frontend richiede `?readable=true` per ottenere anche i metadati di
presentazione. I payload di salvataggio li escludono: se l'operatore modifica
un altro campo, chiavi e descrizioni originali sono conservate. Una modifica
esplicita del testo leggibile salva invece il nuovo testo scritto dall'operatore.

## Verifica del 14 novembre 2026

- Backend: `python -m pytest -q --tb=short`, **200 passati su SQLite** e
  uno specifico PostgreSQL saltato; **201 passati su PostgreSQL** isolato.
  Dopo l'ultima rifinitura delle collisioni nei nomi, ripetuti i tre test
  `tests/test_catalog_display.py` su entrambi i database: tutti passati.
- Frontend: `npm test`, **25 passati**; `npm run build` riuscita.
  Resta l'avviso Vite preesistente sul bundle maggiore di 500 kB.
- Docker Compose: build e avvio di API, web e PostgreSQL riusciti su un
  progetto di prova separato con il corpus già arricchito. Controllate le
  presentazioni di tutte le **1.105 schede**, senza riferimenti residui a
  MAME/emulazione nelle descrizioni generate e nelle etichette di lettura.
- Chromium: catalogo e scheda IBM PC 5150, bibliografia completa, confronto
  con selezione di configurazione sul corpus PostgreSQL. Browser editor su
  SQLite isolato: modifica di un valore e salvataggio senza rinominare le
  chiavi importate; successiva rinomina esplicita conservando gli ID.
- `npm run test:browser`: importazione, conflitti, revisione, riconciliazione
  e layout mobile a 320/390 px passati su un ulteriore archivio di prova.

Nessun dato storico aggiunto o eliminato da questa modifica. I caricamenti
browser sintetici riguardano esclusivamente il database di prova. Il contesto
dell'assistente è coperto dai test; nessuna nuova chiamata AI esterna eseguita.
