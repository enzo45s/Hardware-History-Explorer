# Hardware History Explorer — versione 1.1 (fotografie)

Web app per esplorare la storia dei calcolatori commerciali: timeline, catalogo, gallerie fotografiche, schede, confronti, statistiche e assistente AI basato sui dati archiviati.

## Avvio con Docker

1. Installa Docker Desktop / Docker Engine e Docker Compose.
2. Estrai l'archivio e apri il terminale nella cartella `hardware-history-explorer`.
3. Facoltativo: copia `.env.example` in `.env` e configura `OPENAI_API_KEY` per l'assistente.
4. Esegui `docker compose up --build -d`.
5. Apri **http://localhost:8080**. API e documentazione Swagger: **http://localhost:8000/docs**.
6. Arresto: `docker compose down` (i dati e le fotografie caricate restano nei volumi Docker).

Se stai **aggiornando la versione 1.0**, scompatta la nuova versione in una cartella e assicurati di avviare Compose dallo **stesso progetto/cartella**, così Docker può riutilizzare i precedenti volumi. Per backup e migrazione tra cartelle Compose usa un nome progetto stabile (`docker compose -p hardware-history-explorer ...`) e verifica i volumi. Non eseguire `docker compose down -v` perché elimina i volumi, incluse le immagini.

## Aggiungere le fotografie

1. Apri il **Catalogo** (o la Timeline), poi una scheda con **Dettagli**.
2. Scorri fino alla sezione **Galleria fotografica** e clicca **Gestisci fotografie**.
3. Scegli una di tre opzioni:
   - **Cerca su Commons** — cerca fotografie su [Wikimedia Commons](https://commons.wikimedia.org/), visualizza i risultati con dati su licenza/autore e clicca **Aggiungi** su quella corretta. Richiede connessione Internet al servizio Wikimedia Commons da parte del backend. L'app non scarica il file: salva un URL online e i metadati disponibili.
   - **Carica un file** — carica un file JPEG, PNG, WebP o GIF (max 10 MB e 20 megapixel); il backend lo verifica, converte in WebP statico (incluso il primo fotogramma di un GIF), rimuove i metadati incorporati e lo salva nel volume Docker `image_uploads`.
   - **Inserisci URL** — usa il collegamento diretto HTTPS di un'immagine sul Web; puoi aggiungere didascalia, fotografo, fonte e licenza.
4. Puoi aggiungere **più immagini per sistema**, selezionare una **Copertina** e cancellare quelle non più necessarie. La copertina appare nel Catalogo, nella Timeline e nella tabella di confronto.

**Fonti fotografiche:** le foto non sono per forza utilizzabili liberamente. Controlla che mostrino proprio il modello descritto e verifica diritti, licenza, obblighi di attribuzione, condizioni per modifiche e eventuali requisiti di condivisione allo stesso modo. I metadati estratti automaticamente possono essere incompleti. Il progetto espone il link della fonte originale e quello della licenza quando presenti.

## Sviluppo senza Docker

Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv
# attiva il virtualenv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In assenza di `DATABASE_URL` si usa SQLite (`hardware_history.db`); le fotografie vengono salvate in `backend/uploads` a meno che non sia impostato `UPLOAD_DIR`.

Frontend (Node.js 20+):

```bash
cd frontend
npm install
npm run dev
```

Apri **http://localhost:5173**. Vite inoltra `/api` e `/media` a FastAPI sulla porta 8000.

## API fotografie

| Metodo | Percorso | Scopo |
|---|---|---|
| `GET` | `/api/computers/{id}/images` | Elenco immagini |
| `POST` (JSON) | `/api/computers/{id}/images` | Inserimento da URL HTTPS |
| `POST` (multipart) | `/api/computers/{id}/images/upload` | Upload e conversione locale |
| `POST` | `/api/computers/{id}/images/{image_id}/primary` | Imposta la copertina |
| `DELETE` | `/api/computers/{id}/images/{image_id}` | Elimina un'immagine |
| `GET` | `/api/images/search?q=...` | Ricerca Wikimedia Commons |

La struttura dati comprende ora **19 tabelle**: le 18 originali più `computer_images`. Il campo storico `computers.image_url` resta per compatibilità con database esistenti. I media vengono restituiti tramite `/media/<nome>.webp` e non sono inclusi nelle risposte testuali dell'assistente AI.

## Altre funzionalità

- Timeline ordinata per primo lancio commerciale, con precisione storica delle date.
- Catalogo filtrabile per nome, produttore, categoria e anni.
- Schede con specifiche, configurazioni, mercati, dati di vendita, recensioni, fatti e fonti.
- Confronti tra 2–5 sistemi, analisi e distribuzioni statistiche.
- Assistente AI opzionale: solo dati del database, nessun accesso arbitrario a SQL.

## Stato dei dati e sicurezza

I **10 sistemi iniziali sono esempi dimostrativi**, non un corpus storico verificato, e non includono necessariamente fotografie: puoi inserirle dalla nuova interfaccia. I campi che non hanno dati non vengono inventati.

Questo progetto è progettato per uso **locale single-user**: gli endpoint di modifica (compresi upload e cancellazione) **non richiedono autenticazione**. Non esporre la porta API, il frontend o il database a Internet senza autenticazione, autorizzazioni, limiti di richiesta e configurazione di sicurezza adeguati. Per una distribuzione pubblica è necessario aggiungere anche backup e migrazioni database (es. Alembic). `create_all()` crea le tabelle mancanti ma non aggiorna automaticamente tabelle preesistenti con colonne nuove; in questa release si aggiunge soltanto la tabella separata delle immagini.

## Test

```bash
cd backend
pytest -q
```
