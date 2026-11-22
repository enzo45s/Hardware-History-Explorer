# Dati consolidati del catalogo

Il database conserva due livelli distinti: le specifiche e le commercializzazioni
originali con le loro fonti, e i dati consolidati utilizzati da schede pubbliche,
confronto e assistente. La RAM principale e le opzioni sono ora risolte dal
backend e salvate nel database. Il frontend utilizza i risultati del server;
il vecchio adattatore rimane compatibile con API precedenti e file offline.

## Aggiornamento sul Mac e su Windows

Aggiornare il branch e ricostruire i servizi **del progetto Compose già usato**:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait
```

All'avvio l'API crea le nuove tabelle e i trigger e popola i dati consolidati
dei sistemi esistenti. La migrazione è additiva e ripetibile. Non occorre
reimportare i sistemi, ripetere la revisione delle unità o svuotare l'archivio.
Il primo avvio esegue il popolamento; i successivi aggiornano solo i sistemi
invalidati o le risoluzioni prodotte da regole cambiate. Le ricerche in corso
possono richiedere la ripresa dopo il riavvio dei container.

In **Amministrazione → RAM e varianti → Dati consolidati del catalogo**, premere
**Controlla dati consolidati**. Il numero dei sistemi consolidati deve coincidere
con il catalogo; normalmente «In aggiornamento» è zero. **Ricostruisci dati
consolidati** rigenera solo il livello derivato, conservando originali e audit.

Lo stato può essere letto anche dal Terminale:

```bash
docker compose -p hhe-import-test exec api python -m app.catalog_store status
```

Per una ricostruzione esplicita, ad esempio dopo modifiche con strumenti esterni:

```bash
docker compose -p hhe-import-test exec api python -m app.catalog_store rebuild
```

Fuori Docker i comandi richiedono `DATABASE_URL` esplicito. La sola migrazione
è disponibile come `python -m migrations.catalog_store`; il comando `rebuild`
esegue anche la migrazione se necessaria. `status` richiede uno schema già aggiornato.

## Tabelle e interrogazione

| Tabella | Contenuto |
|---|---|
| `catalog_snapshots` | Un risultato consolidato per computer, versione delle regole, impronta degli input e data di ricostruzione |
| `catalog_metrics` | Metriche interrogabili per computer e scheda/configurazione: componente, proprietà, quantità numerica NUMERIC, unità, valori strutturati, note e stato della risoluzione |
| `catalog_metric_assertions` | Collegamenti con tutte le specifiche originali che supportano il dato |
| `catalog_metric_sources` | Collegamenti alle fonti delle specifiche originali, comprese quelle conservate solo per tracciabilità interna |
| `catalog_dirty` | Coda dei sistemi da ricalcolare e generazione dell'invalidazione |

Le chiavi RAM sono `ram.capacity` e `ram.options`. Una capacità scalare esatta,
senza ruolo o qualificazione, è salvata numericamente in **KiB**. Intervalli,
elenchi, limiti, parole native e banchi nominati mantengono valori strutturati
e testo: non diventano arbitrariamente un singolo totale. Le unità storiche
ambigue non vengono equiparate a prefissi IEC. La presentazione usa KB/MB/GB
secondo le regole già adottate dal progetto; non riscrive le unità originali.

Esempio PostgreSQL, selezione delle quantità scalari riportate, senza includere
automaticamente valori di riferimento, massimi o capacità ignote:

```sql
SELECT c.id, m.name AS produttore, c.model_name,
       f.sheet_id, f.numeric_value AS ram_kib, f.resolution_state,
       f.verification_status
FROM catalog_metrics f
JOIN computers c ON c.id = f.computer_id
JOIN manufacturers m ON m.id = c.manufacturer_id
WHERE f.metric = 'ram.capacity'
  AND f.resolution_state = 'reported'
  AND f.unit = 'KiB' AND f.numeric_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalog_dirty d WHERE d.computer_id = c.id)
