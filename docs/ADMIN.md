# Pannello amministrativo

Apri **Amministrazione** dal menu laterale. Le sezioni **Calcolatori** e **Fonti** offrono un elenco ricercabile, inserimento e modifica. I pulsanti Salva applicano le modifiche al database; Annulla le abbandona. Prima di cambiare sezione o elemento, lasciare il pannello o chiudere la pagina, vengono segnalate le modifiche non salvate.

## Calcolatori

1. Premi **Nuovo calcolatore**, oppure scegli un elemento dell'elenco per modificarlo.
2. Inserisci nome del modello, produttore e descrizione. Puoi selezionare categorie e fonti bibliografiche.
3. Se necessario, aggiungi un produttore o una categoria dalla sezione espandibile. Questi riferimenti vengono creati immediatamente e rimangono disponibili anche se annulli la scheda.
4. Aggiungi commercializzazioni con mercato, data di lancio/fine, prezzo, valuta, tipo di prezzo e fonti. È possibile aggiungere nuovi mercati.
5. Aggiungi configurazioni e specifiche: componente, proprietà, valore **numerico oppure testuale**, unità e fonti. Un valore numerico zero è valido.
6. Premi **Salva calcolatore**. L'archivio, i filtri, la timeline e le statistiche si aggiornano. **Apri scheda e fotografie** apre il normale dettaglio, da cui usare la gestione fotografica esistente.

Le date storiche accettano `AAAA`, `AAAA-MM` oppure `AAAA-MM-GG`; la precisione viene conservata. Lascia vuoti i dati sconosciuti. Il pannello non inventa una data di lancio quando non è disponibile.

Le modifiche preservano gli identificativi di configurazioni, specifiche e commercializzazioni e i collegamenti bibliografici. Fotografie, vendite, recensioni e fatti non vengono modificati dal salvataggio. La rimozione di una configurazione, specifica o commercializzazione richiede conferma e viene applicata al salvataggio; annullando il modulo, anche queste rimozioni vengono abbandonate. Non vengono offerte cancellazioni di interi calcolatori o fonti.

## Fonti

In **Fonti**, crea o modifica titolo, autore, editore/pubblicazione, URL HTTP(S), tipo di fonte, data di pubblicazione e consultazione. Il titolo è obbligatorio. Gli URL non possono incorporare credenziali. Il tipo può essere, per esempio, `website`, `book`, `manual`, `article` o `archive`; i valori già presenti vengono mantenuti.

Le date delle fonti sono date complete facoltative. Dopo aver creato una fonte, puoi associarla a un calcolatore, a una commercializzazione o a una specifica. Modificare il titolo o altri dati di una fonte aggiorna anche le schede che la citano, conservando associazioni ed evidenze esistenti.

## API e compatibilità

| Metodo | Percorso | Funzione |
| --- | --- | --- |
| POST | `/api/computers` | Crea un calcolatore |
| GET | `/api/admin/computers/{id}` | Dati completi per il modulo, con ID e precisione delle date |
| PUT | `/api/computers/{id}` | Salva una scheda completa |
| POST | `/api/sources` | Crea una fonte |
| GET / PUT | `/api/sources/{id}` | Legge o modifica una fonte |
| POST | `/api/manufacturers` | Crea un produttore |
| POST | `/api/categories` | Crea una categoria |
| POST | `/api/markets` | Crea un mercato |

La GET pubblica `/api/computers/{id}` conserva la struttura della scheda. Le risposte fonti includono anche autore e date. Lo schema database non cambia: vengono usate le tabelle già presenti, senza migrazioni aggiuntive.

La PUT riceve nome, produttore e i dati del modulo. Le liste `category_ids`, `source_ids`, `releases` e `configurations` omesse non sostituiscono le relazioni esistenti; una lista vuota ne richiede esplicitamente lo svuotamento. Le liste annidate del modulo sono complete e mantengono gli ID delle righe esistenti. ID appartenenti ad altri calcolatori o configurazioni sono rifiutati. Dati e riferimenti vengono validati prima dell'applicazione; un errore impedisce salvataggi parziali.

Il pannello usa la modalità locale single-user già prevista dal progetto, senza login separato. Le porte Docker rimangono limitate a localhost. Un'eventuale esposizione remota richiede un sistema di autenticazione e autorizzazione.

## Verifiche

Test automatici coprono creazione/modifica di calcolatori e fonti, visibilità nel catalogo, date, valori zero, validazione dei riferimenti, atomicità degli errori, modifica/rimozione di righe annidate e conservazione di foto, dati storici ed evidenze bibliografiche. I test frontend verificano la conversione dei moduli nei payload senza perdere ID, precisione o associazioni. La verifica nel browser esercita i moduli, il percorso fotografico esistente, la persistenza, l'aggiornamento del catalogo e l'annullamento delle modifiche.

Esito della verifica di questa versione: **46 test backend superati con PostgreSQL**, **45 superati e 1 specifico PostgreSQL saltato su SQLite**, **8 test frontend superati**. Build frontend e Compose riuscite. Nel browser sono stati verificati creazione/modifica di fonte e calcolatore, produttore nuovo, specifica numerica zero, precisione delle date, fotografia, riapertura della scheda, conservazione dei dati dopo Annulla, aggiornamento del catalogo e assenza di overflow orizzontale a 390 px.
