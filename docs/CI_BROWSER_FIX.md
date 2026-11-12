# Correzione failure browser nel job verify

La failure segnalata in `npm run test:browser` avveniva dopo il superamento
di upload, staging, applicazione, deduplicazione e revisione del conflitto.
Falliva il controllo sulla larghezza della pagina a 320 px.

## Causa riprodotta

Le tre schede Calcolatori / Fonti / Importazioni erano disposte in un flex
container senza ritorno a capo. La loro larghezza dipende dal font disponibile.
Con DM Sans caricato, la riproduzione locale ha misurato una pagina larga
**322 px** su una viewport di **320 px**; il pulsante Importazioni arrivava a
321,625 px. Con il font di ripiego la pagina poteva rientrare nella viewport,
pur avendo i pulsanti fuori dal contenitore del contenuto.

## Modifiche

- `frontend/src/admin.css`: le schede possono andare a capo con `flex-wrap`.
  Il controllo di overflow non è stato rimosso né reso tollerante.
- `frontend/tests/browser/imports.cjs`: attesa del caricamento font, controlli
  a 320 e 390 px sia con il font disponibile sia con un font locale più largo,
  verifica che le schede rientrino anche nel loro contenitore.
- In caso di failure il test salva screenshot e JSON con dimensioni, font,
  elementi responsabili e posizione dei pulsanti. Lo scorrimento interno del
  menu mobile resta consentito.
- `.github/workflows/test.yml`: i file diagnostici vengono allegati alla run
  fallita come artifact `browser-diagnostics`.
- `.gitignore` e `frontend/.dockerignore`: risultati browser esclusi dal
  versionamento e dal contesto della build Docker.

## Verifica

Il problema è stato riprodotto prima della correzione caricando DM Sans e
Space Grotesk dalle distribuzioni ufficiali Fontsource in un browser di prova.
I font sono stati usati come fixture locali temporanee, senza cambiare i font
del prodotto o aggiungere dipendenze al progetto.

Con la correzione passa il flusso browser sia con i font web caricati sia con
il font di ripiego; viene verificato anche il font locale più largo. Una
riproduzione temporanea del vecchio layout fa fallire il controllo più severo
e produce correttamente screenshot e JSON diagnostico.

Sono passati i 21 test frontend e la build Vite. Il controllo completo viene
eseguito anche contro la build Docker con PostgreSQL. Il risultato della nuova
run GitHub Actions va confermato su GitHub: una prova locale riuscita non
equivale alla conferma della CI remota.
