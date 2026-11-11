# Campione reale: quattro home computer

File pronto: **`retroflops-home-computers-4.json`**, versione 2, circa 97 kB.
Formato **JSON canonico Hardware History Explorer**, non esportazione RetroFlops.

## Come provarlo su Windows

Nella cartella del progetto, sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
```

Non serve ricostruire Docker per caricare il JSON aggiornato: usa il formato
canonico già supportato dall'importatore. Avvia la tua istanza di prova come
già fatto. Per aggiornare anche l'adattatore automatico RetroFlops, che ora
crea una voce CPU · Modello dai componenti disponibili, ricostruisci il
progetto di prova dopo il pull:

```powershell
docker compose -p hhe-import-test up --build -d
```

1. Apri **Amministrazione → Importazioni**.
2. In **Fonte dati**, scegli **CSV / JSON autorizzato**. Non scegliere
   RetroFlops: quel selettore si aspetta l'esportazione originale dell'archivio,
   mentre questo file è già adattato al formato del progetto.
3. Carica `docs/examples/retroflops-home-computers-4.json`.
4. Conferma i diritti di riutilizzo: il campione conserva attribuzione e licenza
   CC BY 4.0 del catalogo RetroFlops.
5. Premi **Prepara anteprima dal file**, controlla le quattro righe e applicale.

Nel database dimostrativo standard i quattro modelli sono nuovi: l'esito atteso
è **4 importati**. Ripetendo il caricamento: **4 invariati**, senza duplicati.
Se hai già inserito questi sistemi, controlla prima le corrispondenze.

Se avevi importato la prima versione di questo campione (solo frequenze e RAM),
carica il file aggiornato: l'esito atteso è **4 aggiornati**, con i modelli CPU
aggiunti alle cinque configurazioni esistenti. Un ulteriore caricamento produce
**4 invariati**. Non occorre eliminare o ricreare i calcolatori e non serve
ricostruire Docker per questa reimportazione del JSON canonico.

## Contenuto

Le seguenti sono informazioni **riportate dal dataset RetroFlops**, non
verificate indipendentemente sui documenti primari in questa sessione.

| Modello | Lancio dichiarato | Configurazione | Modello CPU | Frequenza CPU | RAM |
|---|---|---|---|---|---|
| Amstrad CPC 464 | 1984-06 | PAL retail machine | Zilog Z80A | 4 MHz | 64 KiB |
| Atari 800 | 1979-11 | NTSC, 48 KiB RAM | MOS Technology 6502 | 1,79 MHz | 48 KiB |
| Atari 800 | 1979-11 | PAL, 48 KiB RAM | MOS Technology 6502 | Non inclusa | 48 KiB |
| BBC Micro Model B | 1981-12 | Retail Model B | MOS Technology 6502 | 2 MHz | 32 KiB |
| ZX Spectrum 48K | 1982-04 | PAL 48K | Zilog Z80A | 3,5 MHz | 48 KiB |

Totale: **4 modelli, 5 configurazioni, 9 specifiche numeriche e 5 specifiche
testuali CPU · Modello con fonte**. I modelli CPU sono tratti dai record
canonici dei componenti; non vengono dedotti dalle frequenze o dall'architettura.
Le configurazioni sono quelle selezionate dalla fonte; non rappresentano tutte
le opzioni ordinabili dei quattro modelli. Le date sono quelle del catalogo
secondario e non attestano da sole disponibilità commerciale in tutti i mercati.

La frequenza PAL dell'Atari è esclusa perché la fonte la classifica `rumored`.
ROM, GPU, quantità ignote e misure aggregate non sono state importate come RAM.
`KiB` non è convertito in `KB`. Nessun prezzo, fotografia o dato mancante è
stato inventato. Tutte le asserzioni iniziano **pending / Da verificare**,
indipendentemente dallo stato editoriale dell'archivio originale.

## Provenienza e riutilizzo

- Autore e archivio: **RetroFlops**, <https://github.com/retroflops/retroflops>.
- Licenza della compilazione e dei metadati: **CC BY 4.0**,
  <https://creativecommons.org/licenses/by/4.0/>.
- Revisione consultata: `fbbed6181149b997329854e5808e0d036ad769e2`.
- Data del recupero: **12 novembre 2026**.
- Adattamenti: selezione dei modelli, delle denominazioni CPU e delle misure CPU/RAM, etichette italiane,
  conversione del formato YAML originale in JSON canonico, esclusione delle
  misure incerte. Numeri, unità, nomi e precisione delle date conservati.

Ogni modello e specifica cita il file ufficiale alla revisione indicata. Le
specifiche conservano identificativo della misura, metodo, livello dichiarato
dalla fonte, localizzatori e riferimenti ai documenti citati.

Il blocco `_metadata` include le copie UTF-8 e gli SHA-256 dei **21 file originali**
consultati (licenza, sistemi, componenti CPU, misure e manifesti delle fonti). È conservato
integralmente nello storico dell'upload, separatamente dai record normalizzati.
Non sono state scaricate né redistribuite fotografie o copie dei manuali.
I documenti primari citati conservano i diritti dei rispettivi editori: la
licenza del catalogo non attribuisce una licenza sui manuali.

## Controlli realmente eseguiti

Contro l'API reale in un database SQLite temporaneo separato:

- Anteprima: **4 righe pronte**.
- Prima applicazione: **4 importati**, catalogo dimostrativo da 10 a 14 modelli.
- Seconda applicazione: **4 invariati**, catalogo fermo a 14.
- Ogni specifica ha una fonte; **0 conflitti**, **0 asserzioni verificate**.
- Schede dettagliate e API confronto dei quattro modelli funzionanti.
- Due configurazioni Atari conservate; nessuna frequenza CPU assegnata alla PAL.

Verificata inoltre la sequenza **versione 1 → versione 2 → ripetizione versione 2**:
4 importati, 4 aggiornati, 4 invariati. Identificativi dei calcolatori, delle
configurazioni e delle nove specifiche numeriche preservati. Le nuove cinque
voci testuali CPU sono visibili nelle schede e nel payload dell'API confronto,
tutte corredate di fonte e senza conflitti automatici.

Non è stata applicata alcuna importazione al database sul computer dell'utente.
