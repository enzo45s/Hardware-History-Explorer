# Ripartire con un catalogo vuoto

Il pannello **Amministrazione → Importazioni → Svuota archivio per un nuovo
import** rimuove i dati correnti del catalogo. Serve per ripetere prove o
preparare un'importazione completa. Non viene eseguito automaticamente:
aggiornamento, migrazione e avvio dell'applicazione non svuotano nulla.

## Aggiornare la stessa istanza su Windows

Sul branch `feat/historical-data-import`, nella cartella del progetto:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
```

Usa lo stesso nome progetto Compose già utilizzato. Se avviavi senza `-p`,
omettine il parametro anche adesso. Cambiarlo significherebbe usare altri
volumi e un altro database. Premi Ctrl+F5 nel browser dopo la ricostruzione.

## Backup prima dello svuotamento

Conserva un backup esterno del database e delle fotografie. Questi comandi
salvano il dump nel container e lo copiano come file, evitando la redirezione
binaria di alcune versioni PowerShell. Usa una cartella nuova per ogni backup:

```powershell
$backupFolder = "hhe-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
New-Item -ItemType Directory -Path $backupFolder
docker compose -p hhe-import-test stop api web
docker compose -p hhe-import-test exec -T db pg_dump -U history -d hardware_history -Fc -f /tmp/hhe-before-reset.dump
docker compose -p hhe-import-test cp db:/tmp/hhe-before-reset.dump "$backupFolder/database.dump"
docker compose -p hhe-import-test cp api:/code/uploads "$backupFolder/"
docker compose -p hhe-import-test up -d
```

Controlla che i comandi siano riusciti e che dump e cartella `uploads` siano
presenti prima di confermare nel pannello. Non usare `docker compose down -v`:
rimuoverebbe i volumi invece di eseguire questo reset controllato.

## Eseguire il reset dal pannello

1. Apri **Amministrazione → Importazioni → Svuota archivio per un nuovo import**.
2. Premi **Prepara anteprima di svuotamento**. È una lettura: il catalogo
   non cambia. Controlla i conteggi dei dati da rimuovere.
3. Inserisci una motivazione e conferma di avere salvato il backup.
4. Scrivi esattamente **SVUOTA ARCHIVIO** e premi **Svuota i dati elencati**.
5. Il catalogo deve mostrare **0 calcolatori**, anche dopo un riavvio API.
6. Seleziona **CSV / JSON autorizzato** e prepara una nuova anteprima del
   file canonico. Per il campione `retroflops-computers-19.json`, partendo
   dal catalogo vuoto, l'esito atteso è **19 importati**; ripetendolo,
   **19 invariati**. Non riappare il seed di dieci macchine dimostrative.

Per un corpus più grande svuota una sola volta, poi importa i lotti successivi
senza altri reset. Restano i limiti di 1000 record e 8 MB per file: il reset
non li modifica. Per aggiornare dati già presenti, l'import incrementale resta
disponibile senza dover svuotare il catalogo.

Se i dati cambiano fra anteprima e applicazione, il server rifiuta il reset:
prepara una nuova anteprima. In caso di errore durante la transazione,
catalogo, storico e marcatore dello svuotamento vengono ripristinati insieme.

## Ambito preciso

| Dati | Effetto |
|---|---|
| Calcolatori e configurazioni | Rimossi dal catalogo |
| Specifiche, commercializzazioni/prezzi, vendite, recensioni, fatti | Rimossi dal catalogo |
| Produttori, categorie e mercati | Rimossi, anche se non utilizzati, per ripartire senza vecchi alias |
| Galleria e collegamenti alle fonti dei calcolatori | Rimosse le associazioni correnti |
| File fotografici nel volume `image_uploads` | Conservati; non vengono ricollegati automaticamente ai nuovi sistemi |
| Biblioteca delle fonti | Conservata e riutilizzata dai nuovi import |
| Upload originali, asserzioni e decisioni | Conservati nello storico; le vecchie decisioni non possono modificare le nuove schede |
| Identità esterne e corrispondenze attive | Rimosse |
| Importazioni precedenti | Archiviate; non applicabili direttamente, ma ripetibili con una nuova anteprima |
| Riconciliazioni precedenti | Storico conservato; gli abbinamenti delle configurazioni precedenti al reset non vengono riutilizzati |
| Dati dimostrativi | Il ripopolamento automatico resta disattivato per questo database |
| Configurazione, chiavi e codice | Invariati |

Una nuova tabella additiva `archive_resets` conserva motivazione, conteggi e
metadati precedenti alla rimozione; lo storico permette di scaricarli come
JSON. Gli originali restano nel database e i file fotografici sul disco:
**non è una cancellazione definitiva dei dati né un pulsante di ripristino**.
Il backup PostgreSQL e la copia del volume restano necessari per un ripristino
completo. Nessuna sequenza PostgreSQL viene azzerata e nessuna tabella eliminata.

La tabella è creata all'avvio o dalla migrazione ripetibile già esistente
`python -m migrations.historical_imports`. Il pannello mantiene l'uso locale
single-user del progetto.

## Test del reset

I test backend coprono conferma, anteprima senza effetti, reset completo,
conservazione di file/fonti/originali, riavvio senza seed, nuovo import e replay,
anteprima superata anche con conteggi uguali, isolamento dalle vecchie decisioni
e riconciliazioni, rollback se una cancellazione fallisce.

Controlli eseguiti su database isolati:

- SQLite: **126 test passati**, uno specifico PostgreSQL saltato.
- PostgreSQL in Docker: **127 test passati**.
- Frontend: **23 test passati** e build Vite riuscita.
- Browser importazioni/riconciliazioni e browser reset: passati, comprese
  conferme, selezioni/filtri azzerati e layout a 320/390 px.
- API Docker riavviata dopo il reset: catalogo ancora a zero.
- Campione reale sul PostgreSQL Docker vuoto: **19 importati**, poi
  **19 invariati**, **70 specifiche con fonte**, zero verifiche automatiche.
  Il campione non contiene prezzi e non ne sono stati inventati.

L'unico reset eseguito dal cloud è sul progetto Compose temporaneo `hhe-reset`,
creato per queste prove. Il database dell'utente non è stato svuotato.
Gli screenshot sono in `/workspace/hhe-reset-artifacts/`. Restano gli avvisi
non bloccanti su bundle Vite e deprecazione TestClient/httpx; la CI remota va
confermata su GitHub dopo il push.

La prova browser è separata perché svuota il catalogo: **solo su un progetto
Compose usa e getta**, mai sul database dell'utente:

```powershell
$env:HHE_ALLOW_TEST_RESET = "1"
$env:HHE_BASE_URL = "http://127.0.0.1:8080/"
cd frontend
npm run test:browser:reset
```

Richiede flag esplicito e URL loopback. La CI la esegue solo contro il proprio
Compose temporaneo, dopo il test di importazione. La prova verifica i tre
requisiti della conferma, catalogo vuoto, layout mobile e assenza di errori JS.
