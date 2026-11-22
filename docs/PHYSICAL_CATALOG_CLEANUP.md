# Pulizia fisica delle tabelle del catalogo

La pulizia accorpa i record **nelle tabelle principali** `configurations`,
`specifications` e `releases`. Non si limita a nasconderli nel frontend e non
mantiene una seconda copia operativa del catalogo: dopo l'applicazione, le
tabelle di snapshot e metriche del precedente livello consolidato vengono
svuotate e non vengono più popolate.

Gli originali rimossi o modificati, i collegamenti alle fonti, gli identificativi
precedenti e le corrispondenze sono conservati nell'audit `physical_cleanup`.
Gli upload e le asserzioni storiche delle importazioni rimangono disponibili.
Questa conservazione serve a capire cosa affermava una fonte e a riconoscere
le successive reimportazioni; non costituisce una seconda scheda attiva.

## Applicazione sul Mac o su Windows

Aggiornare il branch e i servizi del progetto Compose esistente:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up --build -d --wait --wait-timeout 900
```

Prima dell'applicazione conservare un backup completo recente. Aprire
**Amministrazione → RAM e varianti → Pulizia fisica dell’archivio**:

1. Premere **Analizza pulizia fisica** per leggere i conteggi effettivi.
2. Premere **Applica pulizia alle tabelle principali**.
3. Ripetere l'analisi: deve indicare zero sistemi da aggiornare.

L'applicazione ricontrolla i dati sotto lock e rifiuta un'anteprima diventata
obsoleta. La trasformazione e l'audit sono nella stessa transazione; un errore
annulla l'intera operazione. Non bisogna svuotare l'archivio o reimportare il dump.
Il database sul Mac non è raggiungibile direttamente dall'ambiente cloud.

In alternativa, nel contenitore API:

```bash
docker compose -p hhe-import-test exec api python -m app.catalog_cleanup preview --output /tmp/hhe-pulizia.json
docker compose -p hhe-import-test exec api python -m app.catalog_cleanup apply --plan /tmp/hhe-pulizia.json
```

Il file di anteprima contiene dati originali privati: conservarlo fuori da Git.
Il comando non sovrascrive un file esistente; usare un nome nuovo nelle analisi
successive. Dopo un aggiornamento delle regole va preparata una nuova anteprima.

## Regole

- Profili regionali compatibili, blocchi tecnici complementari e proprietà
  equivalenti diventano record unici. Componenti e configurazioni hardware
  sostanzialmente diversi rimangono distinti e selezionabili.
- La RAM ha una proprietà principale `Capacità` e, quando necessaria, una sola
  proprietà `Opzioni di memoria`. Le capacità scalari precise vengono espresse
  in KiB; intervalli, opzioni, limiti e organizzazioni native restano espliciti.
  Le etichette pubbliche continuano a usare KB/MB/GB secondo le regole del progetto.
- Un valore riportato prevale su un riferimento; il riferimento differente
  resta una nota documentata. Massimi, banchi nominati e VRAM non diventano
  automaticamente la dotazione RAM installata o un totale inventato.
- Le commercializzazioni complementari diventano righe complete con mercato,
  data e prezzo. Date derivate dal contesto generale del modello restano
  qualificate come tali; non diventano prove autonome della consegna in un paese.
  Prezzi, valute e configurazioni differenti restano separati.
- Le informazioni PAL/NTSC e 50/60 Hz non necessarie alla scheda vengono tolte
  dalle specifiche attive e rimangono negli originali archiviati. I clock CPU
  e le caratteristiche effettive dei monitor restano conservati.
- Piccoli metadati `catalog_details` conservano qualificazioni e identità dei
  profili accorpati; i valori principali non sono duplicati in un'altra tabella.
- Le importazioni successive seguono gli identificativi accorpati. Verificare
  una vecchia asserzione già rappresentata non deve ripristinare un mercato
  sconosciuto, sovrascrivere tutta una capacità composta o sostituire la RAM
  riportata con il vecchio riferimento.
- Le nuove modifiche e importazioni vengono normalizzate automaticamente
  quando l'API elabora la coda. La ricerca per autocompletamento resta leggera.
  Le modifiche SQL eseguite ad API spenta vengono elaborate al riavvio.

## Interrogazione diretta

Il catalogo operativo è nelle tabelle originarie, non in `catalog_metrics`:

```sql
SELECT c.model_name, f.variant_name, s.numeric_value AS ram_kib,
       s.catalog_details->>'resolution_state' AS stato
FROM computers c
JOIN configurations f ON f.computer_id = c.id
JOIN specifications s ON s.configuration_id = f.id
WHERE s.component_type = 'RAM' AND s.property_name = 'Capacità'
  AND s.numeric_value IS NOT NULL AND s.unit = 'KiB'
