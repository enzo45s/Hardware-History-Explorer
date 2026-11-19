Il catalogo ora può essere popolato da CSV/JSON o da fonti aperte senza perdere
originali e citazioni. L'upload crea un'anteprima persistente; l'operatore sceglie
le corrispondenze, può escludere righe e applica esplicitamente il lotto. I dati
mancanti vengono aggiunti e i valori discordanti rimangono in revisione finché
una persona decide, con nota e controllo sui valori modificati nel frattempo.

Le commercializzazioni ora presentano insieme data e prezzo da registrazioni
complementari quando l'abbinamento e univoco. Sintesi con una sola citazione
e senza riquadro di provenienza; originali e ambito della data conservati
internamente. Le citazioni MAME e le autocitazioni HHE sono escluse da catalogo,
pannello Fonti, asserzioni visibili e contesto AI, mantenendo dati e audit ETL.
Le fonti RetroFlops sono visibili solo quando ancora collegate ad almeno un
calcolatore, specifica, commercializzazione, vendita, recensione o fatto.
Mercati/prezzi multipli, date
discordanti e listini successivi rimangono distinti. Nessuna modifica agli ID,
all'audit ETL o alle evidenze originali usate dall'editor e dall'assistente AI.
Regole e verifica in `docs/RELEASE_SUMMARIES.md`.

Schede e confronti riuniscono in Europa i profili tecnici regionali identici,
conservando revisioni, tastiere e dotazioni differenti. Un riquadro Europa
raggruppa le offerte regionali, accorpando solo dati equivalenti. Paesi non
europei o transcontinentali non vengono assegnati automaticamente al continente.
Originali, identificativi e importazioni restano invariati. HTML senza cache e
`build-info.json` permettono di verificare il frontend effettivamente distribuito;
criteri, aggiornamento forzato e verifiche in `docs/EUROPE_GROUPING.md`.

Il pannello Cenni storici ricerca descrizioni italiane da Wikipedia e completa
i testi vuoti o generati, conservando quelli curati. Coda persistente, pausa,
attese della fonte, controllo su modifiche concorrenti, originali, citazioni e
asserzioni pending; nessuna chiamata AI a pagamento. Prova reale isolata:
10 descrizioni aggiornate su 11 sistemi, un caso senza abbinamento idoneo.
Copertura non garantita per l'intero catalogo; istruzioni e criteri in
`docs/HISTORICAL_DESCRIPTIONS.md`.
La ricerca riprova con parole chiave marca/modello e consulta le sezioni di
famiglia collegate dal modello, con originali e attese persistenti per ogni
tentativo. Gestisce i casi PowerBook 180, BBC Model B e Atari 130XE/400/800XL;
un comando dedicato ritenta gli esiti senza testo conservando gli aggiornamenti
già riusciti e lo storico delle ricerche precedenti.
Il ritentativo mirato seleziona i vecchi candidati e i nomi interessati dagli
alias corretti, conservando gli altri esiti. Recuperati nei controlli reali
PDP-1, Epson HX-20, M15, NeXTcube, Atari 800 e Macintosh PowerBook 180;
il pannello rende visibili anche saltate, modifiche e query rifiutate.

Il pannello RAM e varianti recupera capacità documentate (incluso HP 85 da
1000bit) e consolida le denominazioni di configurazione conservando dati,
prezzi e testi per variante. Alias approvati evitano la ricreazione di schede
da importazioni successive; ricerca e assistente mantengono accessibili le
sigle precedenti. Il parser 1000bit riconosce anche le etichette inglesi.
Sul corpus completo: 1.109 → 1.099 schede, 1.261 configurazioni e 3.199 specifiche
conservate; 1.139 righe reimportate invariate. Dettagli in `docs/CATALOG_QUALITY.md`.

