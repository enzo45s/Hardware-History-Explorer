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

Poi ricaricare il sito. Lo stesso pacchetto restituisce `already_applied` dalla
seconda esecuzione, senza duplicare o ricreare sistemi eliminati successivamente.
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
  documenti di assistenza. L’anno rimane assente dove non accertato dalla ricerca.
- La RAM del 30-286 è la configurazione standard E01/E21 del catalogo 1989;
  non costituisce verifica di ogni allestimento H31. Non si importano come memoria
  fisica i vecchi 1664 KB comuni a molte schede, né i limiti generici fino a 256 MB.
- Il 2168 contiene l’allestimento BB1 documentato, non un’ipotetica dotazione
  comune a tutte le torri 2168. Le capacità native e i limiti restano distinti.
- Non vengono aggiunti prezzi o fotografie in questa revisione. Le offerte
  precedenti conservano valuta, importo e date; non si inventa una data di vendita.

## Verifica

[verification.json](verification.json) riporta i conteggi della copia PostgreSQL
isolata e i controlli di conservazione. I test automatici del pacchetto sono in
`backend/tests/test_ibm_ps_research.py`: fonte per specifica, nomi, primo import,
ripetizione, accorpamenti, foto/prezzi, valori verificati, rollback completo e
reimportazione dei vecchi codici nella configurazione corretta.
