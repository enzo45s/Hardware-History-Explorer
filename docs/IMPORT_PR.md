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
- Completamento editoriale opt-in delle categorie sulle schede generiche già
  caricate: anteprima, regole versionate e asserzioni pending nello storico.
  Sul corpus reale riconosce 610 schede e ne lascia 529 generiche, preservando
  classificazioni manuali, ID e tutti gli altri dati.
- Foto automatiche Commons: associazione del primo risultato utilizzabile,
  ordinato per rilevanza, senza conferma per immagine; attribuzione e licenza
  conservate. Coda persistente, pausa/ripresa, una richiesta per volta, rispetto
  dei limiti e protezione delle fotografie già presenti. Due nuove tabelle
  additive e migrazione ripetibile; nessun processo automatico all'avvio.
- Rifinitura opt-in del catalogo esistente: accorpamento di 34 schede regionali
  in 22 gruppi, con trasferimento di tutti i dati e audit; revisioni hardware
  distinte. Le importazioni successive seguono configurazioni e prezzi originali
  tramite le identità nell'audit, anche dopo collisioni di nomi/mercato/data.
- Snapshot AppleDB/MAME con originali e licenze: 105 specifiche documentali,
  3.891 proprietà esplicitamente emulate e cinque prezzi IBM RT contestualizzati.
  Descrizioni italiane per le schede vuote, preservando il testo già scritto.
  Nessun nuovo modello tramite l'arricchimento locale; replay invariato.
- Adattatore Wikidata esteso a descrizioni italiane, CPU/OS, unità e prezzi.
  Prezzi qualificati/multipli o con valuta non risolta rimangono note contestuali;
  codici valuta risolti via ISO 4217, senza inventare mercati o date di lancio.

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

I cinque lotti MAME iniziali non contengono prezzi e non certificano commercializzazioni o
configurazioni vendute. Date e specifiche richiedono revisione storica.
Importazione completa e replay dei cinque lotti provati su SQLite e PostgreSQL:
1.139 schede, 1.251 configurazioni e 3.184 specifiche restano invariati;
controllate via API tutte le schede e le citazioni delle specifiche. Chromium
con il catalogo reale verifica timeline, catalogo, confronto, analisi e
paginazione delle fonti. Nessuna verifica automatica dei dati.

Verifiche aggiornate: 197 test SQLite passati e uno specifico PostgreSQL saltato,
198 test PostgreSQL passati, 23 test frontend passati, build e avvio Compose,
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

Aggiornamento 14 novembre: browser con backend reale e Commons sintetico,
dieci immagini associate, pausa/ricaricamento/ripresa e modifica dalla galleria;
nessuna ricerca live riuscita a causa del proxy cloud. Ripetuta la suite browser
di importazione/conflitti/riconciliazione. Categorie applicate su PostgreSQL
isolato al corpus completo, con tutte le 1.139 schede controllate prima/dopo
e replay di zero aggiornamenti. Guide in `docs/AUTOMATIC_PHOTOS.md` e
`docs/CLASSIFICATION.md`; database dell'utente mai raggiunto.

Rifinitura verificata sull'intero corpus PostgreSQL isolato: 1.105 sistemi,
1.308 configurazioni e 7.180 specifiche; tutti gli ID delle configurazioni e
specifiche preesistenti conservati. Descrizioni presenti su tutte le 1.105
schede nella prova, cinque prezzi effettivamente importati e replay con zero
aggiornamenti. Ricaricato anche il primo lotto MAME originale: 250 invariati.
Browser con accorpamento, fotografia preservata, arricchimento e prezzo
visibile su mobile. Limiti storici e copertura parziale espliciti in
`docs/CATALOG_REFINEMENT.md`, prova in `docs/CATALOG_REFINEMENT_VALIDATION.md`.

Le viste del catalogo ora usano nomi hardware leggibili senza ripetere MAME
in descrizioni, configurazioni e specifiche. Fonti complete e chiavi originali
restano conservate; nessuna migrazione o reimportazione necessaria. Le capacità
di riferimento restano distinte dai limiti commerciali documentati. L'editor
mantiene le chiavi importate nei salvataggi non relativi alle etichette.
Verifica: 200 test SQLite più uno specifico PG saltato, 201 PostgreSQL,
25 frontend, build/Compose e prove Chromium di schede, confronto, editor e
importazioni riuscite. Dettagli in `docs/CATALOG_PRESENTATION.md`.
