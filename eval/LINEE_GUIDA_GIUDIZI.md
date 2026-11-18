# Linee guida per i giudizi di rilevanza (HW4)

Giudicano A, C e D (B no: conoscendo il motore sarebbe di parte).
Ognuno riceve un file `pool_X.csv` con circa 10 query. Per ogni riga si riempie **solo** la colonna `rilevanza`.

## Come si giudica

1. Leggi la colonna `bisogno_informativo`: è **quello** che l'utente voleva, non le parole della query.
   Per le query con errori di battitura, tra parentesi quadre c'è la query intesa (es. `[intesa: terremoto Haiti]`).
2. Leggi `titolo` ed `estratto` (l'inizio dell'articolo). Se non basta, apri `url`.
3. Giudica **il documento**, non la posizione o la frase evidenziata. Non sai quale configurazione l'ha trovato, ed è voluto.
4. Non usare il motore di ricerca mentre giudichi.
5. Nel dubbio tra due valori, scegli il più basso. Puntiamo a circa 20 secondi per riga.

## Scala

| Valore | Significato | Esempio (q11 "Barack Obama") |
|---|---|---|
| **2** | Molto rilevante: l'articolo parla **principalmente** del bisogno informativo | "Obama vince le elezioni presidenziali" |
| **1** | Parzialmente rilevante: il tema c'è ma è secondario, oppure è citato con qualche informazione utile | Articolo sul G20 in cui Obama fa una dichiarazione |
| **0** | Non rilevante: il tema non c'è, oppure è solo nominato di sfuggita, o c'è un omonimo | Articolo su Michelle Obama ristoratrice, oppure un elenco di notizie in cui "Obama" compare una volta |

Casi frequenti:
- Articolo sullo stesso evento ma da un altro punto di vista (es. q01: il processo al comandante della Concordia) → **2** se l'evento è il tema principale.
- Notizia di sport con il nome solo nell'ordine d'arrivo (es. q09, Rossi decimo) → **1**.
- Pagine di servizio, elenchi o calendari senza contenuto informativo sul tema → **0**.

## Consegna

- Salva il file **con lo stesso nome**, in formato CSV (Excel: "CSV UTF-8" se c'è, altrimenti "CSV (delimitato dal separatore di elenco)"; Google Fogli: File → Scarica → CSV).
- Non cambiare le colonne `query_id` e `doc_id` e non riordinare le righe di altre query.
- Ammessi solo 0, 1, 2. Le righe vuote vengono segnalate da D come mancanti.
