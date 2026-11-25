# NewBrain, Micro-Professor I e Robotron — 24 novembre 2026

[Pacchetto offline](../../../backend/app/importing/data/microcomputers-2026-11-v1.json)
con cinque schede, cinque configurazioni, **87 specifiche con fonte individuale**,
cinque descrizioni italiane originali, dieci note, sei commercializzazioni
(quattro prezzi) e cinque fotografie Commons. Riusa entità e percorsi esistenti:
nessuna nuova tabella, funzione amministrativa o richiesta di rete all’avvio.

| Produttore | Scheda | Data e dati principali |
| --- | --- | --- |
| Grundy Business Systems | NewBrain | 1982; Z80A, 4 MHz, 32 KB RAM; A e AD nella stessa scheda, display VFD da 16 caratteri solo su AD. |
| Multitech | Micro-Professor I | 1981; MPF-I/MPF-1, Z80 a 1,79 MHz, 2 KB RAM, monitor ROM da 2 KB e sei cifre LED; scopo didattico. |
| Robotron | KC 85/1 | Famiglia Z9001 commercializzata alla fine del 1984, rinominata KC85/1 nel 1985; U880 a 2,5 MHz, 16 KB RAM, 4 KB ROM. |
| Robotron | KC 87 | 1987; evoluzione del KC85/1 con BASIC integrato, U880 a 2,5 MHz, 16 KB RAM e 14 KB ROM. |
| Robotron | A 5105 | Consegne scolastiche dal settembre 1989; UA880 a 3,75 MHz, 64 KB RAM, 40 KB ROM, grafica e rete BICLAN opzionale. |

Sono aggiunti i profili di **Robotron** e **Grundy Business Systems** quando
assenti, con descrizione, paese e sede. Robotron ha anche denominazione
VEB Kombinat Robotron, fondazione 1 aprile 1969, scioglimento 1 luglio 1990,
logo storico, attribuzione e fonti. Non vengono inventati fondatori o date per
Grundy. Il profilo Multitech già presente resta intatto; se assente, è creato il
produttore necessario alla scheda senza copiare il profilo della successiva Acer.

## Scelte di identità e dati controversi

- **Z9001 e KC85/1 sono una sola scheda**, con rinomina spiegata nella descrizione.
  Anche le varianti di colore restano nella famiglia, senza schede duplicate.
- **KC85/2, /3 e /4 non sono Robotron**: appartengono alla diversa linea del
  VEB Mikroelektronik Mühlhausen. Non sono aggiunti sotto il produttore sbagliato.
- Micro-Professor I non è confuso con i compatibili Apple Microprofessor II/III
  già censiti, con il successivo MPF-1P/Plus o con il modello a 8088 MPF-1/88.
  Il firmware del MPF-1B è documentato come opzione della famiglia, non come
  capacità ROM installata sul modello originale.
- **NewBrain: 28 KB ROM secondo il manuale**, appendice 9; 1 KB di ROM nel
  COP420M separato. Il valore 24 KB di alcune fonti secondarie non sostituisce
  quello del manuale. Il display AD è **fluorescente VFD, non LCD**; la stessa
  appendice indica larghezze grafiche 256/320/512/640 e fino a 250 righe, senza
  imporre una singola risoluzione ai diversi modi.
- Una RAM principale per sistema: 32, 2, 16, 16 e 64 KB rispettivamente.
  Espansioni, memoria ROM, RAM-floppy e memoria video non sono sommate alla
  dotazione base. La normale espansione KC aggiunge due moduli da 16 KB;
  il limite d’indirizzamento di 64 KB non diventa RAM installata.
- A5105: prototipi nel 1988, serie da luglio 1989 e consegne da settembre.
  È registrata la data delle consegne, senza inventare il giorno del mese.

Alias espliciti in `identity.py` consentono successive importazioni nelle
grafie Grundy/NewBrain AD, Multitech/MPF-I, Z9001/KC85/1, KC87 e A5105.
Non si applicano abbreviazioni generiche o accorpamenti di altre famiglie.
La ricerca testuale può trovare anche successori che menzionano un modello
nel loro contesto storico: questo non indica un duplicato del modello cercato.

