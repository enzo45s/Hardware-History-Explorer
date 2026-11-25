# Duplicati, fonti e prezzi

## Aggiornamento su Windows

Sul branch `feat/historical-data-import`, nella cartella del progetto:

```powershell
git pull --ff-only
docker compose -p hhe-import-test up --build -d
```

Usa il nome del tuo progetto Compose se diverso. Un refresh completo del
browser carica il pannello aggiornato. Non serve ricaricare il JSON per
controllare i duplicati già creati.

Viene aggiunta soltanto la tabella di audit `catalog_reconciliations`:
l'avvio la crea se manca. La migrazione esplicita ripetibile è inclusa in
`python -m migrations.historical_imports`, dopo un backup e con API ferma.
Nessun duplicato viene unito automaticamente durante la migrazione o l'avvio.

## Riconciliare le schede esistenti

Prima di riconciliare il tuo archivio, conserva un backup. Con il database
Compose in esecuzione, questi comandi evitano la redirezione binaria di PowerShell:

```powershell
docker compose -p hhe-import-test exec -T db pg_dump -U history -d hardware_history -Fc -f /tmp/hhe-before-reconciliation.dump
docker compose -p hhe-import-test cp db:/tmp/hhe-before-reconciliation.dump ./hhe-before-reconciliation.dump
```

1. Vai in **Amministrazione → Importazioni → Duplicati già importati**.
2. Premi **Controlla duplicati e produttori**. Sono mostrati gruppi di
   calcolatori e produttori con nomi identici o alias esplicitamente riconosciuti.
3. Per ogni coppia, scegli **Anteprima: unisci … in …**. La scheda indicata
   da **mantieni ID** conserva nome, identificativo e valori già presenti.
4. Controlla le differenze. I campi mancanti della scheda mantenuta vengono
   completati; quelli discordanti restano negli originali scaricabili e,
   quando presenti, nelle asserzioni da rivedere. Non sono sovrascritti.
5. Inserisci la motivazione, conferma che è lo stesso elemento e premi
   **Applica la riconciliazione controllata**.
6. Ripeti finché resta una scheda per ogni gruppo equivalente. Per Apple e
   Apple Computer, riconcilia anche il gruppo **Produttore** scegliendo il nome
   che vuoi mantenere. Questo aggiorna tutte le schede collegate.
7. Apri la scheda rimasta e controlla la bibliografia. Una nuova importazione
   usa le identità esterne trasferite e non ricrea la scheda eliminata.

L'unione è transazionale e riguarda solo la coppia scelta. La scheda duplicata
viene rimossa **dopo** il trasferimento dei dati. Configurazioni, specifiche,
commercializzazioni, vendite, recensioni, fatti e fotografie conservano i propri
ID e le proprie citazioni. I file fotografici non sono cancellati.
Configurazioni omonime restano separate con un suffisso identificativo: non
si fondono automaticamente varianti tecniche potenzialmente diverse. La
reimportazione con la stessa identità esterna ritrova la configurazione
originaria tramite lo storico, anche se il nome ha richiesto quel suffisso.

Upload originali e decisioni restano conservati. Le righe, le identità esterne
e i riferimenti delle asserzioni vengono reindirizzati alla scheda mantenuta;
lo stato di verifica non viene promosso. Lo **Storico delle riconciliazioni**
permette di scaricare righe, riferimenti e collegamenti alle fonti precedenti
all'unione. Non è un pulsante di ripristino automatico del database.
Un cambiamento dopo l'anteprima ne impedisce l'applicazione: ricreala.

## Alias e distinzione fra famiglie e modelli

Il riconoscimento è esplicito e circoscritto al produttore: Apple/Apple Computer,
IBM/International Business Machines, Commodore/Commodore Business Machines e
DEC/Digital Equipment Corporation. Esempi di modelli: Apple Macintosh 128K e
Macintosh 128K; IBM Personal Computer 5150 e IBM PC 5150; C64 e Commodore 64.
Il registro completo è `backend/app/importing/identity.py`. Gli alias sono
regole di abbinamento del catalogo, non verifiche delle affermazioni storiche.

Con una sola corrispondenza l'importazione la riusa, conservando il nome già
scelto; con più schede equivalenti richiede una scelta, senza crearne un'altra.
Gli alias sconosciuti non vengono inventati né abbinati con somiglianza vaga.

**IBM System/360 è una famiglia; IBM System/360 Model 50 è un modello specifico.**
La loro presenza insieme non costituisce una duplicazione. Il pannello e le API
non consentono di unirli come alias. Lo stesso vale per modelli distinti come
PDP-8/PDP-11 e Apple II/Apple IIe. Questo lavoro non introduce una nuova
gerarchia famiglia → modelli.

## Dove si trovano le fonti

Le fonti del campione sono sulle schede importate e sui singoli dati tecnici.
Se prima dell'aggiornamento si erano create due schede, quella dimostrativa
originale poteva risultare senza fonti mentre la nuova aveva le citazioni.
La riconciliazione le riunisce sulla scheda scelta.

La scheda ora mostra le citazioni accanto alle specifiche e raccoglie nella
bibliografia anche quelle collegate a specifiche, commercializzazioni, vendite,
recensioni e fatti. Non presenta più «nessuna fonte verificata» come sinonimo
di «nessuna fonte». Presenza della citazione e verifica sono cose distinte:
gli stati e le decisioni umane restano in **Fonti e verifiche** nell'importazione.

## Perché mancano i prezzi

**Il campione RetroFlops di 19 modelli non contiene prezzi.** La trasformazione
seleziona CPU, misure CPU/RAM e date disponibili. Non sono state aggiunte nuove
fonti di prezzo o trascrizioni di listini/manuali in questa correzione.
Un listino citato come fonte non implica che il prezzo sia già un campo importato.

L'anteprima mostra **Prezzi presenti nel file: 0** e la scheda segnala che
non contiene un prezzo documentato. Per aggiungerlo occorrono un valore,
valuta, mercato, contesto/data e fonte appropriati, tramite editor o JSON/CSV
autorizzato. L'importatore supporta già questi campi; un prezzo mancante
non cancella quello eventualmente esistente e non diventa zero o una stima.

## Verifiche di questa correzione

- Backend SQLite: 120 test passati, uno specifico PostgreSQL saltato.
- Backend PostgreSQL in Docker: 121 test passati.
- Frontend: 23 test passati; build Vite riuscita.
- Browser su Compose: importazione, conflitti, riconciliazione con conferma,
  conservazione ID/citazioni/configurazioni e layout a 320/390 px riusciti.
- Campione reale su SQLite e PostgreSQL separati: 4 precedenti importati, poi 19 righe
  abbinate senza mapping manuale: 11 nuovi, 4 aggiornati, 4 invariati;
  totale 25 schede. Replay: 19 invariati. Due conflitti di descrizione
  (Macintosh 128K e IBM PC 5150), zero conflitti di alias e zero verifiche automatiche.

Non è stata applicata alcuna unione o importazione al database dell'utente.
Restano gli avvisi non bloccanti su dimensione del bundle Vite e TestClient/httpx.
