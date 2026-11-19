# Cenni storici in italiano

La sezione **Amministrazione → Cenni storici** ricerca descrizioni storiche
documentate per le schede vuote o con la vecchia frase preimpostata, ad esempio
«HP 85 è un calcolatore di HP. Le configurazioni censite riportano HP-Capricorn.».
La sola descrizione delle CPU non viene considerata una ricerca storica.

## Utilizzo sul Mac o su Windows

Aggiorna il branch che contiene le modifiche, mantenendo il progetto Docker
che contiene il tuo archivio:

```bash
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

1. Apri **http://localhost:8080** e ricarica la pagina.
2. Apri **Amministrazione → Cenni storici**.
3. Premi **Cerca cenni storici**. Il sistema esamina tutte le schede presenti
   all'avvio, conserva quelle già curate e cerca i testi mancanti.
4. Lascia aperto il pannello: una richiesta per volta, con almeno due secondi
   di intervallo e rispetto delle attese imposte dalla fonte. Puoi mettere in
   pausa o chiudere la pagina; tornando al pannello premi **Riprendi ricerca
   storica**. Il lavoro prosegue dallo stesso sistema.
5. Controlla descrizioni aggiornate, testi non trovati e casi ambigui.
   **Scarica resoconto completo** contiene tutti gli esiti, anche quelli che
   non rientrano negli ultimi dieci mostrati. Una successiva nuova ricerca
   ritenta solo le descrizioni ancora vuote o preimpostate e include le nuove
   schede; non riscrive quelle già completate.
   Se hai già esiti senza testo, metti in pausa oppure attendi il termine e
   premi **Riprova i sistemi senza testo**: rimette in coda solo gli esiti
   `no_match` e `search_error` ancora aggiornabili, mantenendo risultati già
   riusciti, ricerche precedenti e originali. Riparte anche se la ricerca era
   stata completata con la versione precedente del motore.
   Dopo una ricerca completata, **Riprova gli abbinamenti migliorati (N)**
   limita invece il ritentativo ai vecchi esiti con pagine candidate o con
   nomi interessati dalle nuove regole. N è il numero di casi da riesaminare,
   non di descrizioni garantite. Le schede già completate, curate, modificate
   o saltate non vengono rimesse in coda. Un esito negativo del motore attuale
   non viene riproposto continuamente da questo comando.
6. **Fonti e verifica** apre il passaggio utilizzato, la licenza, il valore
   precedente e la revisione umana facoltativa. Il download dell'originale
   conserva la risposta JSON della fonte consultata.

Non occorrono chiavi OpenAI, nuovi pacchetti o servizi di traduzione. La ricerca
**non effettua chiamate AI a pagamento** e non contatta fonti in inglese.
Non è possibile garantire un'introduzione per tutti i sistemi: le fonti italiane
disponibili coprono solo parte del catalogo. I casi irrisolti restano nel
resoconto, senza testi inventati o traduzioni automatiche.

## Fonte e criteri di abbinamento

Viene usata l'API ufficiale di [Wikipedia in italiano](https://it.wikipedia.org/w/api.php),
con User-Agent identificativo, `maxlag=5`, timeout e dimensione massima della
risposta. Non vengono scansionati siti né aperti URL scelti dai risultati.
Ogni passo esegue una sola richiesta, con al massimo cinque voci candidate.
Se non basta il nome esatto fra virgolette con la parola «computer», seguono
tentativi con le sole parole chiave **marca e modello**, poi con il modello
senza virgolette e infine la lettura della pagina completa. I tentativi sono
salvati separatamente e distanziati di almeno due secondi; per sistema sono
previste al massimo cinque strategie, oltre agli eventuali ritentativi dopo
errori di rete, interrompendosi appena trova un testo
utilizzabile. Il pannello e il resoconto mostrano le query usate.

Vengono riconosciuti anche alias espliciti come `Apple //c` → `Apple IIc`,
`PowerBook180` → parole chiave `PowerBook 180` e le grafie note del produttore,
incluse differenze nella punteggiatura societaria. Un codice numerico, ad esempio
«400», non autorizza a sostituire la voce «Atari 400» con la pagina del numero.

