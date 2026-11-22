# Una scheda tecnica per sistema

Le schede pubbliche riuniscono i profili regionali e i dati complementari delle
fonti. Per esempio, sull'Atari 400 i blocchi **NTSC**, **PAL** e **Scheda tecnica**
compongono una sola tabella **Scheda tecnica**: un dato identico compare una volta,
un dato presente in una sola fonte viene aggiunto. Le etichette PAL/NTSC e le
frequenze video regionali 50/60 Hz sono omesse dalla vista pubblica, per tutti
i modelli; restano negli originali amministrativi.

## Aggiornamento

```bash
git pull --ff-only origin feat/historical-data-import
docker compose -p hhe-import-test up --build -d --wait
```

Ricaricare la pagina e aprire la scheda del sistema. Non occorre ripetere
importazioni, svuotare l'archivio o avviare un accorpamento amministrativo.
La nuova presentazione si applica ai dati già presenti e alle importazioni future.
Per ripulire anche i **nomi del catalogo**, aprire **Amministrazione → RAM e
varianti → Analizza varianti da accorpare → Accorpa i gruppi selezionati**.
L'operazione unisce i duplicati e rinomina anche le schede isolate con attributi.
La ricerca delle descrizioni può continuare sul proprio archivio; il riavvio
Docker la interrompe temporaneamente, quindi riaprire il pannello e riprenderla
se risulta in pausa.

## RAM: un campo principale e una riga per le opzioni

Nel confronto e nelle schede pubbliche, **RAM** riunisce le diciture
«Capacità», «Capacità riportata», «Dotazioni riportate» e, quando mancano
quantità documentate, il valore di riferimento. Le etichette delle fonti
non generano più righe diverse fra i sistemi confrontati.

La riga facoltativa **RAM · Opzioni di memoria**, subito sotto, raccoglie
le scelte disponibili, le espansioni e i limiti minimi/massimi, con la
relativa qualificazione. Un massimo non diventa la RAM installata. Se
esistono solo limiti o annotazioni, la riga principale indica «Non documentata».

Valori equivalenti espressi in unità esatte vengono riuniti. La RAM viene
mostrata con le diciture storiche KB/MB/GB: per esempio 4096 KiB diventa
4 MB nella vista. I valori interni non cambiano. KB/MB originari ambigui,
bit e parole non sono equiparati arbitrariamente a quantità IEC.

Una quantità documentata ha precedenza sul valore di riferimento. Un
riferimento differente resta una nota nella stessa cella, con le sue fonti;
non viene inventata un’opzione di memoria per riconciliarlo. Se le quantità
documentate sono discordanti, la cella conserva entrambe e segnala la
differenza. Gli attributi RAM e le indicazioni non quantificabili rimangono
note collegate alla riga, senza moltiplicare le caratteristiche da confrontare.
Memoria video e banchi nominati conservano il proprio ambito e non vengono sommati.

La selezione di una configurazione limita quantità e opzioni a quella
configurazione. La vista «Tutte le configurazioni» mantiene i valori distinti
e segnala la copertura parziale. Originali, proprietà, unità, ID e fonti
rimangono disponibili nelle API, nell’editor e nell’audit. Non serve una
migrazione, una nuova importazione o una revisione delle unità per applicare
questa presentazione ai dati già presenti.

Verifiche: 43 test frontend superati, compilazione React e Docker; prova browser
di confronto e scheda con alias RAM, opzioni adiacenti, scelta indipendente
delle configurazioni, dati/fonti originali conservati e layout a 320/390 px.
Sulla copia fornita dei 1.133 sistemi, il confronto conserva al massimo due
righe RAM per sistema e tutte le fonti/ID; le 902 schede con campi RAM passano
da 1.428 a 1.369 righe. Il database sul Mac non è modificato da remoto.

## Differenze che restano visibili

- Quantità RAM, processori/architetture, memorie di massa e tastiere differenti
  possono identificare configurazioni distinte. Le configurazioni nominate e gli
  alias approvati rimangono separati quando non c'è una regola sicura per unirli.
- PAL/NTSC/SECAM e 50/60 Hz non creano da soli schede hardware separate e
  non compaiono come dettagli nella scheda tecnica. La frequenza CPU e la
  risoluzione rimangono, con i valori documentati distinti senza etichette video;
  non viene scelto arbitrariamente un valore principale. La frequenza di un
  monitor moderno (ad esempio 144 Hz) non viene eliminata.
- I blocchi generici di 1000bit, documentazione tecnica, Wikidata e AppleDB non
  costituiscono di per sé nuove configurazioni.
- Se una fonte generica riguarda un sistema con più configurazioni, viene
  aggiunta a una configurazione solo quando l'ambito è univoco, mediante alias
  approvato o caratteristiche compatibili. Altrimenti compare una sola volta
  tra i **Dati generali del sistema**, senza copiare il dato in tutte le varianti.
- Valori discordanti non vengono cancellati o risolti automaticamente. Il
  riepilogo conserva le alternative, le fonti e gli ID delle specifiche originali.
- Il riepilogo RAM distingue quantità, limiti, opzioni e note nella presentazione
  descritta sopra; non attesta una dotazione di base dalla sola presenza di un
  riferimento e non interpreta arbitrariamente unità ambigue.
- Processori secondari e componenti ripetuti mantengono i rispettivi ruoli.

Catalogo, confronto e contesto dell'assistente utilizzano la medesima vista.
Quando esiste una sola scheda, il confronto non propone un selettore ridondante.
Gli ID di configurazioni precedentemente selezionate risolvono alla nuova vista
che li contiene. Il confronto non eredita dati da altre configurazioni hardware.

## Conservazione e verifica

La vista tecnica è una proiezione di lettura e non modifica i dati salvati.
L'accorpamento/rinomina dei nomi è un'operazione separata del pannello, che
conserva snapshot e alias. Gli originali rimangono nell'editor, nelle asserzioni
e nelle importazioni, così aggiornamenti incrementali e revisione delle fonti
continuano a usare gli stessi identificativi. I prezzi non vengono modificati.

Test automatici coprono l'Atari 400 del dataset distribuito, dati sintetici con
clock/video differenti, fonti complementari, molteplicità dei componenti,
ambiti PAL/NTSC, varianti PET, selezione nel confronto e conservazione dei dati
tramite API e amministrazione. La prova browser controlla una sola tabella CPU,
i dati senza dettagli video regionali e la permanenza dei tre profili nell'editor.
I test usano copie isolate: il database locale dell'operatore non viene raggiunto.
