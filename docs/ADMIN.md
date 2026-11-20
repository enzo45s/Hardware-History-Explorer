# Pannello amministrativo

Apri **Amministrazione** dal menu laterale. Le sezioni **Calcolatori**, **Produttori** e **Fonti** offrono un elenco ricercabile, inserimento e modifica. I pulsanti Salva applicano le modifiche al database; Annulla le abbandona. Prima di cambiare sezione o elemento, lasciare il pannello o chiudere la pagina, vengono segnalate le modifiche non salvate.

## Calcolatori

1. Premi **Nuovo calcolatore**, oppure scegli un elemento dell'elenco per modificarlo.
2. Inserisci nome del modello, produttore e descrizione. Puoi selezionare categorie e fonti bibliografiche.
3. Se necessario, aggiungi un produttore o una categoria dalla sezione espandibile. Questi riferimenti vengono creati immediatamente e rimangono disponibili anche se annulli la scheda.
4. Aggiungi commercializzazioni con mercato, data di lancio/fine, prezzo, valuta, tipo di prezzo e fonti. È possibile aggiungere nuovi mercati.
5. Aggiungi configurazioni e specifiche: componente, proprietà, valore **numerico oppure testuale**, unità e fonti. Un valore numerico zero è valido.
6. Premi **Salva calcolatore**. L'archivio, i filtri, la timeline e le statistiche si aggiornano. **Apri scheda e fotografie** apre il normale dettaglio, da cui usare la gestione fotografica esistente.

Le date storiche accettano `AAAA`, `AAAA-MM` oppure `AAAA-MM-GG`; la precisione viene conservata. Lascia vuoti i dati sconosciuti. Il pannello non inventa una data di lancio quando non è disponibile.

Le modifiche preservano gli identificativi di configurazioni, specifiche e commercializzazioni e i collegamenti bibliografici. Fotografie, vendite, recensioni e fatti non vengono modificati dal salvataggio. La rimozione di una configurazione, specifica o commercializzazione richiede conferma e viene applicata al salvataggio; annullando il modulo, anche queste rimozioni vengono abbandonate.

### Eliminare un calcolatore

Seleziona la scheda nell'elenco e premi **Elimina calcolatore**, poi conferma
il nome mostrato. La cancellazione viene applicata subito, anche se il modulo
contiene modifiche non salvate, che vengono scartate. Annullare la conferma
conserva la scheda.

Sono rimossi la scheda, le configurazioni, le specifiche, i dati commerciali,
vendite, recensioni, note e associazioni fotografiche relative a quel computer.
Fonti, produttore, categorie e mercati restano disponibili. Le selezioni del
confronto e gli elenchi dell'applicazione vengono aggiornati.

Gli originali delle importazioni e le decisioni già registrate restano
conservati. Le corrispondenze attive e i candidati riferiti alla scheda vengono
rimossi; le righe pronte che la utilizzavano vengono saltate, così l'applicazione
del vecchio lotto non la ricrea. Una nuova importazione esplicita può comunque
inserire nuovamente il modello. Le ricerche fotografiche saltano la macchina
eliminata; una risposta già in viaggio non può salvare una foto su di essa.

Uno snapshot dei metadati precedenti resta nella tabella di audit
`catalog_reconciliations`, con tipo `computer_delete`. I file fotografici
locali originali restano sul volume, referenziati nello snapshot; questa azione
non effettua pulizia del disco. Non è disponibile un ripristino automatico
dall'interfaccia. Eliminando l'ultima scheda, il catalogo resta vuoto anche
dopo il riavvio: i dati dimostrativi non vengono ricreati.

## Produttori

Apri **Produttori → Nuovo produttore** oppure scegli un elemento dell'elenco.
Il nome è obbligatorio; paese, data di fondazione e sito HTTP(S) sono facoltativi.
La data di fondazione richiede `AAAA-MM-GG`, coerentemente con la tabella
esistente: lascia vuoto se conosci soltanto l'anno, senza inventare un giorno.
Gli URL non possono contenere credenziali. I nomi duplicati sono rifiutati
anche se differiscono soltanto per maiuscole, spazi o forme Unicode equivalenti.

**Salva produttore** aggiorna i dati conservando l'ID e i computer associati.
La modifica del nome compare nelle schede, nei filtri, nelle analisi e nei
confronti. L'elenco e il modulo mostrano il numero di calcolatori collegati.

**Elimina produttore** è disponibile soltanto quando il conteggio è zero e
richiede conferma. Se è ancora utilizzato, modifica prima il produttore delle
relative schede oppure elimina quelle che non servono. Il backend verifica
nuovamente questo vincolo anche se un altro processo ha modificato l'archivio.
Lo snapshot precedente viene conservato nell'audit con tipo `manufacturer_delete`.

## Fonti

In **Fonti**, crea o modifica titolo, autore, editore/pubblicazione, URL HTTP(S), tipo di fonte, data di pubblicazione e consultazione. Il titolo è obbligatorio. Gli URL non possono incorporare credenziali. Il tipo può essere, per esempio, `website`, `book`, `manual`, `article` o `archive`; i valori già presenti vengono mantenuti.

