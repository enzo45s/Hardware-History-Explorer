# Campione reale ampliato: 19 calcolatori

File pronto: **[retroflops-computers-19.json](retroflops-computers-19.json)**,
circa 550 kB. Formato **JSON canonico Hardware History Explorer**, non
esportazione RetroFlops. Include **19 modelli, 26 configurazioni e 70 specifiche**
con fonte: denominazioni CPU e misure CPU/RAM disponibili. Non rappresenta
tutte le configurazioni ordinabili o tutta la storia dei sistemi elencati.

## Prova su Windows

Nella cartella del progetto, sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
```

Usa il nome del progetto Compose della tua istanza di prova, se diverso.
La ricostruzione serve anche ad aggiornare normalizzazione e interfaccia.

1. Apri **Amministrazione → Importazioni**.
2. Seleziona **CSV / JSON autorizzato**, perché il file è già adattato al
   formato del progetto. Il selettore RetroFlops richiede invece l'export originale.
3. Carica `docs/examples/retroflops-computers-19.json`, conferma la licenza
   CC BY 4.0 conservata nello snapshot e prepara l'anteprima.
4. **Prima di applicare**, controlla le corrispondenze. Nel catalogo
   dimostrativo standard associa manualmente queste quattro righe:

| Nome nel file | Scheda già presente |
|---|---|
| Apple II (Apple Computer) | Apple II (Apple) |
| Apple Macintosh 128K (Apple Computer) | Macintosh 128K (Apple) |
| Commodore 64 (Commodore Business Machines) | Commodore 64 (Commodore) |
| IBM Personal Computer 5150 | IBM PC 5150 |

Il motore non presume che ragioni sociali o nomi simili siano sinonimi.
Non associare **IBM System/360 Model 50** alla scheda generica **System/360**:
una famiglia non equivale a un suo specifico modello. **PDP-8** e **PDP-11**
sono sistemi diversi. Se il tuo archivio è diverso dal seed, controlla tutte
le corrispondenze e applica solo quelle corrette.

5. Applica le righe pronte e apri **Fonti e verifiche**. Le differenze di nome,
   produttore e descrizione richiedono una decisione umana; la citazione del
   manuale è mostrata separatamente dal dato contestato. Nessun dato viene
   verificato automaticamente.
6. Ripeti il caricamento: il numero dei calcolatori deve rimanere invariato.

## Contenuto e limiti

Sono informazioni **riportate dal dataset secondario RetroFlops**, senza
verifica indipendente dei documenti primari in questa sessione.

| Modello | Identificativo RetroFlops |
|---|---|
| Acorn Archimedes A310 | acorn-archimedes-a310 |
| Amiga 1200, 4000, 500 | amiga-1200, amiga-4000, amiga-500 |
| Amstrad CPC 464 | amstrad-cpc-464 |
| Apple II | apple-ii |
| Apple Mac mini M1, M4 | apple-mac-mini-m1, apple-mac-mini-m4 |
| Apple Macintosh 128K | apple-macintosh-128k |
| Atari 520ST, 800 | atari-520st, atari-800 |
| BBC Micro Model B | bbc-micro-model-b |
| Commodore 64 | commodore-64 |
| DEC PDP-8 | dec-pdp-8 |
| IBM PC 5150 | ibm-pc-5150 |
| IBM System/360 Model 50 | ibm-system-360-model-50 |
| Raspberry Pi 5 | raspberry-pi-5 |
| SGI Octane | sgi-octane |
| ZX Spectrum 48K | zx-spectrum-48k |

La data del Mac mini M1 è esplicitamente descritta dalla fonte come annuncio:
diventa `announcement_date`, senza inventare una data di commercializzazione.
Le sue due frequenze CPU appartengono ai core prestazioni ed efficienza:
restano separate, senza generare un falso conflitto. I valori `rumored` o
ignoti non diventano numeri/stime attendibili. Descrizioni con segnaposto
irrisolti sono omesse dai record e conservate negli originali.

Sono esclusi sistemi Intel di riferimento, lo standard generico MSX e record
che non descrivono un modello concreto di calcolatore. Nessun prezzo, dato
mancante, fotografia o contenuto di manuale è stato inventato/importato.
RAM e ROM rimangono distinte; unità storiche ambigue come KB non diventano KiB.

## Provenienza e riproduzione

- Archivio/autore: **RetroFlops**, <https://github.com/retroflops/retroflops>.
- Licenza della compilazione e dei metadati: **CC BY 4.0**,
  <https://creativecommons.org/licenses/by/4.0/>.
- Commit: `fbbed6181149b997329854e5808e0d036ad769e2`.
- Recupero: **12 novembre 2026**.
- Adattamenti: selezione dei modelli e delle misure documentate, conversione
  YAML → JSON canonico, etichette italiane, distinzione parti CPU e date.

Le singole voci citano il file ufficiale al commit indicato. Le evidenze
conservano misure, qualificatori e manifesti dei documenti citati. `_metadata`
include **141 file originali UTF-8 con SHA-256**, fra licenza, sistemi,
componenti, misure e manifesti. Le unità e i valori originali sono conservati
nel JSON distribuito; la vista normalizzata del catalogo usa MHz e KiB dove
la conversione è esplicita. I diritti sui documenti primari restano dei
rispettivi titolari: la licenza del catalogo non si estende ai manuali.

Per rigenerare il file con le dipendenze backend bloccate già installate:

```bash
git clone --filter=blob:none --sparse https://github.com/retroflops/retroflops /tmp/retroflops
python tools/prepare_retroflops_sample.py --source /tmp/retroflops --output docs/examples/retroflops-computers-19.json
```

Lo script legge blob Git dal commit fissato, verifica la licenza, valida i
record e produce solo un file. Non esegue codice upstream, non scarica i
documenti citati e non scrive nel database. Non è uno scraper generalista.

## Verifiche dell'importazione

Prova con API reale e database SQLite temporaneo separato, partendo dal seed
di 10 sistemi e dal precedente campione di quattro modelli già importato:

- Anteprima ampliata: **19 righe pronte**, dopo le quattro associazioni esplicite.
- Applicazione: **11 importati, 4 aggiornati, 4 invariati**; totale **25** schede.
- Nuovo caricamento: **19 invariati**, totale ancora **25**.
- **7 conflitti editoriali**: produttore Apple II; nome/produttore/descrizione
  Macintosh 128K; produttore Commodore 64; nome/descrizione IBM PC 5150.
- Nessun conflitto quantitativo; **0 asserzioni verificate automaticamente**.
- Identificativi delle configurazioni e specifiche dei quattro modelli
  precedenti conservati. Frequenze M1 e annuncio conservati correttamente.

I conteggi cambiano se il catalogo iniziale è diverso. Nessuna importazione
è stata applicata al database sul computer dell'utente.
