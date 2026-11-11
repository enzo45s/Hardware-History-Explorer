# Valutazione fonti — 11 novembre 2026

Verifica effettuata dall'ambiente cloud. Per tutte le pagine HTML e i
`robots.txt` sotto elencati il proxy ha rifiutato il tunnel HTTPS con **403**.
Questo è un blocco della rete dell'ambiente, non una risposta del sito e non
dimostra indisponibilità pubblica. Nessun aggiramento e nessuno scraping HTML.

| Fonte | Struttura/copertura e metadati verificati | API/esportazioni | Riuso e integrazione |
|---|---|---|---|
| oldcomputers.net | Non ispezionabile da questa rete; copertura e qualità non accertate | Nessuna API/esportazione verificata | Robots e termini non leggibili: solo trascrizione/caricamento autorizzato |
| 1000bit.it | Non ispezionabile; copertura e qualità non accertate | Nessuna API/esportazione verificata | Robots e termini non leggibili: solo caricamento autorizzato |
| retroflops.github.io/data | Repository ufficiale leggibile: catalogo curato di sistemi storici e moderni, componenti, configurazioni, misure, stati editoriali e fonti con localizzatori. L'indice consultato elenca 83 sistemi, inclusi oggetti fuori dallo scopo di questo archivio | Esportazioni ufficiali documentate `catalog-v1.json`, `catalog-summary-v1.json`, `measurements-v1.csv`; sito statico senza API runtime | Catalogo/esportazioni **CC BY 4.0**, codice MIT, documenti citati con diritti separati. Adattatore JSON completo, fetch limitato all'esportazione ufficiale; niente crawler. Fetch live bloccato nel cloud |
| dev.computerhistory.org | Non ispezionabile; copertura e qualità non accertate | Nessuna API/esportazione verificata | Permessi da verificare per singola collezione/documento; solo caricamento autorizzato |
| wikidata.org | Endpoint non raggiungibile da questa rete. Adattatore per JSON `wbgetentities`, etichette, produttore P176, data P577 e statement originali; testato con fixture, non con una risposta live | API MediaWiki ufficiale, richieste esplicite da 1–20 QID e recupero limitato delle etichette dei produttori | Dati strutturati CC0 secondo la policy Wikidata; pagina della policy non riletta da questa rete. Nessuna fotografia o testo esterno importato. Verifica storica sempre pending |

## Evidenze RetroFlops realmente lette

- [README ufficiale](https://github.com/retroflops/retroflops/blob/main/README.md)
- [Licenza contenuti](https://github.com/retroflops/retroflops/blob/main/LICENSE-CONTENT.md)
- [Organizzazione dati](https://github.com/retroflops/retroflops/blob/main/data/README.md)
- [Generazione esportazioni](https://github.com/retroflops/retroflops/blob/main/src/lib/data/build.ts)
- [Schema](https://github.com/retroflops/retroflops/blob/main/src/lib/data/schema.ts)
- [Indice del catalogo](https://github.com/retroflops/retroflops/blob/main/docs/CATALOG.md)

Le copie dei documenti di licenza e dei due record letti si trovano in
`docs/source-audit/`, con attribuzione RetroFlops, CC BY 4.0, fonte GitHub.
Sono snapshot di documenti pubblicati dal titolare sotto licenza aperta,
non copie dei manuali citati. Il campione Apple II è trasformato dal record
canonico ufficiale in un sottoinsieme JSON compatibile con l'adattatore;
non va presentato come l'esportazione integrale scaricata dal sito.

Il programma non traduce gli stati editoriali di un altro archivio in
«verificato» locale. Conserva riferimenti e metadati originali. Esclude dal
catalogo RetroFlops guidance computer, console, smartphone e GPU; include solo
mainframe, minicomputer, home computer, personal computer e workstation.
Non interpreta la data d'inizio Wikidata P571 come data commerciale.

## Limiti e controlli prima di nuove fonti

Per aggiungere un crawler occorre prima leggere robots e termini effettivi,
accertare il permesso di raccolta/riuso, concordare frequenza e attribuzione.
L'autorizzazione su robots non sostituisce una licenza. L'upload richiede una
dichiarazione dell'operatore e una citazione per ogni record; questa dichiarazione
non è una verifica legale o storica automatica. Non si devono caricare interi
manuali o immagini senza un'autorizzazione specifica.

Accessi live necessari sul computer dell'operatore: `www.wikidata.org` e
`retroflops.github.io`. Non sono richieste chiavi API. I blocchi di rete non
richiedono di disattivare TLS; se serve una CA privata usare l'override Compose.
