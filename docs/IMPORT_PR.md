Il catalogo ora può essere popolato da CSV/JSON o da fonti aperte senza perdere
originali e citazioni. L'upload crea un'anteprima persistente; l'operatore sceglie
le corrispondenze, può escludere righe e applica esplicitamente il lotto. I dati
mancanti vengono aggiunti e i valori discordanti rimangono in revisione finché
una persona decide, con nota e controllo sui valori modificati nel frattempo.

La PR punta a `main`, dove `feat/admin-panel` è già confluito con la PR #2.
Il diff comprende il sistema d'importazione e i suoi successivi miglioramenti;
amministrazione, confronti e temi sono già presenti nella base. Non effettua
merge automatico su main.

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
- Alias tecnici e unità esplicite uniformati anche per le specifiche precedenti,
  senza riscritture automatiche dei dati originali; schede e confronti usano
  una vista normalizzata additiva. Parti hardware e unità ambigue restano distinte.
- Conflitti con nomi/valori leggibili e contesto; citazione separata dal dato,
  rifiuto motivato e blocco dell'accettazione di decisioni ormai superate.
- Registro esplicito di alias dei produttori/modelli, riuso delle schede
  esistenti e riconciliazione dei duplicati pregressi con anteprima, scelta
  dell'ID da mantenere, consenso dell'operatore e audit degli originali.
  Configurazioni, foto, prezzi e citazioni sono trasferiti senza perdere i
  propri ID; famiglie e modelli specifici non vengono confusi.
- Bibliografia comprensiva delle citazioni dei singoli dati, fonti visibili
  sulle specifiche e conteggio dei prezzi effettivamente presenti nel file.
- Reset locale del catalogo con anteprima, conferma del backup, frase esplicita
  e audit dei metadati precedenti. Il catalogo resta vuoto anche al riavvio,
  fonti e file fotografici sono conservati, le vecchie importazioni archiviate
  e gli abbinamenti precedenti isolati dai nuovi import. Nessun reset automatico.
- Corpus aggiuntivo da MAME 0.276: 1.139 schede candidate in cinque lotti JSON,
  con 1.251 configurazioni emulate e 3.184 specifiche citate. Generatore
  riproducibile da Git ed export ufficiale XML della stessa versione; originali,
  licenze e hash conservati. CPU/clock/RAM hanno proprietà esplicitamente
  riferite all'emulatore, separate dai valori storici. Copertura CSV leggibile
  in Excel; nessun nuovo servizio remoto o dipendenza di runtime.

Le pagine delle cinque fonti sono bloccate dal proxy cloud con 403. Per
RetroFlops sono stati letti repository e licenza ufficiali: incluso un campione
reale Apple II e due campioni con misure tecniche, attribuzione, originali e hash.
Il campione ampliato contiene 19 modelli, 26 configurazioni e 70 specifiche.
Su SQLite e PostgreSQL separati, partendo dal seed e dal precedente campione,
ha prodotto 11 importati, 4 aggiornati e 4 invariati (25 schede totali); il
replay restituisce 19 invariati. Due differenze nelle descrizioni restano in revisione,
nessuna asserzione viene verificata automaticamente. Nessuna modifica al DB
dell'utente e nessuna importazione automatica all'avvio.

Il campione non contiene prezzi: i campi assenti non vengono inventati e i
prezzi già archiviati sono conservati.

Il corpus MAME non fornisce prezzi e non certifica commercializzazioni o
configurazioni vendute. Date e specifiche richiedono revisione storica.
Importazione completa e replay dei cinque lotti provati su SQLite e PostgreSQL:
1.139 schede, 1.251 configurazioni e 3.184 specifiche restano invariati;
controllate via API tutte le schede e le citazioni delle specifiche. Chromium
con il catalogo reale verifica timeline, catalogo, confronto, analisi e
paginazione delle fonti. Nessuna verifica automatica dei dati.

Verifiche aggiornate: 143 test SQLite passati e uno specifico PostgreSQL saltato,
144 test PostgreSQL passati, 23 test frontend passati, build e avvio Compose,
Chromium con revisione conflitti, riconciliazione, reset esplicito e layout mobile
a 320/390 px riusciti. Dopo il reset e un riavvio API il catalogo rimane vuoto:
il campione produce 19 importati e poi 19 invariati su PostgreSQL. Vite
segnala il bundle oltre 500 kB; la CI remota va confermata su GitHub.

Verifiche e limiti aggiornati in `docs/ARCHIVE_RESET.md`, `docs/RECONCILIATION.md` e `docs/IMPORT_NORMALIZATION_REPORT.md`;
verifica del corpus in `docs/datasets/mame-0276/VALIDATION.md`;
verifica iniziale in `docs/IMPORT_REPORT.md`; istruzioni e formati
in `docs/IMPORTING.md`, valutazione delle fonti in `docs/IMPORT_SOURCES.md`.
Il pannello resta locale single-user senza nuova autenticazione. La generazione
AI esterna non è stata provata con una chiave/crediti configurati.
