# Seconda ricerca fotografica: NEC, Kaypro, Daewoo e Silicon Graphics

Ricerca del **25 novembre 2026**, successiva alla revisione tecnica del catalogo.
Il nuovo pacchetto propone **45 immagini per schede esistenti**:

| Produttore | Immagini nuove |
|---|---:|
| NEC | 22 |
| Daewoo | 11 |
| Kaypro Corporation / Non-Linear Systems | 8 |
| Silicon Graphics | 4 |

Sono **20 fotografie** e **25 immagini da cataloghi originali**, con fonte,
crediti, condizioni, motivazione dell’abbinamento e impronta SHA-256 del file
controllato. I file originali rimangono sui rispettivi archivi: nessun binario
fotografico viene distribuito nel repository.

## Utilizzo locale

Sul branch aggiornato, nella cartella del progetto:

```bash
git pull
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima di sola lettura, poi applicazione esplicita:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.catalog_photos
docker compose -p hhe-import-test exec api python -m app.importing.catalog_photos --apply
```

Non occorre reimportare un dump o ripetere i supplementi precedenti. Il comando
non parte automaticamente all’avvio e non va sostituito con il caricamento del
JSON nel modulo generico. Usa solo le schede presenti e non ambigue; riconosce
anche il precedente nome **PC** del Kaypro PC e gli alias approvati del catalogo.

**Tutte le gallerie e copertine già presenti vengono conservate**, comprese le
foto assegnate automaticamente. Il pacchetto completa soltanto schede prive di
immagini. Non crea computer o produttori, non rinomina modelli e non cambia
RAM, specifiche, descrizioni, date, prezzi, configurazioni o verifiche.

L’applicazione è transazionale, viene registrata nell’audit e si può ripetere
senza duplicazioni. Un’immagine eliminata manualmente dopo l’applicazione non
viene ripristinata da un nuovo avvio dello stesso pacchetto.

## Fonti effettive e identificazione

- **MSX Resource Center**: gallerie dei singoli Daewoo, file originali e cronologia
  dei caricamenti. Sono coperti Kobo, DPC-100/180, CPC-300, CPC-400/400S e cinque
  Zemmix. Chi carica un file non viene automaticamente indicato come fotografo.
- **retrocmp**: sezioni delle revisioni Kaypro, fotografie di esemplari, adesivi
  e brochure. Distinte le versioni 2/84, 4/83, 4/84, 4x, New 2 e Plus88.
  Il Kaypro 4/83 Plus88 usa una foto dell’aspetto esterno della macchina base:
  la didascalia non certifica la presenza della scheda interna.
- **PC-9800.net / With98**: cataloghi originali PC-98 e H98, compresa la pagina
  specifica del **PC-H98S model 8/U8**. Il catalogo Nr/Nw/Ni mostra la famiglia,
  senza identificare individualmente i due portatili in copertina: limite
  conservato nella didascalia del Nw150.
- **1000bit**: foto del NEC Trek, brochure del PC-8500 e del Kaypro PC. Le ultime
  due sono copertine a bassa risoluzione, segnalate come tali nel pacchetto.
- **SGIstuff e copie Internet Archive**: IRIS 3130 identificato nella galleria;
  Indigo R4400 collegato alla documentazione dello stesso esemplare aggiornato,
  che conserva il marchio esterno R4000. Gli URL dei due file sono copie HTTPS
  archiviate, perché il sito originario non forniva le immagini tramite HTTPS.
- **Wikimedia Commons**: Professional IRIS (2), Seiya Ishibashi, CC BY 2.0.
  Per 4D/50 e 4D/70 viene dichiarato l’involucro TwinTower condiviso; la CPU
  dell’esemplare fotografato non è identificata. La foto del 4D/80 non viene
  spacciata per un esemplare dei due modelli richiesti.

Le condizioni di MSX, retrocmp e With98 sono state consultate; per 1000bit
esiste l’autorizzazione al recupero dei dati fornita dall’utente. Le immagini
senza licenza libera documentata conservano l’indicazione dei diritti riservati.
I collegamenti sono destinati alla consultazione personale locale richiesta:
**non attribuiscono una licenza libera o un permesso di ripubblicazione**.
Nessuna credenziale, API a pagamento o scraping massivo.

## Presentazione delle scansioni

Per **24 immagini** la fotografia del computer occupa solo una parte della
pagina. Il frontend mostra quella regione tramite una finestra SVG, senza
modificare il file originale. Le coordinate sono documentate nel pacchetto;
il collegamento **Apri fotografia** continua ad aprire l’originale completo.
Le copertine rimangono uniformi, le didascalie e i crediti sono visibili nella
scheda, le immagini fuori schermo sono caricate solo quando necessario.
Le fotografie normali e le gallerie esistenti mantengono la visualizzazione
precedente.

## Verifica e lacune

L’inventario comprende **tutti i 104 sistemi** dei quattro gruppi di produttori,
non soltanto la selezione della precedente revisione. Nel clone del catalogo
61 erano senza immagine: il pacchetto ne completa 45, lasciandone **16**.

Restano **14 NEC** (soprattutto varianti PC-88, Bungo mini 5SX, EWS4800/310,
PC-8401BD, PC-6601/SR e PC-8001mkIISR), **Daewoo DPC-200E** e
**Kaypro Omni II Logic Analyzer**. Per otto NEC sono disponibili schemi ufficiali
delle connessioni posteriori, esclusi dalla selezione delle fotografie.
Non vengono usati loghi, schermate o foto di altri modelli per riempire i vuoti.

[Inventario, crediti e controlli dei file](images.json).
[Verifica sul database PostgreSQL e modelli ancora scoperti](verification.json).

Test automatici: importazione, conservazione di foto e dati, alias, ambiguità,
fonti, rollback, ripetizione e geometria della finestra. Vengono verificati
anche build React, costruzione Docker e visualizzazione delle immagini.
Esito: **28 test SQLite, 28 PostgreSQL e 47 frontend** superati; database, API
e web sani. Chromium ha controllato cinque schede nei temi chiaro/scuro, a
1440 e 390 px, con gli stessi byte originali già scaricati e verificati via HTTP.
Questa prova isola il rendering dalla rete del browser cloud e non certifica
il recupero diretto dai siti esterni nel browser. Le 45 risorse erano
raggiungibili e decodificabili durante il controllo separato.
Gli URL esterni possono cambiare; le disponibilità documentate si riferiscono
al giorno della ricerca.
