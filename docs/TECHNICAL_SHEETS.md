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
- RAM di riferimento, RAM documentata, capacità massima e opzioni non diventano
  un'unica dotazione di base; unità ambigue non vengono interpretate arbitrariamente.
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
