# Importare descrizioni storiche da JSON

Da **Amministrazione → Importazioni**, scegli **Descrizioni storiche (JSON)**
nel menu **Fonte dati**. Carica il file, conferma i diritti di importazione già
previsti dal pannello e premi **Prepara anteprima dal file**.

Ogni riga mostra il calcolatore associato, il testo attuale, quello proposto e
la fonte. Controlla gli abbinamenti prima di premere **Applica le righe pronte
all'archivio**. Il file originale resta scaricabile senza modifiche.

## Formato

JSON UTF-8, anche con BOM, con un elenco di 1–1000 oggetti (massimo 8 MB).
È accettato anche `{"records": [...]}`. Esempio puramente dimostrativo:

```json
[
  {
    "manufacturer": "Produttore dimostrativo",
    "model_name": "Sistema dimostrativo",
    "description": "Una breve sintesi in italiano basata sulla fonte indicata.",
    "source": {
      "title": "Fonte dimostrativa",
      "url": "https://example.org/sistema-dimostrativo",
      "source_type": "website"
    }
  }
]
```

`manufacturer`, `model_name`, un testo `description` non vuoto e `source`
con titolo e URL HTTP(S) sono obbligatori. Il testo conserva paragrafi e
caratteri italiani; sono accettati fino a 20.000 caratteri per descrizione.
È facoltativo `evidence`, per note o passaggi della fonte (massimo 3.000
caratteri). La citazione può includere anche autore, editore, licenza e date
esplicitamente fornite. Non vengono inventate licenze o date di consultazione.
URL con credenziali o schemi diversi da HTTP(S) vengono rifiutati.

Non aggiungere ID del database, flag di verifica, prezzi, configurazioni o
altri campi: questo importatore aggiorna esclusivamente la descrizione. Le
righe non valide vengono segnalate separatamente, senza scartare quelle valide.

## Abbinamenti e testi esistenti

- Si aggiornano soltanto computer già censiti, anche se una chiamata API tenta
  di disattivare questa protezione. Nessun produttore o sistema viene creato.
- L'abbinamento usa marca e modello, con marche brevi (Acorn, Sun, NeXT,
  Kaypro...), alias noti come Apple ][ e i nomi precedenti già approvati
  durante gli accorpamenti. L'indice viene costruito una volta per anteprima.
- I nomi del catalogo rimangono invariati. Modelli diversi come Apple IIc e
  IIe non vengono considerati equivalenti; non si usano abbinamenti approssimativi.
- Se più schede corrispondono, scegli quella corretta nella riga. Una riga
  senza associazione a un sistema esistente viene esclusa quando applichi il
  lotto. Puoi cercare e associare manualmente un computer prima di applicare.
- Un testo vuoto o il vecchio testo preimpostato viene sostituito. Un testo
  già curato resta invariato: una proposta diversa diventa un conflitto in
  **Fonti e verifiche**, dove puoi accettarla o mantenere la descrizione attuale.
- I testi sono ricontrollati al momento dell'applicazione: una modifica manuale
  successiva all'anteprima prevale e una scheda eliminata non viene ricreata.

Ricaricare lo stesso file non duplica computer o fonti e lascia invariate le
descrizioni già identiche. Ogni nuova anteprima mantiene il proprio resoconto
e le proprie asserzioni; applicare due volte lo stesso lavoro non lo riesegue.
**Riprova con una nuova anteprima** permette di riesaminare gli abbinamenti dopo
eventuali correzioni al catalogo.

## Fonti, assistente e ricerca automatica

Gli URL sono citazioni dichiarate dall'operatore: non vengono aperti dal
caricamento. Un testo prodotto con ChatGPT non diventa verificato per il solo
fatto di avere un link. Le asserzioni restano da verificare fino a una decisione
umana esplicita. Non vengono estratti automaticamente numeri, prezzi o
specifiche dalla prosa.

Le descrizioni applicate compaiono nelle schede e nel contesto dell'assistente
insieme alle fonti associate. La successiva ricerca automatica di cenni storici
le conserva come testi curati. Se una richiesta automatica era già in corso,
il controllo delle modifiche impedisce di sovrascrivere il nuovo testo.
Non servono chiavi AI, chiamate a pagamento o modifiche allo schema del database.

Da terminale è disponibile lo stesso flusso:

```bash
python -m app.importing descrizioni.json --provider historical_descriptions --rights-confirmed
python -m app.importing descrizioni.json --provider historical_descriptions --rights-confirmed --apply
```

Eseguilo dalla directory `backend` nell'ambiente Python configurato. Il primo
comando prepara soltanto l'anteprima; il secondo crea un nuovo lavoro e lo
applica esplicitamente.

## Verifiche ripetibili

Le prove usano testi sintetici, senza accesso a siti o servizi AI:

```bash
cd backend
python -m pytest tests/test_description_imports.py -q
```

Con Compose avviato su un database di prova e Chromium installato:

```bash
cd frontend
npm run test:browser:descriptions
```

La prova browser crea tre schede sintetiche, verifica anteprima, sostituzione
dei testi preimpostati, revisione di un conflitto, ripetizione e layout mobile,
poi elimina soltanto le schede che ha creato.
