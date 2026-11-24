# Produttori: ricerca supplementare del 24 novembre 2026

Il [pacchetto offline](../../../backend/app/importing/data/manufacturers-deep-2026-11-v1.json)
arricchisce **30 produttori esistenti**, aggiungendo **14 descrizioni italiane**
e **18 loghi**. Compila soltanto campi mancanti; conserva testi, marchi, crediti
e fonti già curati. Non crea, rinomina o accorpa aziende e non modifica le
schede dei computer. Nessuna API a pagamento, nuova dipendenza o migrazione.

## Risultati effettivi sulla copia PostgreSQL

| Copertura | Prima | Dopo |
| --- | ---: | ---: |
| Produttori | 187 | 187 |
| Descrizioni | 151 | 165 |
| Loghi | 88 | 106 |
| Computer | 1.152 | 1.152 |

Sono aggiunte **33 fonti e 34 associazioni** ai produttori, tutte `pending`.
Un URL non certifica una verifica umana. Sono compilati anche l’anno di
fondazione **1963** e il sito ufficiale di **Terco**, se mancanti. I conteggi
del database locale possono differire in presenza di modifiche manuali.

**Descrizioni aggiunte:** Alex Zhabin, Dragon Data / Compusense, H/H
Microcomputers, ITT Information Systems, Kondor and Kramis, NEMO, Patisonic,
Ritas do Brasil Ltda, Scientific Micro Systems, Shaanxi Province Computer
Factory, Signal, Terco AB, Vendex e Vladimir Drozdov.

Si distinguono progettisti, attività aziendali, marchi e collaborazioni.
Drozdov è associato al Pentagon **48K** del 1989, senza attribuirgli tutte le
revisioni 128K. Dragon / Compusense descrive la piattaforma e le espansioni
del fornitore, senza inventare una società congiunta. La fabbrica Shaanxi non
viene confusa con quella di Nanjing.

**Loghi aggiunti:** Autocue Ltd., Basis, Didaktik Skalica, EACA Computers,
Elwro, Ericsson Information System, ICE-Felix, ITT Information Systems,
LNW Research, Lobo Systems, Matra & Hachette, Morrow Designs, Multitech,
Nascom Microcomputers, Sakhr, la voce congiunta «SpecNext Ltd., Victor Trucco,
Fabio Belavenuto», Terco AB e Thomson SIMIV.

La voce congiunta SpecNext usa il marchio della società **SpecNext Ltd.**,
non loghi personali degli sviluppatori. Thomson SIMIV usa il marchio del
gruppo Thomson, non quello di un’entità giuridica separata. Per Autocue viene
usato il simbolo ufficiale del marchio. I loghi attuali di Autocue, Terco e
SpecNext non vengono datati come originali degli anni Ottanta. Multitech
riceve il proprio marchio storico, non Acer o l’omonima Multi-Tech Systems.

## Fonti realmente utilizzate

- **1000bit:** 28 pagine di produttori selezionate, confronto dei modelli,
  scheda ITT XTRA e 14 loghi. Robots senza percorsi vietati; recupero nel
  perimetro dell’autorizzazione già fornita dall’utente. Il footer riserva
  il materiale a studio privato, ricerca e attività accademica; marchi dei
  rispettivi titolari. Nessuna licenza libera dedotta dal download.
- **MSX Resource Center:** categorie Bawareth, CIEL, Fenner, Talent,
  Sakhr/Al Alamiah e Sharp/Epcom, più pagina e cronologia del file Sakhr.
  Usato soltanto il logo Sakhr; il marchio MSX del sito non viene attribuito
  alle singole aziende. Nessun endpoint vietato da robots interrogato.
- **Terco, Autocue e SpecNext:** siti ufficiali e rispettivi loghi. Per
  Terco, pagina di storia e formazione tecnica; ritardo robots rispettato.
  Nessuna specifica della vecchia stazione 4426 dedotta dai prodotti attuali.
  Il logo Videndum non viene trasferito ad Autocue.
- **China Computer Federation:** storia del CEC-I e ruolo della fabbrica
  Shaanxi nel progetto congiunto coordinato da Tsinghua. Non sono importate
  cifre di vendita o date aziendali non documentate.
- **VAXBARN e Bitsavers:** architettura PDP-11/QBUS dell’SMS 1000 e indice
  delle brochure. Il PDF SMS ha restituito 403: non viene dichiarato letto
  e non supporta nuove specifiche o date nel pacchetto.
- **MCbx:** ruolo commerciale Vendex, fabbricazione Samsung degli HeadStart,
  stabilimento Signal di Chișinău e versioni Sintez. Sintesi italiane dei
  fatti, senza riprodurre fotografie o lunghi testi.
