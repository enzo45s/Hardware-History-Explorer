# Completamento delle categorie delle schede già caricate

I cinque lotti MAME conservano la categoria generica **Calcolatore**, perché
il registro dell'emulatore non fornisce una tassonomia storica equivalente
a quella di HHE. Lo svuotamento precedente rimuoveva anche le categorie
dimostrative: non sono state cancellate dall'importatore MAME.

Per arricchire il catalogo già caricato, senza svuotarlo o ripetere gli upload:

1. Aggiorna e ricostruisci l'applicazione.
2. Apri **Amministrazione → Importazioni → Completa le categorie delle schede generiche**.
3. Premi **Prepara anteprima categorie** e controlla conteggi e prime proposte.
4. Premi **Applica le categorie proposte**.

L'azione conserva ID, caratteristiche tecniche, fotografie, prezzi, fonti e
ogni categoria precedente. Salta le schede già dotate di una categoria
specifica, comprese quelle personalizzate. **Calcolatore** resta associata,
ma nelle schede e nelle copertine la categoria specifica appare per prima.
Puoi correggere o completare le assegnazioni nell'editor amministrativo.

## Criteri e copertura

Le regole versionate sono in `backend/app/importing/classification.py`.
Riconoscono famiglie esplicite insieme al produttore, ad esempio Macintosh,
Apple II, Commodore 64, IBM PC, IBM RT, PDP/MicroVAX e HP9000/3xx. Per MSX
utilizzano anche la provenienza già registrata nel driver MAME. Non deducono
la categoria dalla sola marca, dall'anno o dal quantitativo di RAM.

Sul pacchetto da 1.139 schede, partendo dalle sole categorie generiche:

| Categoria proposta | Schede |
|---|---:|
| Home computer | 357 |
| Personal computer | 172 |
| Workstation | 44 |
| Portable | 25 |
| Minicomputer | 11 |
| Microcomputer | 1 |
| Totale riconosciuto | **610** |
| Non riconosciuto, resta generico | **529** |

Non tutte le denominazioni del corpus identificano univocamente una famiglia;
quelle non riconosciute restano da classificare. Il vocabolario comprende
anche Mainframe e Supercomputer, ma questi conteggi non indicano schede MAME
appartenenti a tali categorie. Una voce del filtro può quindi avere zero risultati.
Categorie specifiche già presenti possono ridurre il numero di aggiornamenti.

## Provenienza e controllo

Queste assegnazioni sono **classificazioni editoriali HHE da verificare**,
non nuove attestazioni storiche di MAME. Ogni assegnazione crea un'asserzione
`pending` con regola, versione e categorie precedenti; la fonte è denominata
**HHE · Classificazione editoriale v1**. Non si attribuisce a MAME la conferma
di una categoria che il suo export non contiene.

Trovi l'operazione nelle **Ultime importazioni** e le asserzioni in
**Fonti e verifiche**. I JSON originali dell'operazione sono scaricabili come
per gli altri lavori. L'anteprima è invalidata se cambiano le assegnazioni
proposte; applicazione e audit sono atomici. L'azione considera al massimo
1.000 schede per volta e può essere ripetuta senza duplicare le associazioni.
Non viene eseguita automaticamente all'avvio e non richiede nuove tabelle.

## Verifica del 14 novembre 2026

Su PostgreSQL isolato sono state aggiornate le 610 schede riconosciute del
corpus reale. Controllate tutte le 1.139 schede prima e dopo: stessi ID e nomi,
configurazioni, specifiche, fotografie, prezzi, vendite, recensioni e fatti
conservati. Una seconda applicazione aggiorna zero schede; restano 529 casi
generici. Nessuna modifica è stata applicata al database dell'utente.
