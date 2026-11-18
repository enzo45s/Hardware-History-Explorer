# Bibliografia e citazioni del dataset di base

Le schermate del catalogo e dell'amministrazione escludono le citazioni MAME
dalla bibliografia operativa. La commercializzazione mostra al massimo una
fonte, privilegiando quella del prezzo; non presenta il riquadro di provenienza
o la nota tecnica sull'accorpamento. Le altre fonti indipendenti restano disponibili.

## Ambito

- Schede, specifiche, commercializzazioni, fatti, vendite e recensioni.
- Pannello Fonti e relativi endpoint di elenco/dettaglio/modifica.
- Asserzioni visibili nel pannello importazioni e relativi conteggi di verifica.
- Citazioni e asserzioni trasmesse all'assistente AI.

Il riconoscimento usa le parole MAME/Mamedev in titolo, autore, editore e tipo
di fonte, i domini ufficiali mamedev.org/mame.net e il repository
github.com/mamedev/mame, compresi gli URL raw e codeload. Non usa una ricerca
indiscriminata della sottostringa negli URL: fonti come 1000bit, AppleDB,
Wikidata o un dominio differente non vengono escluse per un parametro casuale.

## Conservazione dei dati

La modifica non riscrive modelli, specifiche, prezzi, fotografie o relativi ID.
Gli identificativi delle citazioni del dataset di base rimangono nello storico
interno, insieme agli originali e alle asserzioni ETL: questo conserva i
collegamenti, le decisioni precedenti e la ripetibilita delle importazioni.
Non viene effettuata una cancellazione fisica dello storico o della tabella
Sources. Backup completi e download espliciti degli originali possono quindi
contenere ancora questi metadati.

Le API bibliografiche restituiscono solo fonti ammesse; una citazione MAME non
e raggiungibile per ID attraverso il pannello Fonti e non puo essere reinserita
manualmente nella bibliografia. Le importazioni tecniche continuano a funzionare
e a conservare gli originali senza far ricomparire citazioni MAME nelle schermate.
Nessun dato viene verificato automaticamente e nessuna fonte alternativa viene
inventata per un'informazione che ne rimane priva.

Le attribuzioni e le licenze delle fotografie restano nei metadati fotografici.
Licenze, file e documentazione dei dataset originali sono conservati nel repository.

## Aggiornamento

Sul branch `feat/historical-data-import`, dalla cartella del progetto:

```bash
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait
```

Ricarica la pagina. La politica si applica subito alle fonti gia presenti e
alle importazioni successive. Non richiede migrazioni o una nuova importazione.

## Verifiche

I test backend verificano il riconoscimento dei riferimenti, i casi che non
vanno esclusi, la bibliografia di ogni entita, le API del pannello Fonti, il
contesto AI, i conteggi delle asserzioni e la conservazione di dati e originali.
Una seconda importazione identica rimane invariata. Il test browser controlla
una commercializzazione accorpata con una sola fonte del prezzo, i dettagli
tecnici conservati dopo un'importazione MAME e il pannello Fonti privo di tali
citazioni, anche su schermi da 320 e 390 px.

Verifiche del 18 novembre 2026: **434 test SQLite superati e uno specifico
PostgreSQL saltato; 435 test PostgreSQL superati; 28 test frontend superati**.
Build React, build/avvio Docker Compose e Chromium su commercializzazioni,
pannello Fonti e importazione Excel riusciti. Il bundle Vite resta oltre
500 kB, avviso gia presente nelle versioni precedenti. Le prove usano database
isolati; nessun accesso o modifica al database locale Windows/Mac dell'utente.
