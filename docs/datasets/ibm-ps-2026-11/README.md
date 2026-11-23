# IBM PS/2, PS/1 e PS/note

Ricerca del 23 novembre 2026 e importazione offline esplicita. Il pacchetto
[ibm-ps-research-v1.json](../../../backend/app/importing/data/ibm-ps-research-v1.json)
contiene 14 schede, 143 asserzioni tecniche con citazioni individuali e 24
rettifiche che richiedono corrispondenza esatta con i precedenti valori importati.
I nuovi dati restano `pending`: una fonte non equivale a una verifica umana.

## Nomi commerciali

Il produttore resta IBM; il nome pubblico evita di ripeterlo.

| Nome precedente | Nome commerciale |
| --- | --- |
| IBM PS/2 8530-H31; IBM PS/2 Model 30-286 | PS/2 Model 30-286 |
| IBM PS/2 8535-043 | PS/2 Model 35 SX |
| IBM PS/2 8550-021 | PS/2 Model 50 |
| IBM PS/2 8550-061 | PS/2 Model 50 Z |
| IBM PS/2 8555-081 | PS/2 Model 55 SX |
| IBM PS/2 8580-071; IBM PS/2 8580-111 | PS/2 Model 80 |

Il Model 50 Z è una revisione distinta con memoria a zero wait state e dischi
ESDI. I due Model 80 restano allestimenti separati nella stessa scheda: 16 MHz
con disco da 70 MB e 20 MHz con disco da 115 MB, documentati dal catalogo IBM
del maggio 1989. Il doppione del 30-286 viene accorpato solo quando le specifiche
coincidono dopo le rettifiche documentate; configurazioni diverse non sono eliminate.

I vecchi codici restano alias ricercabili e conservano configurazioni, offerte,
identità esterne e originali ETL. I codici non documentati non vengono interpretati
tagliando semplicemente il suffisso: `unmapped_machine_codes` nell’anteprima
segnala ulteriori codici presenti nel database locale ma assenti dalla ricerca.
Non si confonde il Model 30 originale 8086 con il Model 30-286.

## Sistemi aggiunti se assenti

- PS/1 Model 2011, il primo della serie (1990): 286 a 10 MHz, DOS in ROM,
  alimentatore nel monitor e opzioni dedicate.
- PS/1 Model 2121: configurazioni C42 a 16 MHz e G42 a 20 MHz, entrambe 386SX.
- PS/1 Model 2133: configurazioni documentate G11 (386SX) e G53 (486SX),
  con distinzione fra i pacchetti software Consultant, Essential ed Expert.
- PS/1 Model 2168: torre, con allestimento BB1 documentato, 486DX2/66,
  disco da 420 MB, CD-ROM 2× e audio Aria 16.
- PS/2 Note N33 SX e N51 SX, precedenti alla diffusione dei ThinkPad.
- PS/note 182 e PS/note 425. **PS/note è il marchio documentato**, anche quando
  il badge richiama PS/1. Il 425 condivide l’hardware con ThinkPad 350: una scheda
  350 già presente viene riutilizzata conservandone il nome. Il 350C resta distinto.

Le altre famiglie PS/2 preesistenti eliminate dall’operatore non vengono ricreate.
Non si censiscono automaticamente tutti gli allestimenti elencati nei manuali.

## Applicazione sul database del proprio PC

Dalla cartella del repository sul Mac o su Windows:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Conservare un normale backup locale prima della revisione. L’anteprima non scrive:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research
```

Applicazione sul database collegato a quel servizio API:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research --apply
```

Poi ricaricare il sito. Il pacchetto tecnico restituisce `already_applied` dalla
seconda esecuzione, senza duplicare o ricreare sistemi eliminati successivamente.
Il comando controlla separatamente il supplemento cronologico descritto sotto:
può completare le date anche quando le specifiche sono già state importate.
L’operazione è transazionale: anche rinomine e accorpamenti vengono annullati se
fallisce l’arricchimento. Non viene eseguita automaticamente all’avvio.

Le prove cloud usano una copia del database: **non modificano il Mac**. Il comando
va eseguito localmente. Non caricare il pacchetto operativo come JSON generico
dal pannello delle descrizioni. Non vengono reintrodotti pannelli di ricerca.

I testi curati, i dati verificati e i valori modificati a mano non sono sostituiti
perché diversi da quelli del pacchetto. La proposta alternativa resta un conflitto
consultabile in Importazioni → Fonti e verifiche. Gli accorpamenti mantengono foto,
prezzi, fonti, fatti e originali; nella scheda risultante una sola foto è principale.
I relativi audit sono `computer`, `physical_cleanup` e `ibm_ps_research`.

