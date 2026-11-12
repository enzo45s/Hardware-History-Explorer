# Verifica del corpus MAME 0.276 — 12 novembre 2026

## Risultati effettivi

| Controllo | Esito |
|---|---|
| Suite backend SQLite | 143 passati, 1 test specifico PostgreSQL saltato |
| Suite backend PostgreSQL | 144 passati |
| Suite frontend | 23 passati |
| Compilazione React e immagini Docker | Riuscita |
| Docker Compose isolato `hhe-corpus` | API e web avviati, PostgreSQL operativo |
| Importazione dei cinque lotti, SQLite e PostgreSQL | 250 + 250 + 250 + 250 + 139 importati |
| Replay completo, entrambi i database | 1.139 invariati, stessi ID e nomi |
| Catalogo risultante | 1.139 schede, 1.251 configurazioni, 3.184 specifiche |
| Schede controllate tramite API di dettaglio | 1.139 / 1.139 con fonti |
| Specifiche controllate tramite API di dettaglio | 3.184 / 3.184 con citazioni |
| Conflitti nella prova da archivio vuoto | 0 |
| Asserzioni promosse automaticamente a verificate | 0 |

Le suite comprendono 17 nuovi casi per estrazione, esclusioni, qualificatori
hardware, anni incerti, licenze, versione XML, scelta del processore rispetto
alle periferiche, byte RAM e conservazione dei nomi dei chip come testo.
I test dei parser utilizzano fixture sintetiche; la prova completa sopra usa
i cinque lotti reali, verificandone prima SHA-256 e dimensioni dal manifest.

Per la prova integrata sono stati creati database vuoti e isolati, rimossi
soltanto i loro dieci record dimostrativi tramite il reset esplicito e applicati
i cinque file tramite gli endpoint di anteprima/applicazione. Nessun database
del computer dell'utente è stato raggiunto o modificato. Non sono state create
nuove tabelle o migrazioni per questo pacchetto.

## Tempi osservati

Tempi indicativi comprensivi di upload, preparazione e applicazione via API,
non benchmark di capacità né garanzia sui tempi di altri computer:

| File | Schede | SQLite, primo import | PostgreSQL via HTTP, primo import | PostgreSQL, replay |
|---|---:|---:|---:|---:|
| batch-01.json | 250 | 6,46 s | 15,11 s | 9,09 s |
| batch-02.json | 250 | 6,18 s | 13,26 s | 8,33 s |
| batch-03.json | 250 | 6,49 s | 14,48 s | 7,60 s |
| batch-04.json | 250 | 7,35 s | 15,65 s | 9,40 s |
| batch-05.json | 139 | 4,22 s | 10,32 s | 4,01 s |

Il replay aggiunge eventi e asserzioni allo storico senza aumentare il numero
di calcolatori, configurazioni o specifiche. L'assenza di conflitti in un
archivio vuoto non garantisce l'assenza di differenze rispetto ai dati già
presenti nell'archivio dell'operatore.

## Browser con il catalogo reale

Chromium su Compose, senza mock e senza aggiungere fixture al corpus:

- timeline e catalogo con tutte le 1.139 schede;
- filtro del catalogo su **IBM PC 5150** e apertura della scheda;
- proprietà esplicitamente emulate, nove riferimenti nella scheda a file
  ufficiali al commit fissato e messaggio di prezzo non documentato;
- autocompletamento e confronto di **IBM PC 5150** e **Apple IIgs**;
- pagina analisi con il conteggio completo;
- storico importazioni, apertura di **Fonti e verifiche** con stato
  **Da verificare** e passaggio dalle righe 1–25 alle 26–50;
- nessun errore JavaScript rilevato.

Nel singolo caricamento osservato la timeline era completa dopo circa 1,37 s.
È una misura locale occasionale, non un test di carico o una verifica esaustiva
del comportamento con decine di migliaia di schede. Catalogo e timeline
renderizzano ancora l'intera selezione; la virtualizzazione resta un possibile
miglioramento per archivi molto più grandi.

## Limiti

La copertura dei dati e le limitazioni storiche sono nella [guida](README.md).
I dati importati sono secondari e da revisionare: questi controlli verificano
il funzionamento del software, non attestano l'esattezza di ogni registrazione
MAME o l'esistenza commerciale distinta di ogni scheda candidata.

Non sono stati importati prezzi o fotografie. Non è stata effettuata una
verifica esterna delle date e delle configurazioni con manuali originali.
Wikidata è rimasta inaccessibile dalla rete cloud; AppleDB è stato esaminato
ma non importato. La generazione AI tramite servizio esterno non è stata
provata con crediti/chiavi configurati.

La build Vite segnala il bundle superiore a 500 kB; i test backend segnalano
un avviso di compatibilità/deprecazione Starlette TestClient/httpx. I controlli
locali sono passati; la CI remota va confermata dopo il push.