## Prezzi e date

- **Micro-Professor I: 149 USD**, pubblicità Multitech su BYTE, agosto 1982,
  pagina 127. Il modello risale al 1981; il prezzo pubblicitario è del 1982,
  con imposte e spedizione separate. Le due fonti e i due riferimenti temporali
  restano distinti: non viene certificato come prezzo di lancio.
- **Z9001.10 monocromatico: 1.550 DDM**, riportato nella ricostruzione tedesca
  con riferimento a Jugend + Technik dell’agosto 1984. È una fonte secondaria
  con riferimento al documento: non si dichiara di aver letto quel fascicolo.
- **KC87: 3.005 DDM monocromatico, 3.390 DDM a colori**, da Robotrontechnik.
  Il listino non è datato: 1987 è la data del modello, non la data accertata del
  prezzo. I due allestimenti conservano etichette e offerte native distinte.
- Prezzi NewBrain e A5105 assenti: non sono inseriti valori enciclopedici
  privi di un contesto sufficiente o ricavati per conversione.

**DDM è il marco della Germania Est**, non DEM e non EUR. I mercati europei
sono raggruppati in Europa, mantenendo nelle note Regno Unito/Germania Est.
Le date di lancio hanno una propria citazione anche quando quella del prezzo
è diversa. I metadati `date_scope`, `date_sources`, `price_reference_date` e
le note commerciali impediscono di confondere anno del modello e listino.

## Fonti consultate

