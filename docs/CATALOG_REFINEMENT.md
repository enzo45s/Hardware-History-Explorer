# Rifinitura del catalogo — 14 novembre 2026

Questa versione arricchisce le schede già esistenti. Non avvia nuovi import
all'avvio, non svuota l'archivio e non richiede nuovi caricamenti dei cinque
JSON MAME. Non aggiunge nuovi modelli tramite l'azione di arricchimento.

## Come applicarla su Windows

Sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
docker compose up --build -d
```

Mantieni l'eventuale nome progetto `-p` della tua istanza. Conserva un backup
del database e delle fotografie; non usare `down -v` né **Svuota archivio**.
Premi Ctrl+F5 e apri **Amministrazione → Importazioni → Rifinisci catalogo:
varianti regionali, descrizioni e dati**.

1. **Anteprima varianti regionali** elenca i gruppi e la scheda da mantenere.
2. **Accorpa le varianti regionali proposte** trasferisce i dati nelle schede
   mantenute, conservando gli originali nello storico delle riconciliazioni.
3. **Anteprima arricchimento** mostra la copertura e alcuni esempi di descrizioni.
4. **Applica arricchimento ai sistemi esistenti** elabora l'archivio in lotti
   da 100 schede. Mantieni aperta la sezione; puoi fermarti dopo il lotto corrente.
5. Controlla schede e **Ultime importazioni → Fonti e verifiche**. Le asserzioni
   restano da verificare. Eventuali conflitti mantengono il valore preesistente.

Puoi ripetere l'arricchimento dopo un'interruzione: crea nuovi eventi di audit
ma riusa i dati già presenti. Le descrizioni esistenti, anche scritte a mano,
sono conservate. Le righe riferite a schede rimosse nel frattempo vengono
saltate invece di ricreare il calcolatore.

## Varianti regionali

Le regole rimuovono solo qualificatori geografici/linguistici espliciti dai
confronti d'identità, anche quando compaiono con revisioni nello stesso gruppo:

- `Apple //c (rev 4, France)` e `Apple //c (rev 4, Germany)` corrispondono
  alla stessa revisione `Apple //c (rev 4)`;
- `Apple //c` e `Apple //c (rev 4)` restano distinti;
- `Macintosh SE` e `Macintosh SE (FDHD)` restano distinti;
- capacità, codici modello e piattaforme hardware non vengono rimossi.

Nel pacchetto originale da 1.139 schede si riconoscono **22 gruppi**, con
**34 schede ridondanti**: dopo l'accorpamento restano **1.105 sistemi**.
Altre differenze di denominazione non vengono considerate automaticamente
equivalenti. Un sistema con un qualificatore regionale ma senza una seconda
scheda equivalente non viene eliminato.

Configurazioni regionali, specifiche, foto, mercati/prezzi, fonti, identità
esterne e riferimenti delle importazioni vengono trasferiti mantenendo gli ID.
Anche la coda fotografica segue la scheda mantenuta. Le configurazioni non
vengono distrutte o fuse sulla base di valori simili. La transazione completa
è atomica e l'anteprima diventa invalida se i dati cambiano prima dell'applicazione.

Se si arricchisce prima di accorpare, i dati condivisi di un modello vengono
assegnati a una sola delle schede equivalenti, evitando di moltiplicarne le
configurazioni in ogni variante regionale. L'ordine consigliato resta quello sopra.

## Copertura reale del pacchetto

| Informazione | Disponibilità nello snapshot |
|---|---:|
| Descrizioni italiane | Sintesi per tutte le schede che ne sono prive |
| Descrizioni curate su documentazione specifica | 44 modelli |
| Modelli con ulteriori dati nello snapshot | 1.089, dopo l'accorpamento |
| Configurazioni documentali aggiuntive | 57 |
| Specifiche da documentazione/AppleDB | 105 |
| Ulteriori specifiche esplicitamente emulate | 3.891 |
| Voci di rilascio/documentazione aggiuntive | 40 |
| Modelli con prezzo nello snapshot | **5, tutti IBM RT PC** |

Le 3.891 specifiche emulate comprendono 1.239 risoluzioni, 1.239 frequenze
video, 744 elenchi di opzioni RAM e 669 elenchi di chip audio. Restano nelle
configurazioni MAME originali, con nomi che esplicitano la natura emulata.
Non sono presentate come configurazioni ordinate al lancio. Rumori floppy,
cassette, speaker, slot e filtri software dell'emulatore non diventano
ulteriori chip audio fisici.

Le 105 specifiche documentali comprendono codici modello AppleDB, informazioni
su RAM, floppy, video, espansioni e interfacce di alcuni Macintosh e IBM.
Queste informazioni sono in configurazioni documentali distinte dai default
MAME. Le note delle configurazioni sono ora visibili nelle schede e nei confronti.

### Prezzi effettivamente trovati

| Modello | Importo | Valuta/mercato | Periodo riportato |
|---|---:|---|---|
| IBM RT PC Model 010 | 11.700 | USD, Stati Uniti | 1986-01 |
| IBM RT PC Model 015 | 10.050 | USD, Stati Uniti | 1986-11 |
| IBM RT PC Model 020 | 14.945 | USD, Stati Uniti | 1986-01 |
| IBM RT PC Model 025 | 17.940 | USD, Stati Uniti | 1986-01 |
| IBM RT PC Model A25 | 19.510 | USD, Stati Uniti | 1986-01 |

