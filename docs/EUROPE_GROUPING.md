# Profili e commercializzazioni raggruppati in Europa

Le schede e i confronti riuniscono le configurazioni regionali europee con gli
stessi dati tecnici. Le commercializzazioni europee compaiono sotto un unico
riquadro **Europa**: offerte identiche ripetute fra paesi differenti vengono
accorpate, mentre prezzi, valute, date e tipi di listino differenti restano
distinguibili nello stesso riquadro.

## Criterio geografico

Si riconoscono nomi italiani/inglesi e alias espliciti dei paesi europei,
compresi UK/Regno Unito, Norvegia e Svizzera: il criterio non e l'appartenenza
all'Unione Europea. Sono comprese denominazioni storiche come Cecoslovacchia
e Jugoslavia. Gli elenchi composti, per esempio Svezia/Finlandia, vengono
raggruppati solo se tutti gli elementi sono riconosciuti come europei.

Russia, Turchia, Kazakistan, Georgia, Azerbaigian e altri casi transcontinentali
o territorialmente ambigui restano con la denominazione originale. Cipro e
Armenia non vengono assegnati all'Europa geografica. Territori non europei
come Groenlandia e Guyana francese non vengono classificati in base al paese
di appartenenza. Lingua, valuta, PAL/NTSC ed etichette generiche come EMEA non
sono usate per dedurre un continente.

I codici paese sono riconosciuti nei mercati; nei nomi di configurazione si
evitano abbreviazioni hardware ambigue come **AT**, **SE** e **ME**. Un modello
UK-2086 non diventa una versione britannica per il solo prefisso UK.

## Configurazioni

Si accorpano solo profili con le stesse specifiche normalizzate, compresi ruolo
del componente, quantita, unita, molteplicita e note visibili. Non si aggiungono
a una configurazione dati mancanti presi da un'altra. ROM, revisioni, tastiere
AZERTY/QWERTY, Enhanced, Platinum, UniDisk e altre qualifiche riconosciute sono
conservate. Profilazioni europee con RAM o processori diversi rimangono distinte.

Il raggruppamento riguarda i dati censiti: non certifica che firmware, tastiere
o copertura commerciale fossero identici in tutti i paesi europei.

L'API aggiunge `display_configurations` e mantiene `configurations` originale.
Ogni profilo conserva `configuration_ids` e gli identificativi delle specifiche
riunite. Scheda e confronto usano i profili; l'editor mantiene tutte le varianti
originali. Anche una selezione di confronto salvata con un vecchio ID regionale
continua a corrispondere al profilo corretto.

## Commercializzazioni

Paesi europei con stessi importo, valuta, date e tipo di prezzo diventano una
sola offerta. Prezzi senza valuta e piu registrazioni dello stesso paese non
vengono equiparati automaticamente. Prezzi diversi rimangono righe distinte
con il paese di riferimento, quando noto; non vengono effettuate conversioni.
Le regole conservative sulle date dei [riepiloghi](RELEASE_SUMMARIES.md)
restano applicate. I mercati e le registrazioni originali non sono riscritti.

## Vecchio menu di provenienza e verifica della build

Il nuovo frontend non contiene il menu **Provenienza dei dati accorpati**.
L'HTML e il file di versione vengono serviti con `Cache-Control: no-store`;
gli asset con hash possono essere memorizzati come immutabili. La versione
compilata si controlla aprendo:

```text
http://localhost:8080/build-info.json
```

Deve mostrare **`"ui_version": "2026-11-europe-1"`** e la data UTC di compilazione.
Se compare il vecchio sito o il file non e disponibile, il frontend servito
non corrisponde a questa build. Per ricompilare entrambi i servizi dalla cartella
del progetto, conservando il progetto Docker con i tuoi dati:

```bash
git fetch origin
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test build --no-cache api web
docker compose -p hhe-import-test up -d --force-recreate --wait api web
```

Su Safari ricarica dall'origine con **Option-Command-R**; su Chrome/Firefox
usa **Command-Shift-R**, oppure apri il sito in una finestra privata. Se usi
un nome Compose diverso, sostituisci `hhe-import-test` con quello dell'istanza
in uso (`docker compose ls -a`). Non occorre svuotare o reimportare l'archivio.

## Verifiche

Test backend su paesi europei/non europei, casi transcontinentali, nomi hardware
ambigui, revisioni Apple reali, fonti/ID conservati e differenze tecniche/monetarie;
test frontend sui gruppi e sulla selezione delle configurazioni nel confronto.
`npm run test:browser:europe` verifica API e frontend compilato, assenza del
menu, header cache, file di build, offerte differenti e viewport da 320/390 px.

Prova sui lotti originali del dataset di base: **1.251 configurazioni diventano
1.211 profili visualizzati**, senza perdere alcun ID o valore tecnico. Le 180
varianti europee producono 140 profili; 13 modelli hanno profili ripetuti accorpati.
Apple //c e Apple //e passano rispettivamente da 5 e 6 configurazioni a 2 profili
(uno generale e uno Europa); MEGA ST passa da 5 a 2 (USA ed Europa).

Verifiche del 18 novembre 2026: **554 test SQLite superati e uno specifico
PostgreSQL saltato; 555 test PostgreSQL superati; 30 test frontend superati**.
Build React e Docker Compose riuscite; Chromium verifica il frontend compilato,
i profili europei, offerte differenti, cache e viewport mobili. Il bundle Vite
resta oltre 500 kB, avviso gia presente prima di queste modifiche.
