# Campione reale: quattro home computer

File pronto: **`retroflops-home-computers-4.json`**, circa 84 kB.
Formato **JSON canonico Hardware History Explorer**, non esportazione RetroFlops.

## Come provarlo su Windows

Nella cartella del progetto, sul branch `feat/historical-data-import`:

```powershell
git pull --ff-only
```

Non serve ricostruire Docker per caricare questo nuovo file: il codice
dell'importatore non cambia. Avvia la tua istanza di prova come già fatto.

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

## Contenuto

Le seguenti sono informazioni **riportate dal dataset RetroFlops**, non
verificate indipendentemente sui documenti primari in questa sessione.

| Modello | Lancio dichiarato | Configurazione | Frequenza CPU | RAM |
|---|---|---|---|---|
| Amstrad CPC 464 | 1984-06 | PAL retail machine | 4 MHz | 64 KiB |
| Atari 800 | 1979-11 | NTSC, 48 KiB RAM | 1,79 MHz | 48 KiB |
| Atari 800 | 1979-11 | PAL, 48 KiB RAM | Non inclusa | 48 KiB |
| BBC Micro Model B | 1981-12 | Retail Model B | 2 MHz | 32 KiB |
| ZX Spectrum 48K | 1982-04 | PAL 48K | 3,5 MHz | 48 KiB |

Totale: **4 modelli, 5 configurazioni, 9 specifiche numeriche con fonte**.
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
- Adattamenti: selezione dei modelli e delle misure CPU/RAM, etichette italiane,
  conversione del formato YAML originale in JSON canonico, esclusione delle
  misure incerte. Numeri, unità, nomi e precisione delle date conservati.

Ogni modello e specifica cita il file ufficiale alla revisione indicata. Le
specifiche conservano identificativo della misura, metodo, livello dichiarato
dalla fonte, localizzatori e riferimenti ai documenti citati.

Il blocco `_metadata` include le copie UTF-8 e gli SHA-256 dei **17 file originali**
consultati (licenza, sistemi, misure e manifesti delle fonti). È conservato
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

Non è stata applicata alcuna importazione al database sul computer dell'utente.
