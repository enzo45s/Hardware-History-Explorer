# Ricerca e raccolta dei profili dei produttori

Ricerca del **23 novembre 2026** sui 184 nomi presenti nella copia di catalogo
fornita dall'utente. I profili riguardano aziende, marchi, collaborazioni,
pubblicazioni e alcuni progettisti: non tutti rappresentano una società.

La raccolta versionata è
[`manufacturers-v1.json`](../backend/app/importing/data/manufacturers-v1.json).
Contiene dati effettivamente ricercati, descrizioni italiane, citazioni per
campo, identificativi e revisioni delle entità consultate e lacune. È un
pacchetto editoriale offline, non un generatore di biografie o uno scraper
eseguito all'avvio. L'applicatore e le sue protezioni sono descritti in
[MANUFACTURERS.md](MANUFACTURERS.md).

## Copertura effettiva

| Informazione | Nomi con dato documentato | Totale esaminato |
| --- | ---: | ---: |
| Descrizione italiana | 148 | 184 |
| Logo e fonte/condizioni | 84 | 184 |
| Paese | 117 | 184 |
| Fondazione | 86 | 184 |
| Cessazione | 31 | 184 |
| Sede | 85 | 184 |
| Fondatori | 39 | 184 |
| Sito web | 50 | 184 |

Questi numeri non significano che i profili siano completi in ogni campo o
che tutti i dati siano stati verificati da una persona incaricata della
revisione del catalogo. Le associazioni appena importate restano `pending`.
L'assenza di una data di cessazione non dimostra che l'azienda sia attiva.
I siti web possono riferirsi a società successive o archivi storici, come
indicato dal contesto della descrizione e dalle fonti.

## Fonti realmente usate

- **Wikipedia**: API ufficiali, estratti italiani e consultazione di testi
  inglesi, spagnoli e altre lingue per le realtà locali. Sintesi scritte in
  italiano; fonte alla revisione consultata, attribuzione ai collaboratori e
  collegamento alla licenza CC BY-SA 4.0 per i testi derivati da Wikipedia.
- **Wikidata**: API ed esportazioni delle entità per dati societari e
  identificativi, citati alla revisione consultata. Dati CC0. Valori ambigui,
  date di rinomina e casi di società madri/figlie sono esclusi o corretti
  mediante la fonte testuale. Un valore del primo gennaio viene conservato
  prudentemente al solo anno se può essere una data convenzionale.
- **Wikimedia Commons**: `imageinfo` e `extmetadata` per URL, autore e
  condizioni dei loghi effettivamente associati all'identità. Le licenze sono
  quelle della singola immagine: non si assegna una licenza libera a tutti i
  marchi. Non vengono trasferiti i diritti sui marchi commerciali.
- **1000bit**: indice e schede produttori pertinenti, nel perimetro del
  permesso al recupero già fornito dall'utente; robots consultato. Dati
  fattuali e loghi collegati per URL. Il sito riserva i diritti ai rispettivi
  titolari: **nessuna licenza libera presunta** e nessun download dei loghi
  ridistribuito nel repository.
- **MSX Resource Center**: categorie pubbliche pertinenti, per realtà come
  Fenner, CIEL, Bawareth, Talent, Sharp/Epcom e Yeno. API non disponibile;
  rispettate le esclusioni robots delle pagine Special e degli URL index.php.
  Sintesi fattuali originali, senza copiare gli articoli riservati.
- **Documentazione ufficiale dei progetti GitHub**: Micro 8088 di Sergey
  Kiselev e NuXT di Monotech, con citazione alla documentazione consultata.
- **Manuali conservati su Internet Archive/Bitsavers**: DreamWriter di NTS,
  SB180 di Micromint e documentazione Orel BK-08. Non si deducono le date di
  fondazione dall'anno di un manuale o dal lancio di un computer.

Non sono usate API a pagamento. Il tentativo Wikidata con `maxlag=5` è stato
rifiutato per ritardo del servizio; le successive letture con tolleranza
`maxlag=30` hanno fornito i dati effettivi. Risultati di ricerca estranei e
pagine irraggiungibili non sono diventati fonti della raccolta.

## Controlli di identità

- La Unitron tedesca dell'indice 1000bit è stata esclusa per la brasiliana
  Unitron Eletrônica.
- Daewoo non riceve il logo Winia; Hyundai Electronics non riceve il logo
  SK Hynix; Multitech non riceve automaticamente il logo Acer.
- Codimex e Polymax non vengono abbinate a società francesi omonime.
- Tesa Etikett non eredita la fondazione nel 2001 di Tesa SE. National,
  collaborazioni e persone non ereditano date da società madri o prodotti.
- Sergey Kiselev è documentato dal proprio progetto hardware: sono stati
  scartati gli omonimi trovati nelle ricerche enciclopediche.

## Lacune da approfondire

Restano **36 nomi senza una descrizione sufficientemente documentata** e
**100 senza un logo associabile con condizioni identificabili**. Nessun logo
è stato inventato; per persone e progetti può essere più corretto conservare
il segnaposto. La presenza di un nome nel catalogo non basta a scriverne una
storia aziendale. Il resoconto scaricabile dall'amministrazione riporta tutte
le lacune anche per gli altri campi e i nomi eventualmente assenti dal
pacchetto.

- AUVA
- Alex Zhabin
- Arbiter Leisure
- China HKC
- ComputerTechnik/IBS
- Comus Instruments
- Craft
- Dragon Data / Compusense
- G2 Systems
- GTAC
- H/H Microcomputers
- ILCE / SEP
- ITCI
- ITT Information Systems
- JUKO
- Komtek
- Kondor and Kramis
- Lawrie T&M Ltd.
- MY-COM
- Milmar
- NEMO
- Nanjing Computer Factory
- Omni Logic
- Patisonic
- Professional Data Computer
- Ritas do Brasil Ltda
- Scientific Micro Systems
- Shaanxi Province Computer Factory
- Signal
- Tantel
- Terco AB
- Tesa Etikett
- Tinsley Medical Instruments
- Vendex
- Victor do Brasil
- Vladimir Drozdov