ORDER BY c.model_name, f.variant_name;
```

Lo stato `reference` indica un riferimento, non una dotazione iniziale provata.
Per selezionare solo quantità riportate aggiungere
`AND s.catalog_details->>'resolution_state' = 'reported'`.

## Limiti

Pulire la struttura non completa le ricerche storiche e non verifica tutte le
asserzioni. Valori mancanti, parti non documentate e conflitti reali rimangono
espliciti. Non vengono accorpate offerte diverse né configurazioni distinguibili
solo per ottenere un conteggio inferiore. Restano valide le fonti e gli stati
di verifica umana; stati discordanti su una stessa associazione consolidata
rimangono conservati nell'audit e non vengono promossi automaticamente.

## Risultato sulla copia del Mac e verifiche

La prova sul dump del 22 novembre 2026 conserva tutti i **1.133 sistemi**:

| Tabelle principali | Prima | Dopo |
|---|---:|---:|
| Configurazioni | 1.713 | 1.166 |
| Specifiche | 9.557 | 6.988 |
| Commercializzazioni | 1.783 | 1.183 |
| Fonti | 7.435 | 7.435 |
| Fotografie associate | 605 | 605 |

Seconda analisi: zero modifiche. Tutte le 9.557 specifiche originali sono
rintracciabili nell'audit; i prezzi originari sono conservati. Nessun riferimento
FK orfano e nessun duplicato esatto nelle specifiche attive o nelle offerte
con lo stesso ambito. Le tabelle di cache non contengono più copie del catalogo.
Dodici reimportazioni reali da dati manuali, 1000bit e prezzi storici non
ricreano configurazioni, specifiche, commercializzazioni o sistemi.

La copertura RAM rimane 867 sistemi con quantità censita e 266 senza;
restano espliciti nove valori non quantificabili e sei parziali. Queste lacune
non vengono nascoste dalla pulizia.

Verifiche: suite SQLite completa con 906 test superati e due casi PostgreSQL
saltati; 167 test PostgreSQL mirati, seguiti dalle verifiche finali sui moduli
di pulizia, catalogo e unità (69 SQLite più uno saltato, 70 PostgreSQL).
Superati 44 test frontend, compilazione React, Docker Compose e Chromium:
applicazione della pulizia, seconda analisi invariata, editor e confronto,
conservazione delle configurazioni e layout a 320/390 pixel. La copia effettiva
è stata verificata anche nel browser tramite un'API in sola lettura.
Il roundtrip PowerShell completo è predisposto in CI con una sorgente pulita
e una destinazione nella modalità precedente; `pwsh` non è presente nel cloud
locale. Il dump non include i file delle immagini caricate sul Mac.

## Aggiornamenti successivi delle regole

Una volta attivata la pulizia fisica, l'avvio di una nuova versione delle regole
normalizza automaticamente tutte le schede nelle tabelle principali. Non è
necessario reimportare il database. La migrazione registra la versione e gli
originali modificati nell'audit; se fallisce, la transazione viene annullata e la
coda resta disponibile per il tentativo successivo. Mantenere un backup recente
prima di aggiornare. Le regole delle date delle varianti e dei prezzi sono
spiegate in [Commercializzazione](RELEASE_SUMMARIES.md).

Il primo avvio dopo un aggiornamento può richiedere alcuni minuti per il
riesame completo. L'health check concede dieci minuti alla fase iniziale e
segnala subito l'API pronta quando l'operazione termina; gli avvii ordinari
non devono attendere questa durata.

### API in avvio e frontend non avviato

Durante la transazione iniziale Uvicorn non accetta ancora connessioni:
`Waiting for application startup` e `Connection refused` nell'health check
possono indicare una normalizzazione ancora in corso. I log mostrano ora la
fase e l'avanzamento ogni 50 sistemi, fino a `database pronto`:

```bash
docker compose -p hhe-import-test logs -f --tail=60 api
```

Se il primo `up` si è interrotto ma l'API ha poi terminato l'avvio, completare
l'avvio del frontend senza ricompilare:

```bash
docker compose -p hhe-import-test up -d --wait --wait-timeout 900 web
```

Una normalizzazione limitata alle commercializzazioni evita ora di riscrivere
configurazioni, specifiche e collegamenti alle fonti rimasti identici. La
pulizia esplicita registra anche la versione delle regole applicate: riavvio,
backup e ripristino della stessa versione non riaccodano inutilmente l'intero
catalogo e non aggiungono un evento di migrazione al solo riavvio.

Verifica della correzione di avvio: 49 test SQLite superati (uno specifico
PostgreSQL saltato), 50 test PostgreSQL e otto test degli archivi superati;
build e health check Compose riusciti. Su una nuova copia del dump con 1.133
schede, l'avvio completo con normalizzazione è durato 23,64 secondi nel cloud
(misura non trasferibile al Mac). Tutte le righe principali e i collegamenti
alle fonti coincidono con il risultato della normalizzazione precedente. Un
secondo avvio completo conserva gli hash di tutte le tabelle e le sequenze.
Il test copre anche la versione delle regole che causava un falso cambiamento
dello snapshot dopo l'esportazione nel test CI del trasferimento.