- [NewBrain Handbook originale, Grundy Business Systems](https://archive.org/details/grundy-newbrain-handbook-manual):
  metadati ed esportazione OCR, appendice 9 e capitoli su BASIC, grafica e I/O.
- [Testimonianza di Gerald McMullon conservata da Binary Dinosaurs](https://www.binarydinosaurs.co.uk/Museum/Grundy/gerald.php)
  e [pagina storica Grundy](https://www.binarydinosaurs.co.uk/Museum/Grundy/):
  sviluppo, espansioni, passaggio a Tradecom e contesto dell’azienda.
- [BYTE agosto 1982](https://archive.org/details/byte-magazine-1982-08):
  OCR della pubblicità originale Multitech a pagina 127, prezzo e memorie base.
- [Electrickery — Multitech MPF-1](https://electrickery.nl/comp/mpf1/):
  varianti e architettura del sistema. Solo pagina HTML; nessun PDF o ROM copiato.
- Robotrontechnik:
  [KC di Dresda](https://www.robotrontechnik.de/html/computer/kc_dresden.htm),
  [A5105](https://www.robotrontechnik.de/html/computer/a5105.htm),
  [Kombinat Robotron](https://www.robotrontechnik.de/html/standorte/robotron.htm).
- API Wikipedia, revisioni fissate negli URL del pacchetto: NewBrain, MPF-I,
  storia dettagliata Z9001/KC85/1/KC87 e Kombinat Robotron. Le affermazioni
  enciclopediche e i loro riferimenti restano distinguibili dai documenti letti.
- API Commons `imageinfo`/`extmetadata` e revisioni delle pagine dei file:
  [NewBrain AD](https://commons.wikimedia.org/wiki/File:New_Brain_IMG_4244.jpg),
  [Micro-Professor I](https://commons.wikimedia.org/wiki/File:Mpf-I.jpg),
  [Z9001](https://commons.wikimedia.org/wiki/File:Robotron_z_9001_technische_Sammlung_Dresden.jpg),
  [KC87](https://commons.wikimedia.org/wiki/File:Robotron_KC_87.jpg),
  [A5105](https://commons.wikimedia.org/wiki/File:Robotron_a5105.jpg),
  [logo Robotron](https://commons.wikimedia.org/wiki/File:VEB_Robotron.svg).

Letture selettive e API ufficiali, senza scraping massivo. Robotrontechnik:
non recuperate immagini o directory download escluse da robots. Electrickery:
non recuperati i PDF esclusi. The Register e Flite non sono fonti del dataset,
per le condizioni robots dei siti. Alcuni URL inizialmente cercati restituivano
404: non sono diventati fonti. Nessuna API AI a pagamento.

Le fotografie sono collegate a Commons e conservano autore e licenza del
singolo file: Rama & Musée Bolo (CC BY-SA 2.0 fr), Toytoy (CC BY-SA 2.0),
ubahnverleih (CC0), Max Mustermann (CC BY-SA 2.0), Florian Schäffer
(CC BY-SA 4.0). Logo ricostruito da O. Wolters, dichiarazione PD-textlogo e
marchio commerciale. Nessun PDF, ROM o file immagine redistribuito nel repository.

## Applicazione locale

Dalla cartella del progetto:

```bash
git switch feat/historical-data-import
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
```

Anteprima senza scritture:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.microcomputer_research
```

Importazione esplicita:

```bash
docker compose -p hhe-import-test exec api python -m app.importing.microcomputer_research --apply
```

Ricaricare il sito. I dati sono nativi: catalogo, timeline, profili produttore,
confronti, analisi e contesto dell’assistente li usano senza percorsi speciali.
Il file operativo non va caricato come generico JSON dal pannello: il comando
installa anche profili aziendali, fotografie e offerte con ambito distinto.

Il pacchetto riusa i produttori e modelli già presenti quando l’identità è
univoca. Conserva testi curati, categorie, caratteristiche manuali, offerte,
date e copertine esistenti. Valori tecnici discordanti restano claim conflittuali.
Produttori ambigui bloccano l’intera transazione; computer duplicati o con più
configurazioni non riconosciute sono segnalati e saltati. Nessuna fusione cieca.

Originali ETL, citazioni individuali e audit `micro_research` conservano la
provenienza; le nuove associazioni sono `pending`, senza verifica umana automatica.
Un errore annulla l’intera transazione. Il checksum impedisce reimportazioni e
la ricreazione di sistemi cancellati dall’utente. Il database del Mac non viene
raggiunto dalla verifica cloud: richiede l’applicazione esplicita locale.

## Verifiche eseguite

[verification.json](verification.json) riporta la prova su un’ulteriore copia
PostgreSQL dell’archivio: **1.147 → 1.152 computer, 185 → 187 produttori**,
cinque configurazioni e foto aggiunte, 87 specifiche, dieci note e sei offerte.
Tutte le righe e le associazioni precedenti rimangono intatte, inclusi prezzi,
foto, fonti, importazioni originali e claim. Ripetere il pacchetto non cambia i
dati né crea nuovi lavori ETL.

- Backend: **880 passati, due saltati perché esclusivi PostgreSQL**, con sette
  subtest passati. Ripetuti gli otto test del supplemento sul codice finale.
- PostgreSQL: **37 controlli passati** tra supplemento, normalizzazione,
  profili produttore e migrazioni; passato anche il controllo esclusivo di
  concorrenza sul ricalcolo del catalogo. Verificati conservazione dei dati
  manuali, reimportazione con alias, ambiguità, rollback e cancellazioni.
- Frontend: **45 test passati**, build React riuscita. Rimane l’avviso già
  presente di Vite sulle dimensioni del bundle.
- Docker Compose: ricompilazione API e health riuscite sul clone. API del
  catalogo, date della timeline, profilo Robotron, confronto, analisi e offerte
  controllate dopo l’avvio; recupero del contesto dell’assistente con fonti,
  senza chiamate AI a pagamento.
- Chromium sulla build di produzione: logo e profilo Robotron, tre modelli
  collegati, cinque schede tecniche singole, RAM/frequenze, fotografie, prezzi
  DDM separati e visualizzazione mobile a 390 px; nessun errore JavaScript o
  overflow. Per le immagini gli URL esatti sono stati serviti con i medesimi
  file scaricati via HTTPS da Commons; il caricamento remoto diretto dal browser
  cloud non è certificato. I cinque file fotografici sono stati ispezionati.

La prova non modifica il database locale dell’utente e non effettua merge.
