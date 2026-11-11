Il catalogo ora può essere popolato da CSV/JSON o da fonti aperte senza perdere
originali e citazioni. L'upload crea un'anteprima persistente; l'operatore sceglie
le corrispondenze, può escludere righe e applica esplicitamente il lotto. I dati
mancanti vengono aggiunti e i valori discordanti rimangono in revisione finché
una persona decide, con nota e controllo sui valori modificati nel frattempo.

La PR è basata su `feat/admin-panel`, che contiene l'amministrazione, i confronti
e i temi già presenti nel progetto. Questo mantiene il diff focalizzato sul
sistema d'importazione. Non effettua merge su main.

- ETL modulare, normalizzazione di nomi/unità/date, deduplicazione conservativa,
  identità esterne separate per fonte, importazioni incrementali e ripetibili.
- Migrazione esclusivamente additiva: lavori, righe originali/normalizzate,
  asserzioni con provenienza e decisioni umane. Specifiche e altre entità
  continuano a utilizzare i collegamenti alle fonti già presenti.
- Amministrazione React: selezione fonte, upload, recupero API, anteprima,
  conteggi, esclusioni, abbinamenti, conflitti, verifiche e nuovi tentativi.
- L'assistente cerca oltre le prime 100 schede e riceve contesto limitato con
  fonti, stime e stati; nessuna modifica a fotografie o funzioni esistenti.
- Adattatori per export RetroFlops CC BY 4.0 e Wikidata; le altre tre fonti
  restano manuali finché permessi e disponibilità non sono accertati.

Le pagine delle cinque fonti sono bloccate dal proxy cloud con 403. Per
RetroFlops sono stati letti repository e licenza ufficiali: incluso un campione
reale Apple II derivato da record canonici, con attribuzione, originali e hash.
Il campione ha prodotto un solo modello in un database di prova separato, nessuna
misura tecnica aggiunta e nessuna asserzione promossa a verificata. Il replay
è invariato. Nessuna importazione storica massiva o modifica al DB dell'utente.

Verifiche e limiti dettagliati in `docs/IMPORT_REPORT.md`; istruzioni e formati
in `docs/IMPORTING.md`, valutazione delle fonti in `docs/IMPORT_SOURCES.md`.
Il pannello resta locale single-user senza nuova autenticazione. La generazione
AI esterna non è stata provata con una chiave/crediti configurati.