Sono richiesti un modello corrispondente, il produttore nel testo, un'introduzione
di almeno 120 caratteri con informazioni storiche e una revisione identificata.
Si normalizzano separatori, marchi e alias espliciti già riconosciuti dal catalogo.
Le pagine di disambiguazione, i testi troppo brevi, le famiglie diverse dal
modello e gli abbinamenti plurimi non vengono applicati automaticamente.
Le introduzioni dirette comprendono al massimo due paragrafi. Per i modelli
trattati nella pagina di famiglia si richiede un redirect ufficiale dal modello
alla relativa sezione, oppure una corrispondenza esplicita documentata come
BBC Model A/B nella voce BBC Micro di Acorn. Si estraggono soltanto passaggi
che identificano quel modello, preceduti da una frase di contesto della famiglia.
Il testo complessivo resta entro 1.500 caratteri e termina su una frase completa;
non viene riscritto da un modello linguistico. Suffissi come XL, XE, c e +
restano distinti. Non viene assegnata a ogni macchina l'intera storia della famiglia.

Gli alias di ricerca riconoscono anche **Digital Equipment** per DEC e le
denominazioni societarie **NeXT / Next Software Inc**. Per Apple, il prefisso
di linea **Macintosh PowerBook** può corrispondere al titolo **PowerBook**,
conservando numero, Duo e suffissi come `c`: PowerBook 180c non diventa 180.
Queste regole non rinominano computer o produttori nel database.
Le ricerche usano inoltre il nome pubblico senza attributi tra parentesi
tonde/quadre o suffissi video, per tutti i modelli. La pulizia delle schede
esistenti si applica da **RAM e varianti**, come descritto in
[CATALOG_QUALITY.md](CATALOG_QUALITY.md). Numeri e suffissi fuori dalle parentesi
restano significativi: PDP-11/20 non diventa PDP-11, né 180c diventa 180.

Due corrispondenze italiane sono documentate esplicitamente:

- **IBM PC 5150**: voce **PC IBM**, che deve identificare esplicitamente
  «IBM 5150» nel testo. Non viene utilizzata per PC XT o AT.
- **HP 85**: due passaggi della voce **HP 9800** descrivono il passaggio alla
  serie 80, l'HP 85, Corvallis, BASIC e il posizionamento rispetto agli HP 9845.
  Una breve sintesi italiana preparata su questi passaggi viene applicata
  soltanto se entrambi sono ancora presenti nella risposta. Non viene
  attribuita agli altri modelli della serie e non viene dedotta una data di lancio.