## Fonti e limiti

Consultazione selettiva di documentazione IBM e API ufficiale Wikipedia, senza
scraping massivo, chiamate a pagamento o redistribuzione di manuali e fotografie.
Le introduzioni sono scritte in italiano; i crediti delle sintesi da Wikipedia
citano la revisione e la licenza CC BY-SA 4.0. Le specifiche citano la propria fonte.

| Fonte | Impiego |
| --- | --- |
| [IBM PS/2 and Printers Sales Advisor, maggio 1989](https://bitsavers.org/pdf/ibm/pc/ps2/G320-9781-00_PS2_and_Printers_Sales_Advisor_198905.pdf) | Model 30-286, 50/50 Z, 55 SX e allestimenti 80: CPU, memoria, espansione, dischi e floppy |
| [IBM Announcement 191-075, 11 giugno 1991](https://www.ardent-tool.com/35_40/191-075.txt) | Identificazione 8535-043, 386SX/20, 2 MB standard, espansione a 16 MB e disco da 40 MB |
| [IBM Mobile Systems HMM, Volume 1, 1995](https://download.lenovo.com/ibmdl/pub/pc/pccbbs/bp_thinkpad/tpvol1.pdf) | N51 SX (tabella iniziale) e PS/note 425/ThinkPad 350 (pp. 205–228, riepilogo a p. 220) |
| [IBM Service Hints & Tips — 2011](https://ps-2.kev009.com/pcpartnerinfo/ctstips/ca16.htm) | Documento MWER-3S2TF8: dotazioni, DOS in ROM, alimentazione e periferiche |
| [IBM Service Hints & Tips — 2121](https://ps-2.kev009.com/pcpartnerinfo/ctstips/c586.htm) | Documento MWER-3S2UQG: C42/G42, memoria, dischi e connessioni |
| [IBM Service Hints & Tips — 2133](https://ps-2.kev009.com/pcpartnerinfo/ctstips/a8ce.htm) | Documento MWER-3S7Q9R: pacchetti, schede madri e dotazioni G11/G53 |
| [IBM Service Hints & Tips — 2168](https://ps-2.kev009.com/pcpartnerinfo/ctstips/bcaa.htm) | Documento MWER-3THU84: configurazione BB1 e componenti multimediali |
| Wikipedia: PS/1, PS/2, PS/2 Note and PS/note | Contesto storico, N33 SX e 182; URL con revisione esatta nel pacchetto |

I documenti Hints & Tips sono conservati in un archivio esterno: l’autore originale
è IBM, non il mirror. La collezione PS/2 Reference 1992–95 non copre i vecchi modelli
richiesti. Alcune directory Ardent Tool e la richiesta `action=parse` a Wikipedia
hanno restituito 403; il tentativo PS/1 Reference Book ha restituito 404. Non sono
stati aggirati né impiegati come prove. Sono stati usati i documenti accessibili
individuati negli indici e nelle citazioni, con i rispettivi URL.

Limitazioni conservate esplicitamente:

- RAM e clock del PS/note 182 non sufficientemente documentati: lasciati mancanti.
- Le date 2121, 2133 e 2168 non sono dedotte dagli aggiornamenti 1998/1999 dei
  documenti di assistenza. Il supplemento cronologico usa fonti ulteriori,
  conservando le discrepanze descritte sotto.
- La RAM del 30-286 è la configurazione standard E01/E21 del catalogo 1989;
  non costituisce verifica di ogni allestimento H31. Non si importano come memoria
  fisica i vecchi 1664 KB comuni a molte schede, né i limiti generici fino a 256 MB.
- Il 2168 contiene l’allestimento BB1 documentato, non un’ipotetica dotazione
  comune a tutte le torri 2168. Le capacità native e i limiti restano distinti.
- Non vengono aggiunti prezzi o fotografie in questa revisione. Le offerte
  precedenti conservano valuta e importo; non si inventa una data di vendita.

## Supplemento cronologico del 24 novembre 2026

Il pacchetto originale resta immutato, così il suo checksum continua a impedire
la ripetizione di rinomine, rettifiche e accorpamenti già applicati.
[ibm-ps-dates-v1.json](../../../backend/app/importing/data/ibm-ps-dates-v1.json)
aggiunge la cronologia con citazioni ed evidenze indipendenti. Non richiede rete.

Se le schede IBM sono già presenti, dopo aver aggiornato codice e container:

```bash
# Anteprima di sola lettura
docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research --dates-only
# Applicazione al database locale
docker compose -p hhe-import-test exec api python -m app.importing.ibm_ps_research --dates-only --apply
```

Questa modalità non crea calcolatori e non ripete l’arricchimento tecnico. Anche
`--apply` senza `--dates-only` esegue il supplemento, compresi gli archivi che hanno
già applicato il pacchetto originale. Un secondo avvio senza nuove lacune non
crea lavori ETL, offerte o fonti ulteriori. Non ripristina schede cancellate.

| Modello | Introduzione documentata |
| --- | --- |
| PS/2 Model 30-286 | 13 settembre 1988 |
| PS/2 Model 35 SX | 1991; annuncio e disponibilità prevista: 11 giugno |
| PS/2 Model 50 | 2 aprile 1987 |
| PS/2 Model 50 Z | giugno 1988 |
| PS/2 Model 55 SX | maggio 1989; annuncio: 9 maggio |
| PS/2 Model 80 | luglio 1987 per 8580-071; novembre 1987 per 8580-111; annuncio: 2 aprile |
| PS/1 Model 2011 | 1990 |
| PS/1 Model 2121 | 1991, con discrepanza fra fonti |
| PS/1 Model 2133, 2168 | 1992, anno della famiglia |
| PS/2 Note N33 SX | 1991 |
| PS/2 Note N51 SX | 1992; annuncio della serie: marzo |
| PS/note 182 | 1992 |
| PS/note 425 | 1993 |

Fonti: IBM Announcement 191-075, voci Wikipedia specifiche Model 30, 50, 55 SX,
80, PS/1 e PS/2 Note (revisioni esatte ed estratti nel JSON), e
[PC Collection, gamma PS/1](https://www.pc-collection.com/gamme-ps1.php).
Il 2121-282 è documentato da PC Collection nel maggio 1991, mentre l’infobox
Wikipedia indica 1992: si conserva l’anno precedente con nota esplicita, senza
attribuire maggio a ogni allestimento. Per il 2168, Wikipedia indica 1992 e la
collezione francese presenta allestimenti a inizio 1993: l’anno della famiglia
non certifica la prima vendita del singolo BB1. Queste informazioni restano
`pending`, consultabili con le rispettive evidenze; non sono verifiche umane.

Le date sono salvate nelle tabelle native `Computer`/`Release`, con precisione
esplicita, e alimentano catalogo, timeline, confronti e assistente. Non si
trasforma automaticamente un annuncio in un giorno di consegna. Le date del
Model 80 sono abbinate al codice allestimento conservato nell’offerta, mai
dedotte dal prezzo. Senza quel codice viene usato soltanto l’anno della famiglia.

Gli importi, le valute e i mercati esistenti restano intatti. La fonte della data
è registrata separatamente da quella del prezzo: la scheda segnala che la data
del modello non prova la vendita in quel mercato a quel prezzo. Si completa
un’offerta già presente; una riga senza prezzo viene creata solo se il sistema
non ha alcuna commercializzazione. Le date curate/verificate, incompatibili o
più precise si conservano e compaiono nel resoconto `preserved`. In particolare,
il riferimento 1990 dell’allestimento 8530-H31 non è sovrascritto dal lancio
1988 della famiglia. Raw ETL, claim con valore precedente e audit `ibm_ps_dates`
permettono di ricostruire ogni modifica. Qualsiasi errore annulla la transazione.

## Verifica

[verification.json](verification.json) riporta i conteggi della copia PostgreSQL
isolata e i controlli di conservazione. I test automatici del pacchetto sono in
`backend/tests/test_ibm_ps_research.py`: fonte per specifica, nomi, primo import,
ripetizione, accorpamenti, foto/prezzi, valori verificati, rollback completo e
reimportazione dei vecchi codici nella configurazione corretta.

[dates-verification.json](dates-verification.json) documenta il supplemento su
una seconda copia dell’archivio già aggiornato: tutti i 14 modelli hanno una data
nativa, 10 schede aggiornate, 10 date di introduzione e 6 annunci registrati,
3 nuove righe senza prezzo per i PS/1 che non avevano commercializzazione.
`backend/tests/test_ibm_ps_dates.py` verifica inoltre aggiornamento del vecchio
import, idempotenza, cancellazioni, precisione, allestimenti, valori curati,
ambiguità e rollback. Nessun database locale dell’utente viene modificato dal cloud.