Le date delle fonti sono date complete facoltative. Dopo aver creato una fonte, puoi associarla a un calcolatore, a una commercializzazione o a una specifica. Modificare il titolo o altri dati di una fonte aggiorna anche le schede che la citano, conservando associazioni ed evidenze esistenti.

## API e compatibilità

| Metodo | Percorso | Funzione |
| --- | --- | --- |
| POST | `/api/computers` | Crea un calcolatore |
| GET | `/api/admin/computers/{id}` | Dati completi per il modulo, con ID e precisione delle date |
| PUT | `/api/computers/{id}` | Salva una scheda completa |
| DELETE | `/api/computers/{id}` | Elimina un calcolatore e i dati dipendenti dal catalogo |
| POST | `/api/sources` | Crea una fonte |
| GET / PUT | `/api/sources/{id}` | Legge o modifica una fonte |
| POST | `/api/manufacturers` | Crea un produttore |
| GET | `/api/manufacturers` | Elenco con metadati e numero di calcolatori |
| GET / PUT | `/api/manufacturers/{id}` | Legge o modifica un produttore |
| DELETE | `/api/manufacturers/{id}` | Elimina un produttore non utilizzato; 409 se collegato a computer |
| POST | `/api/categories` | Crea una categoria |
| POST | `/api/markets` | Crea un mercato |

La GET pubblica `/api/computers/{id}` conserva la struttura della scheda. Le risposte fonti includono anche autore e date. Lo schema database non cambia: vengono usate le tabelle già presenti, senza migrazioni aggiuntive.

La PUT riceve nome, produttore e i dati del modulo. Le liste `category_ids`, `source_ids`, `releases` e `configurations` omesse non sostituiscono le relazioni esistenti; una lista vuota ne richiede esplicitamente lo svuotamento. Le liste annidate del modulo sono complete e mantengono gli ID delle righe esistenti. ID appartenenti ad altri calcolatori o configurazioni sono rifiutati. Dati e riferimenti vengono validati prima dell'applicazione; un errore impedisce salvataggi parziali.

Per i produttori, POST/PUT ricevono `name`, `country`, `founded`, `website`.
La PUT preserva i campi facoltativi omessi; `null` ne richiede lo svuotamento.
Le DELETE riuscite restituiscono 204, gli ID inesistenti 404. Non sono
necessarie nuove tabelle o migrazioni per queste funzioni.

Il pannello usa la modalità locale single-user già prevista dal progetto, senza login separato. Le porte Docker rimangono limitate a localhost. Un'eventuale esposizione remota richiede un sistema di autenticazione e autorizzazione.

## Verifiche

Test automatici coprono creazione/modifica di calcolatori e fonti, visibilità nel catalogo, date, valori zero, validazione dei riferimenti, atomicità degli errori, modifica/rimozione di righe annidate e conservazione di foto, dati storici ed evidenze bibliografiche. I test frontend verificano la conversione dei moduli nei payload senza perdere ID, precisione o associazioni. La verifica nel browser esercita i moduli, il percorso fotografico esistente, la persistenza, l'aggiornamento del catalogo e l'annullamento delle modifiche.

Esito della verifica di questa versione: **46 test backend superati con PostgreSQL**, **45 superati e 1 specifico PostgreSQL saltato su SQLite**, **8 test frontend superati**. Build frontend e Compose riuscite. Nel browser sono stati verificati creazione/modifica di fonte e calcolatore, produttore nuovo, specifica numerica zero, precisione delle date, fotografia, riapertura della scheda, conservazione dei dati dopo Annulla, aggiornamento del catalogo e assenza di overflow orizzontale a 390 px.

### Gestione produttori ed eliminazione delle schede

340 test PostgreSQL superati; 339 SQLite superati con uno specifico PostgreSQL
saltato; 27 frontend superati. Build React e avvio Docker Compose riusciti.
I nuovi test verificano CRUD dei produttori, nomi duplicati, validazione delle
date e degli URL, conteggi, modifica senza perdita di associazioni, rimozione
dei dati dipendenti, fonti e originali conservati, invalidazione dei candidati
e dei collegamenti ETL, gestione delle code e cancellazione durante una ricerca.
Controllato anche il riavvio con catalogo vuoto dopo l'ultima eliminazione.

La suite Chromium `npm run test:browser:admin`, inclusa in CI prima del reset,
esegue aggiunta/modifica/eliminazione del produttore e creazione/eliminazione
dei soli calcolatori sintetici che inserisce, con conferme annullate e accettate,
protezione del produttore usato, pulizia della selezione del confronto,
persistenza e layout a 320/390 px. Sul catalogo PostgreSQL isolato di 1.105
schede, il conteggio iniziale è stato ripristinato al termine della prova.
Ripetuta con successo anche la suite browser preesistente di importazione,
conflitti, verifiche, HTML 1000bit e confronto, con layout a 320 px.
Le porte di test sono locali; nessun accesso al database Windows dell'operatore.

Restano gli avvisi preesistenti del bundle Vite oltre 500 kB e della deprecazione
Starlette TestClient/httpx.
