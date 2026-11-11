# Loghi del progetto

Copia qui i due PNG originali, con questi nomi esatti:

- `logo-light.png`: logo con lettere blu per il tema chiaro.
- `logo-dark.png`: logo con lettere bianche per il tema Fosfori verdi.

Questa cartella contiene le istruzioni; i PNG allegati nella chat non erano
accessibili come file nell'ambiente di lavoro e non sono inclusi nel repository.
Non sono stati ricreati o sostituiti con immagini generate.

Si consiglia uno sfondo trasparente. Le immagini mantengono proporzioni e colori
originali: il frontend non applica filtri né ritagli. Nel tema chiaro il logo
compare su un piccolo pannello chiaro, poiché la barra laterale è blu scuro;
nel tema scuro il pannello è trasparente.

Il logo segue il tema effettivo, sia in modalità Sistema sia con selezione
manuale. Se il PNG del tema corrente manca o non si carica, viene mostrato il
marchio precedente con icona e nome.

Vite include automaticamente questi file nella build. Dopo averli aggiunti,
ricostruisci il frontend con `docker compose up --build -d web` dalla radice
del progetto (il servizio frontend si chiama `web`).

Verifiche: 21 test frontend e build Vite superati. In Chromium sono stati
controllati scelta manuale/automatica, cambio del tema del sistema, ripristino
dopo ricarica, file mancanti e recupero, nome accessibile e layout da 320 a
1440 px. I controlli di caricamento usano un PNG di prova intercettato dal test:
la resa visiva e la trasparenza dei loghi originali restano da verificare quando
i due file saranno disponibili.