Le viste tecniche riuniscono profili regionali e fonti complementari (per esempio
PAL/NTSC e scheda 1000bit dell'Atari 400) in una tabella, deduplicando i dati
equivalenti e mantenendo le differenze qualificate. Le configurazioni hardware
distinte, le fonti, gli ID e gli originali restano conservati; il confronto e
il contesto AI usano la stessa vista. Nessuna migrazione o reimportazione richiesta.
Criteri e verifiche in `docs/TECHNICAL_SHEETS.md`.
La pulizia dei nomi ora vale per ogni produttore/modello: parentesi tonde/quadre
e suffissi video lasciano una scheda principale, con configurazioni e originali
conservati. Include rinomine singole, applicazione in lotti oltre 100 gruppi,
ricerche con nome pulito e prevenzione dei duplicati nelle nuove importazioni.
Le viste pubbliche omettono PAL/NTSC e frequenze video regionali 50/60 Hz.

Per lavorare su due PC, `tools/Transfer-HheArchive.ps1` esporta e ripristina
database PostgreSQL completo e volume fotografico in un archivio portabile.
Il ripristino verifica SHA-256 e versione del codice, crea il backup della
destinazione, carica il dump in un database separato e cambia quello attivo
solo dopo il completamento. Nessun nuovo endpoint HTTP o requisito Python
sul PC Windows. I backup locali restano esclusi da Git;
istruzioni in `docs/BACKUP_TRANSFER.md`.

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

1000bit: implementata l'estrazione dalla scheda HTML reale Amiga 1200 fornita
dall'operatore, con upload HTML/JSON, retry, CLI e recupero di 1–5 URL espliciti.
Anteprima obbligatoria, aggiornamento dei soli modelli esistenti predefinito,
fonti per ogni specifica e originali verificabili. Alias Commodore attestato,
RAM con unità ambigue conservata, CPU opzionali nelle note, produzione distinta
dalle date commerciali e prezzi privi di data separati dai lanci già presenti.

Prova reale su PostgreSQL isolato: Amiga 1200 aggiornato, sette specifiche e due
note aggiunte, una fonte; 1.105 modelli prima e dopo e replay invariato. Zero
prezzi nel file reale, nessuna verifica automatica. Il recupero live rimane
bloccato dal proxy cloud; nessuna API o copertura dell'intero database 1000bit
viene dichiarata. Browser verifica HTML, associazione, replay, fonti e mobile.
Istruzioni, mappature e limiti in `docs/1000BIT.md`.

È ora disponibile anche l'arricchimento automatico dell'intero catalogo da
1000bit: visita dei collegamenti dell'indice, coda persistente, aggiornamenti
univoci senza nuovi modelli, limiti e pause, ripresa dopo ricaricamento e
resoconto completo. I caricamenti singoli restano facoltativi. Tre tabelle
additive incluse nella migrazione ripetibile; reset e richieste concorrenti
non possono riattivare una vecchia sessione. Nessun nuovo requisito Python.

Verifiche attuali: 268 test SQLite più uno specifico PG saltato, 269 PostgreSQL,
25 frontend, build React e browser di importazione/reset e raccolta automatica.
Test di scala con 1.105 modelli; sito remoto simulato e coda verificata dopo
pausa/riapertura. Il proxy cloud continua a impedire la visita reale di 1000bit:
nessun dato storico nuovo viene dichiarato recuperato in massa. La copertura
effettiva della prima visita locale è esportabile nel resoconto.

Correzione della ricerca fotografica bloccata: l'errore Commons
`urlparamnormal` produce un solo nuovo tentativo della stessa ricerca senza
ridimensionamento. Formati, crediti e licenze restano filtrati. Il pannello
mostra il modello corrente e permette di correggere la ricerca o saltarlo;
le ricerche con sintassi rifiutata hanno una semplificazione limitata, mentre
limiti, guasti remoti e risposte sconosciute conservano la macchina in pausa.
La ripresa rispetta lease e `Retry-After`, inclusi quelli espressi come data.
Nessuna nuova migrazione e nessuna sostituzione delle foto esistenti.

Verifiche della correzione: 303 test SQLite più uno specifico PG saltato,
304 PostgreSQL, 26 frontend, build React, Compose e smoke sul catalogo
isolato di 1.105 schede. Chromium verifica fallback miniature, 429, salto,
modifica, ricaricamento/ripresa, foto conservata e layout a 320 px. Risposte
Commons sintetiche: il caso reale `urlparamnormal` è stato diagnosticato sul
computer dell'operatore, ma la richiesta live dal cloud resta bloccata dal
proxy. Dettagli e comandi per il progetto Compose attivo nella guida foto.

Ricerca fotografica completa: comando per ricominciare su tutte le schede
attuali e aggiornare anche le copertine già presenti, con stringa condivisa
`marca - modello` e rimozione dei prefissi noti ripetuti. Le sostituzioni
avvengono dopo un risultato utilizzabile; galleria, dati storici e foto senza
sostituto restano conservati. Immagini già presenti vengono riutilizzate con
metadati Commons aggiornati, senza duplicarle. Coda precedente resa inattiva,
cooldown mantenuto e risposte tardive invalidate. Migrazione additiva automatica
e ripetibile del flag di sostituzione; le vecchie code restano in modalità
solo mancanti fino al nuovo avvio esplicito.

Verifiche: 325 test SQLite più uno specifico PG saltato, 326 PostgreSQL,
26 frontend e build React; ripetuti i 46 test fotografici SQLite/PG dopo
l'ultima modifica ai metadati. Browser con sostituzione, pausa/riapertura,
ricerca manuale e layout mobile. Compose con nuova coda da 1.105 modelli
sul corpus isolato, senza modificare schede o foto durante la preparazione;
zero richieste reali Commons. Nessun accesso al database Windows dell'utente.

Gestione del catalogo: sezione Produttori con creazione, modifica di nome,
paese/data di fondazione/sito, conteggio delle schede ed eliminazione protetta
dei produttori non utilizzati. I nomi duplicati sono controllati anche senza
distinzione di maiuscole e spazi. L'editor dei calcolatori offre eliminazione
con conferma; fonti, originali ETL e uno snapshot dei metadati restano nell'audit.
Candidati e corrispondenze delle importazioni vengono invalidati, le code
fotografiche saltano la scheda e la selezione del confronto viene aggiornata.
Il catalogo resta vuoto dopo il riavvio se viene eliminata l'ultima scheda.
Nessuna modifica allo schema o migrazione aggiuntiva.

Verifiche: 340 test PostgreSQL, 339 SQLite più uno specifico PG saltato,
27 frontend, build React e Compose. Nuova suite browser inclusa in CI per
CRUD, duplicati, produttori usati, conferma/annullamento, rimozione dei computer,
confronti, persistenza e layout mobile. Prova sul corpus isolato, eliminando
soltanto i record sintetici creati dalla suite; nessun accesso al database utente.
Ripetuta anche la suite browser precedente: importazioni, conflitti, revisioni,
1000bit HTML e confronto superati con il pannello amministrativo aggiornato.

1000bit ora abbina insieme marca e modello con normalizzazione specifica della
fonte: paesi riconosciuti nelle annotazioni della marca, spazi/trattini e
prefissi del produttore. Il caso segnalato `Fujitsu (Japan) · FM 11 EX` trova
la scheda `Fujitsu · FM-11 EX`, senza rinominarla o creare un nuovo produttore.
Sigle, numeri, +, /, punti e divisioni non geografiche restano significativi;
le collisioni sono in revisione anche se aggiunte al catalogo dopo l'avvio.
Il pannello permette di ritentare i soli URL non abbinati di una visita
precedente, preservando risultati, snapshot e cooldown. Anche gli originali
delle nuove pagine non abbinate restano nell'audit con un motivo leggibile.

Verifiche: suite complete 367 PostgreSQL, 366 SQLite più uno specifico PG
saltato e 27 frontend. Ripetuti 48 test matching/raccolta SQLite e PG dopo
l'ultima guardia sulle collisioni. Build e Compose riusciti; browser su
frontend compilato verifica il recupero della sola scheda 935 da una sessione
precedente, risultati conservati e mobile. Zero collisioni nelle nuove chiavi
dei 1.105 modelli di base; lettura sul corpus PostgreSQL trova il Fujitsu.
La fixture 935 ricostruisce soltanto i nomi e l'URL forniti dall'operatore;
1000bit live resta bloccato dal proxy. Nessun nuovo dato tecnico storico
recuperato o dichiarato verificato e nessuna modifica allo schema.

Prezzi da ricerca: aggiunta la fonte **Prezzi storici (Excel / CSV / JSON)**,
con caricamento diretto XLSX del foglio principale, anteprima ed esito. Sono
consentiti solo aggiornamenti di schede esistenti, abbinati per marca/modello,
senza interpretare gli ordinali Excel come ID del database. Il lettore non
esegue formule o segue URL, riallinea soltanto le rotazioni inequivocabili delle
colonne e conserva l'originale binario, l'impronta e i valori per riga. Nessuna
nuova dipendenza o migrazione. Valuta, mercato, configurazione, imposte e
varianti restano tracciati; l'anno non diventa automaticamente data di lancio.
Famiglie/varianti diverse e indicazioni parziali restano note. Gli URL sono
riferimenti da verificare; la fiducia dichiarata nel foglio non marca i dati
come verificati e non viene inventata una data di consultazione della fonte.

Sul file ricevuto: 569 prezzi riportati, 22 listini successivi, 12 note,
502 righe senza importo escluse e 19 disallineamenti di colonne corretti.
Nel test PostgreSQL tutte le 603 righe sono abbinate, 591 prezzi aggiunti,
3.594 asserzioni pending e replay di 603 invariati. Hash delle tabelle
protette invariati; transazione di prova annullata. Il database Windows
non è stato raggiunto. Corretto anche l'elenco esportato che aveva rimosso
slash da alcune sigle; l'abbinamento prezzi supporta il file precedente senza
rinominare i sistemi. L'Excel e i risultati normalizzati non sono pubblicati
nel repository: i test usano esclusivamente prezzi sintetici.

Verifiche: suite complete 394 PostgreSQL, 393 SQLite più uno specifico PG
saltato e 27 frontend. Ripetuti i 27 test prezzi su entrambi i database dopo
l'ultimo controllo numerico. Build/Compose e browser per anteprima, report,
download XLSX, applicazione, replay e mobile riusciti. CI estesa con la prova
browser dei prezzi. Accesso live alle fonti campione bloccato dal proxy:
nessun prezzo dichiarato storicamente verificato. Guida in `docs/HISTORICAL_PRICES.md`.
