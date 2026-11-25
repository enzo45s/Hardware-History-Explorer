# Corpus multimarca MAME 0.276 — 1.139 schede candidate

Pacchetto pronto per **CSV / JSON autorizzato** di Hardware History Explorer.
Contiene **1.139 schede**, **189 denominazioni di produttori**, **1.251
configurazioni emulabili** e **3.184 specifiche con citazione**. Anni dichiarati:
**1961–2020**. Nessuna chiave API e nessuna installazione MAME sono necessarie
per caricare i file già pronti.

È un corpus ampio per provare catalogo ed ETL. **Non è un archivio storico
completo o verificato di commercializzazioni.** MAME descrive anche famiglie,
revisioni e configurazioni emulabili: una registrazione non prova da sola che
sia un modello commerciale distinto. I filtri escludono i casi fuori ambito
identificati, ma resta necessaria una revisione editoriale.

## Cosa contiene davvero

| Campo | Copertura |
|---|---:|
| Fonte MAME identificata e originale conservato | 1.139 / 1.139 |
| Anno numerico dichiarato nel registro | 1.062 / 1.139 |
| Modello di processore emulato | 1.110 / 1.139 |
| Clock configurato nell'emulatore | 1.110 / 1.139 |
| RAM predefinita configurata nell'emulatore | 653 / 1.139 |
| Prezzi | **0** |
| Vendite, recensioni e fotografie importate | **0** |
| Verifiche storiche automatiche | **0** |

I 77 anni mancanti/incerti restano ignoti. L'anno del registro viene conservato
con precisione annuale e una citazione che ne esplicita la provenienza; non è
una verifica della prima disponibilità commerciale, del mercato o della data
giornaliera. Le categorie puntuali e le descrizioni storiche non sono state
inventate: il gruppo generico è **Calcolatore**.

Dal 14 novembre è disponibile un [completamento editoriale delle categorie](../../CLASSIFICATION.md)
per le schede già caricate: riconosce 610 schede, lasciandone 529 generiche.
Si applica dal pannello Importazioni senza nuovi upload. Le assegnazioni sono
da verificare e non cambiano gli originali o le impronte dei cinque lotti.
Le [foto automatiche Commons](../../AUTOMATIC_PHOTOS.md) sono un'operazione
separata, avviata dall'operatore; questi JSON continuano a non contenere immagini.

È disponibile anche la [rifinitura del catalogo esistente](../../CATALOG_REFINEMENT.md):
34 schede regionali accorpabili in 22 gruppi, descrizioni italiane e dati
aggiuntivi tramite uno snapshot separato. I cinque lotti originali restano
invariati; non vanno ricaricati per ottenere l'arricchimento. Il totale dopo
questo accorpamento esplicito è 1.105, con tutte le configurazioni regionali
conservate. I cinque prezzi IBM RT appartengono al pacchetto aggiuntivo,
non a questi file originali.

Le proprietà tecniche sono deliberatamente esplicite:

- **CPU · Modello emulato (MAME)**;
- **CPU · Frequenza emulata (MAME)**, espressa in MHz;
- **RAM · Capacità predefinita (MAME)**, espressa in KiB.

Queste proprietà restano distinte da **Modello**, **Frequenza** e **Capacità**
storiche già presenti. Una configurazione MAME non dimostra che quel quantitativo
di RAM fosse ordinabile al lancio. Per esempio, il default emulato del PC 5150
è 640 KiB: **non va interpretato come RAM del modello base venduto nel 1981**.
Anche i clock possono essere scelte o approssimazioni dell'emulatore.

Le altre opzioni RAM dell'export sono conservate nella descrizione e negli
originali, senza trasformarle automaticamente in configurazioni commerciali.
Lo stato `good` del driver MAME riguarda l'emulazione, non la verifica storica.

## Come provarlo su Windows

