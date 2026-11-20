# Verifica della rifinitura — 14 novembre 2026

## Risultati software

| Controllo | Esito |
|---|---|
| Backend SQLite, suite completa | 197 passati, 1 specifico PostgreSQL saltato |
| Backend PostgreSQL, suite completa | 198 passati |
| Frontend | 23 passati |
| Compilazione React | Riuscita |
| Build e avvio Docker Compose | Riusciti, progetto isolato `hhe-refinement` |
| Browser, backend reale | Accorpamento, foto conservata, arricchimento, descrizione italiana e prezzo con tipo visibile |
| Browser mobile 320 px | Nessun overflow orizzontale o errore JavaScript rilevato |

Le prove Wikidata utilizzano fixture sintetiche: descrizione italiana, CPU/OS,
codici valuta, unità risolte, prezzi qualificati/multipli/non risolti, numeri
non finiti, statement deprecati e valori alternativi. Nessuna verifica live
Wikidata riuscita: il proxy continua a rifiutare la connessione.

Restano gli avvisi preesistenti sul bundle Vite oltre 500 kB e sulla
deprecazione Starlette TestClient/httpx. La CI remota richiede conferma su GitHub.

## Prova integrata del catalogo reale

In un database PostgreSQL nuovo e isolato sono state riprodotte le **1.139
schede importate con la precedente identità**, prima che riconoscesse i
qualificatori regionali misti alle revisioni. Caricati i cinque lotti reali e
rieseguiti una volta, poi applicata la classificazione editoriale già disponibile.
Questa preparazione è una fixture di compatibilità, non una modalità presente
nel prodotto e non un'operazione sul database dell'utente.

| Misura | Prima | Dopo |
|---|---:|---:|
| Sistemi | 1.139 | **1.105** |
| Configurazioni | 1.251 | **1.308** |
| Specifiche | 3.184 | **7.180** |
| Schede con descrizione italiana nella prova | 0 | **1.105** |
| Prezzi | 0 | **5**, tutti IBM RT PC |
| Aggiornamenti alla riesecuzione dell'arricchimento | — | **0** |

L'accorpamento trasferisce 34 schede in 22 gruppi. Verificate tramite API tutte
le schede e gli insiemi degli identificativi: **tutte le 1.251 configurazioni,
le 3.184 specifiche e le commercializzazioni originali sono conservate**.
Le nuove specifiche hanno citazioni; le cinque voci di prezzo hanno valuta,
mercato e fonti. Nei nuovi lotti della prova finale non risultano conflitti o
asserzioni automaticamente verificate.

Tempo osservato per l'accorpamento: **6,77 s**. Arricchimento in 12 lotti da
massimo 100 schede: circa **58,2 s** complessivi per le richieste di applicazione;
riesecuzione circa **33,7 s**. Sono misure locali indicative, non un benchmark
o una garanzia sui tempi del computer dell'operatore.

Anche il primo lotto MAME originale è stato ricaricato dopo accorpamento e
arricchimento: **250 invariati**, circa 10,3 s, totale fermo a 1.105. Un test
dedicato verifica configurazioni con nomi collidenti e commercializzazioni
distinte con stesso mercato/data: il replay segue gli ID originali nell'audit,
senza duplicarli o selezionarne uno arbitrariamente.

La prima prova ha evidenziato un timeout dovuto alla lettura di tutte le righe
raw/normalizzate per ciascuna coppia da unire; ora si leggono prima i soli
campi di abbinamento e poi le righe pertinenti. Le ricerche delle identità
originali sono memorizzate nella singola Session e invalidate da nuovi audit
o reset. La prova finale sopra usa queste correzioni.

È emerso anche un caso AppleDB con due codici modello legittimi per Macintosh
Classic, `M0420` e `M1420`: sono ora conservati insieme come alternative,
evitando un conflitto artificiale nella stessa importazione.

## Cosa i conteggi non attestano

Le 3.996 specifiche aggiuntive comprendono **105 dati documentali** e **3.891
metadati esplicitamente emulati**. Soltanto 44 descrizioni usano documentazione
specifica curata; le altre sono brevi sintesi dei dati disponibili nel catalogo.
Questa prova attesta il funzionamento e la conservazione dei dati, non completa
una ricerca storica su tutti i modelli.

I cinque prezzi sono riportati da una tabella secondaria MAME con contesto
IBM ENUS: i documenti primari non sono stati verificati da questa rete. Non
sono stati trovati prezzi per il resto del catalogo e non sono state eseguite
conversioni, correzioni per inflazione o stime.

Snapshot verificato: `backend/app/importing/data/catalog-enrichment-v1.json`,
9.481.335 byte, SHA-256
`23c4e5ea9829e635f0e5f110d3c2f640819d452a21249d65e30d71b42c6ac8f6`.
I cinque lotti originali MAME restano invariati. I test non hanno raggiunto
il database o le fotografie sul computer dell'utente.
