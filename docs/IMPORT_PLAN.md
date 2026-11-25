# Piano di integrazione importazioni

Branch: `feat/historical-data-import`, basato sulle funzionalità già presenti
in `feat/admin-panel`. Nessun merge automatico su main.

1. Valutare accesso, esportazioni e riutilizzo delle cinque fonti; conservare i
   blocchi osservati senza scambiarli per indisponibilità dei siti.
2. Aggiungere staging persistente, normalizzazione validata e adattatori per
   CSV/JSON, Wikidata e l'esportazione autorizzata RetroFlops.
3. Estendere lo schema solo con tabelle additive per lavori, righe originali,
   identità esterne, asserzioni e decisioni. Migrazione ripetibile senza DELETE.
4. Anteprima, conferma, deduplicazione conservativa, aggiornamenti additivi,
   conflitti espliciti, controllo umano e tentativi successivi.
5. Integrare l'amministrazione React e il contesto con fonti dell'assistente.
6. Test SQLite/PostgreSQL, build, browser e Compose; documentazione e PR.

Limiti deliberati: nessuno scraping HTML generalizzato, nessuna foto importata
automaticamente, nessuna promozione automatica a «verificato». Le quantità
incompatibili restano distinte; date di annuncio e commercializzazione non
sono intercambiabili. Le importazioni vengono confermate esplicitamente.