ORDER BY m.name, c.model_name, f.sheet_id;
```

Durante un'importazione, il filtro sulla coda esclude i sistemi in aggiornamento.
Prima di un'esportazione SQL completa, verificare `pending: 0` tramite `status`
oppure eseguire `rebuild`, così sono inclusi anche gli ultimi aggiornamenti offline.

Per risalire alle prove e alle decisioni umane, unire
`catalog_metric_assertions.specification_id` a `specifications.id` e
`specification_sources.target_id`. I valori `pending`, `verified`, `conflict`
e `rejected` dei collegamenti originali restano invariati. Il riepilogo usa
`pending`, `verified` solo quando tutti i collegamenti di supporto sono già
verificati, oppure `disputed` quando esistono collegamenti in conflitto/rifiutati.
Un dato di riferimento verificato rimane un riferimento, non attesta la RAM di base.

## Risoluzione e aggiornamenti

- La RAM principale preferisce quantità riportate. Un riferimento differente
  resta una nota; in assenza di quantità riportate il riferimento è esplicitamente
  qualificato. Valori discordanti, banchi nominati e memoria video non vengono sommati.
- La seconda riga RAM contiene opzioni, espansioni e limiti qualificati. Un limite
  massimo non diventa RAM installata. Le annotazioni non quantificabili restano note.
- I profili regionali compatibili si accorpano; configurazioni hardware
  sostanzialmente diverse restano separate e selezionabili. Nel confronto ogni
  cella contiene copertura e ambito delle configurazioni.
- Le commercializzazioni complementari vengono consolidate nello stesso snapshot,
  mantenendo gli ID dei record originali e le fonti. L'assistente usa questi stessi
  riepiloghi e queste stesse specifiche, oltre alle asserzioni storiche distinte.
- Trigger SQLite e PostgreSQL invalidano solo i sistemi interessati da modifiche
  a computer, configurazioni, specifiche, commercializzazioni, produttori, mercati,
  alias, fonti e collegamenti specifica/fonte e commercializzazione/fonte.
- L'API svuota la coda all'avvio e prima/dopo le richieste al database. Il percorso
  leggero di autocompletamento mantiene la sua sola query e non attende il ricalcolo.
  Le operazioni CLI/SQL eseguite ad API spenta vengono consolidate alla ripresa.
- Impronte degli input, controlli di versione e ricalcolo in memoria impediscono
  alle API di presentare uno snapshot obsoleto. Il ricalcolo di lettura non scrive;
  l'aggiornamento persistente avviene nella manutenzione transazionale.
- Il lock condiviso del catalogo, i lock sulle righe PostgreSQL e le generazioni
  della coda preservano le invalidazioni concorrenti. In caso di errore rimangono
  intatti l'ultimo snapshot e la coda, che può essere ritentata.

Le tabelle consolidate sono rigenerabili e non vanno modificate manualmente.
Le esportazioni complete del database le includono; lo svuotamento del catalogo
le elimina tramite le chiavi esterne. Gli snapshot di audit dello svuotamento
conservano gli originali ed escludono questa cache derivata, evitando variazioni
del token dovute alla sola manutenzione.

## Limiti e verifica

Questo aggiornamento consolida dati già presenti: non aggiunge ricerche storiche,
prezzi o quantità RAM mancanti e non rende attendibili tutte le fonti. Non modifica
le asserzioni originali, i loro identificativi o gli stati di verifica umana.

La migrazione e il popolamento sono stati provati su una copia separata del dump
del Mac del 22 novembre 2026: 1.133 sistemi. I controlli confrontano il contenuto
di tutte le tabelle storiche prima/dopo, verificano gli ID e le fonti RAM, il limite
di due righe RAM per confronto e la ripetibilità del popolamento. Le prove
automatiche coprono SQLite e PostgreSQL, modifiche SQL, cancellazioni, fonti,
alias, fallimenti atomici, ripresa, configurazioni e aggiornamenti concorrenti.

Risultato sulla copia: **1.133 snapshot, 7.002 metriche, coda vuota** e contenuto
invariato in tutte le 33 tabelle storiche. Ogni specifica RAM conserva gli ID
originali e le fonti; rilettura e svuotamento della coda già elaborata non
riscrivono gli snapshot. Il test browser in sola lettura verifica scheda e
confronto dell'Atari 400, stato amministrativo e layout a 320/390 pixel.

Validazione: suite SQLite completa con 897 test superati e due riservati a
PostgreSQL saltati; suite PostgreSQL completa con 898 test superati, seguita
da 104 test mirati sull'ultima versione, inclusa la deduplicazione delle
quantità equivalenti anche nel campo SQL numerico. Superati 44 test frontend,
compilazione React, Docker Compose e browser qualità su catalogo sintetico.
