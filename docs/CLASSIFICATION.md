# Categorie del catalogo

Dopo un aggiornamento e la ricostruzione dei container, l’API classifica le
schede prive di una categoria specifica. Lo stesso controllo viene eseguito
sui sistemi interessati da un’importazione applicata. Non occorre svuotare
l’archivio o caricare nuovamente i dataset.

Le categorie specifiche già presenti, anche personalizzate, vengono conservate.
Quando una scheda ha una categoria specifica, l’associazione ridondante a
**Calcolatore** viene rimossa: anche filtri e statistiche riflettono la pulizia.
Le importazioni successive non ripristinano quell’etichetta generica.
ID, nomi, configurazioni, specifiche, fotografie, prezzi, descrizioni e fonti
bibliografiche esistenti restano conservati.

## Uso

```sh
git switch feat/historical-data-import
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Usa il nome del tuo progetto Compose se diverso da `hhe-import-test`.
Apri **Amministrazione → Categorie** per vedere:

- conteggi per categoria e numero di schede ancora generiche;
- assegnazioni disponibili, con criterio utilizzato;
- sistemi incerti, filtrabili per marca e modello.

**Aggiorna analisi categorie** ricalcola l’anteprima. **Applica la classificazione
al catalogo** applica tutte le proposte e pulisce le etichette ridondanti,
anche oltre 1.000 schede, in lotti. Il filtro limita la visualizzazione, non
l’applicazione. Serve per esempio dopo modifiche manuali effettuate dall’ultimo
avvio. **Modifica categorie** apre direttamente l’editor della scheda incerta:
seleziona le categorie desiderate e salva. Puoi creare una categoria nell’editor.
Il pannello non ripristina i precedenti blocchi di manutenzione in Importazioni.

## Criteri

Le regole versionate sono in `backend/app/importing/classification.py` e
`classification_rules.py` (`hhe-editorial-categories-v2`). Il vocabolario è:
Home computer, Personal computer, Workstation, Portable, Microcomputer,
Minicomputer, Mainframe, Supercomputer e Server.

La classificazione utilizza:

- famiglie e modelli espliciti insieme al produttore, riconoscendo marchi brevi,
  denominazioni societarie e annotazioni geografiche dei produttori;
- famiglie tecniche individuate dai riferimenti già archiviati nel dataset;
  per i driver sono ammessi soltanto percorsi ufficiali prestabiliti;
- una frase introduttiva italiana che identifichi esplicitamente il modello
  come workstation, portatile, server o altra tipologia prevista.

La sola marca, il processore, la RAM e l’anno non determinano la categoria.
Una menzione di software «per workstation» non classifica il computer come
workstation. In caso di due tipologie specifiche incompatibili non viene
assegnata automaticamente una categoria. Le categorie generali Personal
computer e Microcomputer possono essere precisate dalla famiglia documentata.
Analizzatori logici, gateway e altre apparecchiature specialistiche non vengono
forzati nella categoria di tutti i computer dello stesso produttore.
Nessuna nuova richiesta di rete e nessuna API a pagamento sono necessarie.

## Audit

Le assegnazioni sono editoriali: non diventano automaticamente dati storici
verificati. Ogni assegnazione conserva una dichiarazione `pending` con regola,
versione e categorie precedenti; la pulizia conserva le associazioni precedenti
nel registro dell’operazione. L’operazione usa il consueto lock del catalogo e
controlla che l’anteprima non sia cambiata prima di applicarla.

L’audit interno utilizza una fonte tecnica `editorial_rule`, esclusa dalle
bibliografie pubbliche e dal pannello Fonti secondo la politica esistente:
HHE non viene presentato come fonte storica indipendente. Non viene attribuita
alla fonte del dataset la verifica di una categoria che non dichiarava.
L’applicazione è ripetibile; un secondo passaggio senza cambiamenti non crea
nuove assegnazioni o lavori di audit. Non richiede migrazioni di schema.

## Verifica del 20 novembre 2026

Sul corpus originale di 1.139 record le regole riconoscono 1.112 voci, rispetto
alle 610 precedenti; 27 richiedono esame manuale. Le varianti del dataset sono
più numerose delle schede canoniche effettivamente importate.

In un database temporaneo, importando tutti i cinque lotti con la normale
deduplicazione e conservando i dieci esempi iniziali, risultano **1.073 sistemi**:

| Categoria | Sistemi |
|---|---:|
| Home computer | 510 |
| Personal computer | 316 |
| Portable | 103 |
| Workstation | 84 |
| Microcomputer | 19 |
| Minicomputer | 11 |
| Server | 2 |
| Mainframe | 1 |
| Supercomputer | 1 |
| Calcolatore, da esaminare | 26 |

Il recupero ha classificato 1.037 schede generiche in due lotti; le dieci
schede iniziali erano già classificate. Confrontate tutte le schede prima e
dopo: stessi dati, salvo le categorie. Ripetendo i cinque import, tutti i
1.139 record risultano invariati e la categoria generica non ricompare.
Questi conteggi riguardano il database temporaneo, non il database locale
dell’utente: eventuali categorie specifiche già assegnate vengono preservate.