I testi derivati da Wikipedia mostrano nella scheda attribuzione ai collaboratori,
collegamento alla revisione consultata e [licenza CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Per redistribuire testi derivati occorre conservarne attribuzione e licenza.
La citazione non certifica la correttezza delle affermazioni: le asserzioni
sono importate **pending**, mai verificate automaticamente.

## Conservazione e integrazione

Le descrizioni già curate rimangono intatte, anche se brevi. Il riconoscimento
del vecchio testo è intenzionalmente preciso: una nota aggiunta manualmente
alla frase preimpostata impedisce la sostituzione automatica. Non vengono
modificati specifiche, configurazioni, prezzi, date, fotografie o fonti esistenti.

Ogni aggiornamento conserva il testo precedente, il risultato della ricerca,
la risposta originale e un'asserzione nel sistema di importazione esistente.
Catalogo, timeline e assistente leggono la nuova descrizione dallo stesso campo
`Computer.description`; l'assistente riceve anche fonte e stato dell'asserzione.

Le due nuove tabelle `history_research_jobs` e `history_research_items` vengono
create all'avvio senza modificare le tabelle esistenti. La migrazione esplicita,
ripetibile su un database già configurato, è:

```bash
cd backend
python -m migrations.history_research
```

Richiede `DATABASE_URL`. Il backup completo include code e originali. Una
modifica manuale, rinomina o eliminazione durante la richiesta impedisce la
sovrascrittura. Lo svuotamento dell'archivio archivia anche la coda, invalidando
le richieste in corso. I tentativi simultanei da due schede del browser vengono
serializzati con una lease nel database; un riavvio può richiedere fino a
90 secondi per far scadere una richiesta interrotta.

API locali: `GET/POST /api/admin/history`, `POST /{id}/step`, `/pause`, `/resume`,
`/skip`, `/retry-unresolved` e `GET /{id}/report`, tutti sotto `/api/admin/history`. Un errore di rete
mette in pausa conservando il sistema corrente; **Salta il sistema corrente**
permette di avanzare esplicitamente. Queste funzioni mantengono il modello
single-user locale: Compose espone API e frontend soltanto su loopback.

## Verifiche del 18 novembre 2026

La prova con API reali su un database temporaneo di undici sistemi ha aggiornato
dieci descrizioni: IBM System/360, Altair 8800, Apple II, Commodore 64, IBM PC 5150,
Macintosh 128K, Compaq Portable, Cray-1, PDP-11 e HP 85. Sun-1 non ha trovato un
abbinamento italiano idoneo. Il database di prova è stato rimosso al termine:
nessuna modifica al catalogo locale dell'operatore e nessuna importazione
dichiarata su tutti i 1.105 sistemi.

I test automatici coprono conservazione del testo manuale, abbinamenti e
ambiguità, evidenze HP 85 e PC 5150, fonti pending, originali, replay senza
duplicati, errori, attese e richieste simultanee, reset e modifiche concorrenti.
La prova browser usa un'API sintetica isolata, verifica pausa/ripresa dopo un
reload, attribuzione, contesto visibile, resoconto e layout 320/390 px.

Le fixture `wikipedia-it-hp9800.json` (revisione 148020204) e
`wikipedia-it-pcibm.json` (revisione 149844403) conservano risposte effettivamente
consultate dell'API italiana; i testi appartengono ai collaboratori di Wikipedia
e sono riutilizzati secondo CC BY-SA 4.0. I casi di errore di rete e l'API usata
nella prova browser sono sintetici.

## Diagnosi del resoconto e verifica del 19 novembre 2026

Il resoconto ricevuto comprende 1.105 schede: 80 aggiornate, 101 conservate,
922 senza testo e 2 saltate esplicitamente. Le due saltate sono Acorn R260 e
Apple ][+. Il pannello ora mostra anche saltate, schede modificate/rimosse e
query rifiutate, così il riepilogo rende conto di tutti gli esiti.

Sono stati riprodotti falsi negativi su sei fonti italiane effettivamente
consultate: **PDP-1**, **Epson HX-20**, **Olivetti M15**, **NeXTcube**, **Atari 800**
e **Macintosh PowerBook 180**. Le cause erano grafie del produttore, il prefisso
Macintosh, introduzioni brevi ma storicamente pertinenti e il controllo finale
di un numero di modello già identificato dal redirect alla sezione di famiglia.
I sei casi passano dopo le correzioni, con URL della revisione e licenza; questo
non certifica le affermazioni storiche né modifica il catalogo locale.

La selezione mirata sul report ricevuto propone **45 casi**, conservando i
risultati già riusciti e gli esiti esclusi. Alcuni possono ancora non avere un
testo utilizzabile: una pagina candidata non autorizza ad applicarla al modello.
I dati di questo report non sono inclusi nel repository.

I dieci ultimi esiti indicati dall'operatore sono stati controllati anche con
query marca/modello sull'API italiana. Questi tentativi hanno restituito nessuna
pagina oppure risultati estranei, senza una descrizione applicabile. Non è una
dimostrazione dell'assenza di ogni possibile fonte italiana. La copertura resta
limitata a Wikipedia italiana; non vengono introdotte traduzioni o chiamate AI.

La fixture `wikipedia-it-history-recovery.json` conserva le sei risposte ufficiali
consultate, con i rispettivi identificativi di revisione. Testi dei collaboratori
di Wikipedia, licenza **CC BY-SA 4.0**, come le altre fixture di questa guida.
Il browser usa invece dati sintetici per verificare il nuovo ritentativo,
il conteggio degli esiti, la pausa/ripresa, la conservazione dei testi e il mobile.

Con l'ampliamento della ricerca sono state consultate anche le voci italiane
**PowerBook 180** (134995523), **BBC Micro** (149844331) e **Atari 8-bit**
(153297259), conservate nelle fixture `wikipedia-it-powerbook180.json`,
`wikipedia-it-bbc-micro.json` e `wikipedia-it-atari-family.json` con la stessa
licenza. Verificati contro l'API reale PowerBook 180, BBC Model B, Atari 130XE,
Atari 400 e Atari 800XL in database temporanei: il catalogo locale non viene
modificato da queste prove. I test automatici controllano anche i falsi
abbinamenti con numeri, produttori diversi e varianti della stessa famiglia.