Fonte realmente letta: [tabella nel driver IBM RT PC MAME](https://github.com/mamedev/mame/blob/758c8a169a44f0ce3abfd28e8b5c44cc49148eba/src/mame/ibm/rtpc.cpp#L18).
La valuta USD e il mercato statunitense derivano dal contesto dei rimandi agli
annunci IBM **ENUS** riportati accanto alla tabella. Gli annunci primari non
sono stati riletti da questa rete. Tipo: **prezzo riportato**, senza promozione
automatica a prezzo di lancio/MSRP verificato. Nessuna conversione valutaria,
attualizzazione per inflazione o stima dei prezzi mancanti.

**Non è un arricchimento storico completo di 1.105 modelli.** La copertura dei
prezzi resta molto limitata; la maggioranza dei dati tecnici aggiuntivi proviene
dall'emulatore. Per gli altri modelli i prezzi restano assenti.

## Descrizioni italiane

Per 44 modelli lo snapshot contiene testi italiani curati ricavati dai dati
AppleDB e dai commenti tecnici MAME realmente letti. Per le altre schede viene
costruita una breve sintesi deterministica di produttore, categoria registrata,
anno attribuito da MAME e CPU emulate disponibili. Non serve un servizio AI.

Queste sintesi non inventano primati, diffusione, vendite, successo commerciale
o destinazioni d'uso non documentate. Non trasformano l'anno di un registro
MAME in una data commerciale verificata. Sono un accompagnamento leggibile
dei dati disponibili, non una ricerca storica indipendente su ogni modello.

## Fonti, originali e riuso

- **AppleDB**, MIT, copyright 2022 emiyl; commit
  `5fb98e557f544b7ed783e7855e78c9db9d05ee57`. JSON individuali con date di
  rilascio, codici modello ed eventuali identificativi/architetture. Nessuna
  foto, firmware o accessorio copiato nel catalogo.
- **MAME 0.276**, commit `758c8a169a44f0ce3abfd28e8b5c44cc49148eba`:
  commenti documentali di driver BSD-3-Clause ed export ufficiale `-listxml`
  già verificato per il corpus. Le informazioni emulate rimangono separate.
- **Wikidata**, dati strutturati CC0: adattatore esteso e testato con fixture;
  nessun nuovo record reale recuperato in questa sessione per il blocco di rete.

Lo snapshot è in `backend/app/importing/data/catalog-enrichment-v1.json`.
Contiene record normalizzati, originali selezionati, riferimenti al commit,
righe degli estratti, SHA-256, copyright e testi di licenza. Non caricarlo come
un normale JSON di importazione: il pannello lo usa internamente e suddivide
le operazioni in lotti, associandole esclusivamente alle schede esistenti.
Ogni lotto conserva anche gli originali delle fonti utilizzate nell'audit.
Non sono distribuite ROM, immagini, manuali completi o binari MAME.

Il generatore per sviluppatori è `tools/prepare_catalog_enrichment.py`:

```bash
python tools/prepare_catalog_enrichment.py --mame /percorso/mame --appledb /percorso/appledb --xml /percorso/mame.xml --output /tmp/catalog-enrichment-v1.json
```

I commit sono fissati nel codice; l'XML deve avere la stessa impronta
dell'export originale del corpus. La data di preparazione/accesso cambia nelle
rigenerazioni successive. Non esegue codice dei repository sorgente e non
scrive nel database.

## Wikidata e ulteriori ricerche

Il proxy cloud impedisce l'accesso a Wikipedia/Wikidata e ad alcuni archivi:
non è stato aggirato, e non è stato eseguito scraping massivo.
Per proseguire la ricerca live occorre l'accesso alle API ufficiali.

L'adattatore Wikidata ora conserva descrizioni italiane, CPU (`P880`), sistema
operativo (`P306`), misure con unità risolte e prezzi (`P2284`). Le valute sono
ricavate dal codice ISO 4217 (`P498`) dell'entità valuta, senza dedurle dal solo
simbolo `$`. La definizione di `P2928` viene verificata prima di trattarla come
capacità di memoria. Statement e riferimenti originali restano nell'audit.

Solo un prezzo univoco, senza qualificatori e con valuta risolta viene
riportato nel campo prezzo. Prezzi multipli, qualificati o senza valuta risolta
diventano **Note e dati contestuali** con citazione, senza una falsa data di
lancio. `P585` non viene usato per inventare una prima commercializzazione e
`P571` resta distinto dalla data di rilascio.

Dal computer dell'operatore si può usare **Fonte dati → Wikidata** con QID
noti, controllando l'anteprima e associando ciascuna riga al modello esistente
prima di applicarla. Questa funzione generale può inserire nuove schede:
per mantenere invariato il catalogo controlla gli abbinamenti. L'arricchimento
locale da snapshot, invece, impone sempre la modalità `existing_only`.

## Verifiche

Test automatici per qualificatori geografici, separazione delle revisioni,
conservazione dei dati e degli ID, audit e coda foto, anteprime non più valide,
arricchimento senza nuovi modelli, descrizioni manuali, riesecuzione e prezzi
Wikidata con ambiti/valute non risolti. Risultati e prova integrata del corpus
sono riportati nel [resoconto di validazione](CATALOG_REFINEMENT_VALIDATION.md).
