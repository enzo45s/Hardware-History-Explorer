# RAM e configurazioni dei modelli

La sezione **Amministrazione → RAM e varianti** contiene due operazioni esplicite:
recupero dei dati RAM disponibili e accorpamento di denominazioni che descrivono
configurazioni dello stesso prodotto. Aggiornare il programma non modifica
automaticamente il catalogo.

## Aggiornare e usare il pannello

Nella cartella del progetto, mantenendo l'istanza Docker con i propri dati:

```bash
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Ricarica la pagina, quindi:

1. Apri **Amministrazione → RAM e varianti**.
2. Premi **Controlla RAM mancanti**. L'anteprima mostra i dati recuperabili con
   il valore originale e il collegamento alla fonte. **Completa RAM documentata**
   li aggiunge conservando descrizioni, configurazioni e quantità esistenti.
3. Premi **Analizza varianti da accorpare**. Controlla i gruppi e deseleziona
   quelli che vuoi tenere separati, poi premi **Accorpa i gruppi selezionati**.
4. Cerca il modello comune nel catalogo: le sigle precedenti continuano a
   funzionare nella ricerca e nei suggerimenti del confronto. Le configurazioni
   restano selezionabili e le offerte riportano la variante di riferimento.

Per trasferire il risultato sull'altro computer usa il backup completo già
previsto da [Transfer-HheArchive.ps1](../tools/Transfer-HheArchive.ps1), che include
anche gli alias e gli originali. La [guida al trasferimento](BACKUP_TRANSFER.md)
descrive esportazione e ripristino fra Windows e Mac.

## RAM: cosa viene recuperato

Il controllo distingue una quantità RAM dai soli limiti massimi/minimi e dalle
opzioni. Non sceglie il valore minimo di un elenco e non trasforma una capacità
massima in una dotazione di base. I valori testuali rimangono consultabili.

Vengono utilizzati:

- un piccolo pacchetto versionato con dati effettivamente consultati;
- specifiche RAM nelle righe di importazioni già applicate, quando manca il
  dato nel catalogo. Le righe ancora in anteprima, fallite o archiviate non
  vengono applicate di nascosto. Le configurazioni precedentemente accorpate
  vengono seguite mediante gli identificativi originali;
- una normalizzazione leggibile di quantità singole inequivocabili, ad esempio
  `64KB` → valore numerico `64 KB`. Le specifiche già archiviate mantengono
  il testo originale; le nuove importazioni normalizzano senza duplicare i dati.

Le vecchie citazioni interne escluse dalla bibliografia non vengono reintrodotte.
Gli altri sistemi senza una fonte utilizzabile restano nell'elenco da approfondire:
questa funzione non può inventare la RAM di tutti i computer del catalogo.

### HP 85 e il problema delle schede 1000bit in inglese

La scheda [1000bit n. 118](https://www.1000bit.it/scheda.asp?id=118), consultata
il 18 novembre 2026, identifica **HP 85**, **Hewlett-Packard (USA)** e riporta
**RAM: `16 - 32Kb`**. Il pacchetto conserva questo valore testuale e la citazione,
con hash dell'HTML e campo di origine nell'evidenza. Non assegna 16 o 32 KB come
unica dotazione certificata e non interpreta automaticamente il simbolo `Kb`.
HP 85B resta un modello distinto: non riceve il dato dell'HP 85.

L'importatore 1000bit riconosce ora le etichette italiane e inglesi, inclusi
`Name`, `Manufacturer`, `RAM`, sistema operativo, video, porte e prezzi.
La lingua restituita dal sito non dipende necessariamente dalla lingua del browser.
Campi equivalenti discordanti vengono rifiutati. Inizio produzione e data di
lancio restano concetti distinti. Il recupero RAM non applica prezzi o date
presenti nella stessa pagina.

Tutte le nuove asserzioni restano **pending**: l'esistenza di una citazione
non costituisce una verifica umana. Non occorrono chiavi AI né chiamate a pagamento.

## Quali varianti si accorpano

Le regole sono esplicite e non modificano l'identità generale dell'ETL prima
che l'operatore applichi un gruppo:

- **Commodore PET 2001**: 2001-4, 2001-8, B8/B16/B32 e N8/N16/N32 diventano
  configurazioni del PET 2001. RAM, sigle, tastiere e dati tecnici originali
  restano distinti. La sintesi del modello comune usa la voce italiana
  [Commodore PET, revisione 153297211](https://it.wikipedia.org/w/index.php?title=Commodore_PET&oldid=153297211),
  con attribuzione ai collaboratori e licenza CC BY-SA 4.0;
- **Apple IIc**: revisioni esplicite e variante UniDisk 3.5 dello stesso IIc.
  Apple IIc Plus resta distinto;
- **BBC Micro Model B+**: dotazioni 64K e 128K, conservate nelle configurazioni;
- qualificatori espliciti `(RAM 16 KB)` / `(32 KB RAM)` o `(BIOS 1.0)` /
  `(ROM rev 2)` / `(firmware 3.0)`.

Non vengono eliminati numeri o suffissi arbitrari. Macintosh 128K e 512K,
HP 85 e 85B, Atari 800XL e altri prodotti con denominazioni distinte non vengono
assunti automaticamente come duplicati. Una generica «revision 2» senza
indicazione di firmware resta separata: potrebbe identificare hardware diverso.

## Conservazione e reimportazione

L'operazione è transazionale e rifiuta anteprime diventate obsolete. Conserva
configurazioni, specifiche, immagini, prezzi, vendite, recensioni, fatti, fonti
e asserzioni tramite i loro identificativi. I testi e gli annunci delle singole
varianti rimangono nel relativo contesto, oltre che negli originali conservati.
La descrizione già curata di una scheda comune esistente non viene sostituita.

Date e prezzi di varianti diverse non vengono accorpati fra loro. La sintesi
commerciale può combinare anno e prezzo soltanto entro la stessa configurazione.
Le offerte europee e i profili regionali mantengono i criteri precedenti, rispettando
anche la variante. L'assistente riceve questo ambito e dà priorità alla configurazione
richiesta, anche quando la domanda usa una sigla precedente come N32.

La nuova tabella **computer_aliases** registra soltanto nomi approvati durante
l'accorpamento. Le importazioni successive, anche da un'altra fonte, seguono
questi alias e indirizzano i dati alla configurazione corretta. I nomi precedenti
non rinominano la scheda comune. Sintesi tecniche generate da 1000bit non vengono
ripetute come note aggiuntive del modello.

Le ricerche storiche e fotografiche e le sessioni 1000bit mantengono i riferimenti
validi; una richiesta in corso su una scheda accorpata non può sovrascrivere il
modello comune. La ricerca storica prosegue sugli altri sistemi. Per un modello
comune ancora privo di testo viene accodata una ricerca nel lavoro attivo.

La tabella degli alias viene creata all'avvio con `create_all(checkfirst=True)`.
La migrazione esplicita ripetibile è `python -m migrations.historical_imports`
con `DATABASE_URL` configurato. Nessun reset del catalogo è richiesto.
Uno svuotamento esplicito del catalogo elimina gli alias operativi insieme alle
macchine, conservandoli negli snapshot dell'operazione.

## Verifiche

Sul corpus completo dei cinque lotti distribuiti nel repository, importato in
un database temporaneo, sono stati proposti tre gruppi: PET 2001, Apple IIc e
BBC Micro Model B+. L'accorpamento ha ridotto le schede da **1.109 a 1.099**,
conservando tutte le **1.261 configurazioni** e **3.199 specifiche**. La
reimportazione di tutte le **1.139 righe** è risultata invariata, senza ricreare
modelli o configurazioni. Questi sono conteggi del corpus di prova, non del
catalogo locale dell'operatore.

I test controllano anche fonte HP 85, lingua 1000bit, intervalli/unità ambigue,
recupero da originali applicati, prezzi per configurazione, nuove fonti, alias
regionali, modifiche concorrenti, ricerca storica in corso, migrazione e reset.
La prova browser usa un database temporaneo separato e verifica recupero RAM,
accorpamento PET, conservazione dei testi, ricerca con le sigle precedenti e
layout 320/390 px.

Eseguite le suite backend su SQLite e PostgreSQL, i 30 test frontend, la
compilazione Vite e l'avvio Docker Compose con controlli di salute. Dopo gli
ultimi aggiustamenti sono passati 70 test mirati su ciascun database e una
successiva verifica di 33 casi RAM/riconciliazione. L'assistente è stato
controllato nel recupero locale dei dati, senza chiamate OpenAI a pagamento.