- **The Dragon Archive:** Dragon Plus, revisione **9785**, relazione con
  Compusense e software OS-9/Flex. Sintesi dei fatti con fonte; nessun
  manuale, ROM o immagine riprodotto.
- **Wikipedia:** API ufficiali e revisioni fissate nel pacchetto, in inglese,
  russo e portoghese. Le sintesi derivate conservano attribuzione e
  collegamento **CC BY-SA 4.0**. I titoli inesistenti non diventano fonti.

Consultati anche Apple II History e i metadati Internet Archive per
disambiguazione, senza risultati sufficienti per tutti i nomi. Old-Computers
e Primrosebank hanno restituito 503 al controllo iniziale: nessun aggiramento
o scraping massivo. Robots verificati prima delle consultazioni pertinenti.

Tutti i 18 loghi selezionati sono stati scaricati via HTTPS e ispezionati:
[formato, dimensioni e impronta SHA-256](image-verification.json).
Nel repository sono conservati **URL e metadati, non file grafici**. I marchi
rimangono dei rispettivi titolari; non sono dichiarati liberi e non vengono
inventati autori grafici. Il browser carica il logo dal sito originale, dalla
cui disponibilità dipende la visualizzazione.

## Lacune e abbinamenti esclusi

Rimangono **22 descrizioni e 81 loghi mancanti**. L’
[inventario](research-inventory.json) elenca tutti i 99 profili inizialmente
incompleti, i modelli associati, le aggiunte e i campi residui. La ricerca non
è un censimento esaustivo di ogni sito esistente.

Descrizioni ancora mancanti: AUVA, Arbiter Leisure, China HKC,
ComputerTechnik/IBS, Comus Instruments, Craft, G2 Systems, GTAC, ILCE / SEP,
ITCI, JUKO, Komtek, Lawrie T&M Ltd., MY-COM, Milmar, Nanjing Computer Factory,
Omni Logic, Professional Data Computer, Tantel, Tesa Etikett, Tinsley Medical
Instruments e Victor do Brasil.

Esclusi: logo **Oric** per Tangerine, **Timex Sinclair** per Timex Portogallo,
**Kaypro** per la distinta denominazione Non-Linear Systems e **Osborne**
trasferito senza riscontri a Osborne/Nuevo. Nessun logo combinato
Dragon/Tano o Dragon/Compusense inventato. L’avatar GitHub di Monotech è
un’illustrazione personale, non una prova sufficiente di un marchio aziendale.
Non vengono usati JVC per Victor do Brasil, Unitron tedesca per quella
brasiliana, tesa SE moderna per Tesa Etikett o Hyundai Motor/SK Hynix per
i PC storici. Le persone non ricevono marchi di società omonime.

## Applicazione sul Mac

Dalla cartella del repository, sul branch `feat/historical-data-import`:

```bash
git pull --ff-only
docker compose -p hhe-import-test up -d --build --wait --wait-timeout 900
docker compose -p hhe-import-test exec api python -m app.manufacturer_enrichment --package app/importing/data/manufacturers-deep-2026-11-v1.json
```

L’ultimo comando **applica** il supplemento: non è un’anteprima e non richiede
`--apply`. Il solo aggiornamento del codice non importa il pacchetto aggiuntivo.
Non occorre ripopolare o ripristinare il database. Si può usare il sistema di
backup locale già disponibile prima dell’applicazione.

Il comando stampa `updated`, `fields_updated` e `coverage`. Sulla copia usata,
`updated` vale **30**, con **165 descrizioni** e **106 loghi**. Ripeterlo
aggiorna zero campi e non duplica le fonti; resta una nuova voce di audit
dell’esecuzione esplicita. Le operazioni sono transazionali. Un testo o logo
inserito a mano mantiene la precedenza. Ricaricare **Produttori** dopo l’import.

## Verifiche

[Resoconto PostgreSQL](verification.json): conservati tutti i dati dei 1.152
computer, configurazioni, specifiche, commercializzazioni, prezzi, fotografie
e importazioni precedenti. Anche vecchie fonti e associazioni restano intatte;
nessun campo non vuoto dei produttori viene sostituito.

**26 test** sui produttori passano su SQLite e PostgreSQL: omonimi, diritti
dei loghi, dati curati, fonti collegate soltanto ai campi effettivamente
aggiunti, precisione delle date e ripetizione. Passano anche **45 test
frontend**, compilazione React e build dell’immagine Docker API. Il CLI
nell’immagine Docker conferma la ripetizione senza modifiche.

Prova browser su otto profili con API del database di prova, desktop e viewport
390 px: testo, fonti, loghi, crediti e assenza di marchi inventati per persone.
Gli URL esatti delle immagini sono stati serviti con i byte originali scaricati
via HTTPS; non si certifica il recupero diretto dai siti esterni nel Chromium
cloud. Il database del Mac non è stato raggiunto o aggiornato da questo ambiente.