Nella cartella del progetto e sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
```

Mantieni il nome Compose della tua istanza; ometti `-p hhe-import-test` se
prima avviavi senza. Premi Ctrl+F5. La ricostruzione aggiorna anche il
riconoscimento dei valori testuali del processore emulato.

1. Conserva un backup del database e delle foto.
2. Per una prova pulita, usa una sola volta **Amministrazione → Importazioni →
   Svuota archivio per un nuovo import**, come nella [guida al reset](../../ARCHIVE_RESET.md).
3. In **Fonte dati** scegli **CSV / JSON autorizzato**.
4. Carica `batch-01.json`, conferma i diritti di riutilizzo e prepara l'anteprima.
   Controlla nomi, configurazioni, anno, fonte ed eventuali righe da escludere.
5. Applica le righe che hai deciso di mantenere. Procedi poi con gli altri
   quattro file, **senza svuotare il catalogo fra i lotti**.
6. Apri schede, timeline, confronti e **Fonti e verifiche**. Nessun dato viene
   promosso automaticamente a verificato.

| File da caricare | Schede nel file | Totale atteso, partendo da zero |
|---|---:|---:|
| [batch-01.json](batch-01.json) | 250 | 250 |
| [batch-02.json](batch-02.json) | 250 | 500 |
| [batch-03.json](batch-03.json) | 250 | 750 |
| [batch-04.json](batch-04.json) | 250 | 1.000 |
| [batch-05.json](batch-05.json) | 139 | **1.139** |

I file vanno da circa 1,14 a 2,59 MB, sotto il limite di 8 MB e 1.000 record
per upload. Questi conteggi valgono applicando tutte le righe a un catalogo
vuoto; esclusioni o schede già presenti cambiano gli esiti.

**Non caricare `manifest.json` o `coverage.csv`: sono file di consultazione.**
Non scegliere RetroFlops: il pacchetto è già nel formato canonico del progetto.
Non ricaricare il precedente campione da 19 modelli per raggiungere questi
conteggi: ha una fonte e una granularità diverse.

Ripetendo gli stessi cinque caricamenti si devono ottenere rispettivamente
250, 250, 250, 250 e 139 **invariati**, con totale fermo a 1.139. Gli upload
ripetuti creano nuovi eventi nello storico, senza aggiungere calcolatori.

## Consultare la copertura prima dell'importazione

[coverage.csv](coverage.csv) è leggibile con Excel: UTF-8 con BOM e separatore
`;`. Elenca tutte le schede, gli anni riportati e i dati **emulati** effettivamente
disponibili. I campi mancanti sono vuoti, i prezzi sono segnalati come assenti.
Le celle testuali potenzialmente interpretabili come formule sono neutralizzate;
gli originali restano nei JSON.

[manifest.json](manifest.json) contiene indice completo, conteggi, impronte dei
lotti, normalizzazioni dei produttori, motivi delle esclusioni e provenienza.
Non è un elenco di certificazioni commerciali o di fonti primarie indipendenti.

## Origine, licenze e trasformazioni

- Progetto: **MAMEdev e collaboratori**, <https://github.com/mamedev/mame>.
- Versione: **0.276**, tag `mame0276`, commit
  `758c8a169a44f0ce3abfd28e8b5c44cc49148eba`.
- Export: `mame -listxml`, da **Debian mame 0.276+dfsg.1-1+deb13u1**.
  La dicitura `0.276 (unknown)` nel build identifica l'export del pacchetto,
  non uno stato di verifica dei dati storici.
- Recupero e adattamento: **12 novembre 2026**.
- SHA-256 dell'XML completo, build, copyright individuali e testi di licenza
  sono registrati nei lotti e nel manifest.

Sono state esaminate famiglie di driver di Acorn, Amstrad, Amiga, Apple,
Atari, Commodore, DEC, Epson, Fujitsu, HP, IBM, MSX, NEC, NeXT, Olivetti,
Sharp, Sinclair, Sony, Sun, Tandy e altre. Le registrazioni `COMP` sono
confrontate con la stessa versione dell'export ufficiale; dispositivi e BIOS
non eseguibili non diventano calcolatori.

I filtri escludono prototipi/modifiche dichiarati, trainer, terminali,
periferiche, console identificate, produttori ignoti e costrutti non risolti.
I casi individuati solo dal driver, come Commodore 900 e Dragon Alpha/Beta,
sono esclusi esplicitamente. Non si usa `cloneof`/`parent` per fondere modelli:
parentela nell'emulatore e identità commerciale non equivalgono.

Si accorpano solo produttore normalizzato e denominazioni uguali dopo
qualificatori geografici/firmware espliciti, mantenendo le singole configurazioni.
Qualificatori hardware come `FDHD` restano nel nome. Le normalizzazioni
commerciali sono dichiarate nel manifest; gli originali non sono riscritti.

Ogni lotto conserva metadati XML originali selezionati, dichiarazioni `COMP`,
percorso, riga, copyright e SHA-256 dei file sorgente. Le citazioni rimandano
ai file ufficiali al commit fissato. Sono conservati i testi **BSD-2-Clause,
BSD-3-Clause, GPL-2.0, LGPL-2.1 e CC0**, insieme a `COPYING` di MAME; gli estratti
restano soggetti alle licenze dei file di origine. Le trasformazioni di formato,
selezione e accorpamento sono dichiarate come elaborazione HHE.

**Nessuna ROM, fotografia, copia di manuale o codice compilato è redistribuito.**
I documenti eventualmente citati dal driver non sono stati verificati
indipendentemente in questa sessione.

## Rigenerazione per sviluppatori

Non serve per la prova dell'applicazione. Con Python e le dipendenze backend
già installate:

```bash
git clone --depth 1 --filter=blob:none --no-checkout --branch mame0276 https://github.com/mamedev/mame.git /tmp/mame-hhe
mame -listxml > /tmp/mame.xml
python tools/prepare_mame_dataset.py --source /tmp/mame-hhe --xml /tmp/mame.xml --output /tmp/mame-hhe-batches --distribution "Indicare il pacchetto MAME utilizzato"
```

Il binario deve essere MAME **0.276**, coerente con il commit indicato:
versioni diverse sono rifiutate. Su Windows usa la redirezione di `cmd.exe`
per preservare i byte dell'XML, per esempio `cmd /c "mame.exe -listxml > mame.xml"`.
L'export non richiede ROM. Il clone parziale recupera solo i blob richiesti;
per accelerare la prima esecuzione puoi materializzare le cartelle selezionate
con sparse checkout. Usa una cartella di output nuova: il generatore rifiuta
di sovrascrivere lotti esistenti.

Il generatore legge blob Git, non esegue codice del repository sorgente e
non scrive nel database. Il parser XML rifiuta entità/DTD esterni. Nessuna
API pubblica aggiunta al backend esegue MAME o comandi Git.

## Verifiche del pacchetto

L'importazione completa e il replay sono stati provati tramite API in archivi
isolati. Dettagli, tempi e limiti sono nel [resoconto](VALIDATION.md).
Nessuna importazione o reset è stato applicato al database sul computer dell'utente.
