# Decisioni di progetto

Ogni membro annota qui le proprie scelte, con il motivo e i numeri che le supportano.

---

## A – Dati (`ingest/`)

**Sorgente:** dump di it.wikinews del 20 marzo 2025, formato Wikimedia Enterprise HTML. Contiene un solo file NDJSON da 591 MB con 12.261 pagine del namespace 0 (articoli).
**Risultato:** 10.914 articoli validi (89% delle pagine) in `data/wikinews_clean.jsonl`, statistiche in `data/stats.json`. Tempo di elaborazione: circa 6 minuti.

| Motivo di scarto | Pagine |
|---|---|
| Non pubblicate | 991 |
| Troppo corte (< 30 parole) | 320 |
| Titolo duplicato (tenuta la versione più recente) | 34 |
| Marcate "Da cancellare" | 1 |
| Pagina di servizio | 1 |
| **Totale scartate** | **1.347** |

### 1. Lettura in streaming
Il `.tar.gz` viene letto riga per riga, senza estrarlo su disco e senza caricarlo in memoria.
*Perché:* il file decompresso pesa circa 600 MB, e la memoria resta costante qualunque sia la dimensione del dump.

### 2. Pulizia dell'HTML
Con BeautifulSoup si tolgono tabelle, box e avvisi, riferimenti, didascalie, elementi tecnici e le sezioni "Fonti", "Notizie correlate", "Collegamenti esterni" e "Note".
*Perché:* non fanno parte della notizia e nell'indice sarebbero rumore. Ad esempio, i titoli delle fonti farebbero trovare l'articolo con parole che non compaiono nella notizia. Gli spazi vengono normalizzati e la punteggiatura riattaccata ("Roma , ieri" diventa "Roma, ieri").

### 3. Solo articoli pubblicati
Si tengono solo le pagine con categoria "Pubblicati" o "Articoli archiviati". Ne sono state scartate 991.
*Perché:* su Wikinews un articolo viene pubblicato solo dopo la revisione della comunità. Le altre pagine possono essere bozze non verificate, e un motore di notizie non dovrebbe mostrarle come notizie.
*Verifica empirica* (`check_non_pubblicati.py`, confronto dei template). Tra le scartate compaiono titoli che sembrano notizie vere (es. "Strage di Bucha: Giletti smentisce un giornalista russo"), ma la differenza decisiva è sulle fonti:

| Template | Non pubblicate (992) | Pubblicate (11.268) |
|---|---|---|
| `Fonte` (cita una fonte) | 26,6% | 84,3% |
| `Data` | 58,8% | 92,1% |
| `Categorizzare` / `Argomenti` (pagina incompleta) | 3,3% / 2,7% | 0,0% / 0,0% |

Le pagine non pubblicate sono quasi sempre senza fonti, quindi non verificabili: per questo non hanno superato la revisione. **Decisione confermata:** restano escluse.
*Trade-off:* perdiamo circa l'8% delle pagine che hanno l'aspetto di una notizia, ma il motore mostra solo contenuti verificati.

### 4. Data di pubblicazione
L'ordine di preferenza è:
1. la categoria-data di Wikinews (es. "12 marzo 2017");
2. `date_created`, cioè la creazione della pagina;
3. la prima data trovata nei primi 300 caratteri del testo;
4. altrimenti `null`.

Risultato: 10.828 date dalla categoria (99,2%), 14 dal testo, 1 da `date_created`, 71 mancanti.
*Perché non `date_modified`:* indica l'ultima modifica, non la pubblicazione. Nel primo record del dump, per esempio, la pagina è stata creata nel 2005 e modificata nel 2024. Una data sbagliata è peggio di una data mancante, perché falserebbe filtri e ordinamenti.

### 5. Duplicati
- **Stesso titolo** (34 casi): si tiene la versione con `date_modified` più recente.
- **Testo identico con titoli diversi**: si riconosce con un hash MD5 del testo (0 casi).

### 6. Categorie
Dal campo `categories` sono tolte le categorie di manutenzione ("Pubblicati", "Articoli archiviati", "Articoli da controllare per l'archiviazione", ecc.) e le categorie-data.
*Perché:* non descrivono l'argomento della notizia, e la data ha già il suo campo.

### 7. Licenza
Secondo il dump, i contenuti sono distribuiti con licenza **CC BY-SA 3.0**: servono l'attribuzione a Wikinews e la condivisione con la stessa licenza.

### Osservazioni sui dati (per le slide)
- **Il corpus è sbilanciato nel tempo:** il 54% degli articoli (5.856) è del periodo 2005–2008. Dal 2009 si scende a 150–560 articoli l'anno, e del 2025 ce ne sono solo 45 perché il dump è di marzo. Ordinare per data mostrerà soprattutto poche notizie recenti.
- **Il corpus è sbilanciato nella geografia e nei temi:** "Europa" compare in 7.895 articoli e "Italia" in 6.232, mentre lo sport è il tema più frequente (3.762). Le query su altre aree del mondo avranno pochi risultati: è un limite di copertura del dataset, non del motore.
- **La lunghezza varia molto:** mediana di 154 parole, media di 229, massimo di 15.335 (un valore anomalo). La normalizzazione per lunghezza di BM25 serve proprio a gestire questa variabilità.

### Prestazioni
**Indicizzazione** (misure di B, 10.914 documenti):

| Indice | Tempo | Dimensione su disco |
|---|---|---|
| base (StandardAnalyzer) | 3,17 s | 18,59 MB |
| it (ItalianAnalyzer) | 2,15 s | 16,63 MB (−10,5%) |

- L'indice italiano è più piccolo perché le stopword ("il", "di", "che"...) non vengono indicizzate e lo stemming riunisce più forme sotto un'unica radice ("elezioni"/"elezione"): ci sono meno termini distinti e meno occorrenze (*posting*).
- Il tempo più basso dell'indice italiano va preso con cautela: lo stemming aggiunge lavoro, quindi la differenza dipende probabilmente dall'ordine di esecuzione (il primo indice paga l'avvio della JVM e la lettura del file da disco a freddo). Con una sola misura la conclusione corretta è che **entrambi gli indici si costruiscono in pochi secondi**.

**Tempi di risposta dell'API:** `perf/benchmark_api.py`, con 100 query, 10 di warm-up escluse, media, mediana, 95° percentile e massimo per ogni configurazione (risultati in `data/perf.json`).

### Limiti noti
- La soglia di 30 parole è una scelta empirica: elimina pagine vuote e stub, ma potrebbe scartare brevi notizie lampo.
- I quasi-duplicati (stessa notizia scritta in modo leggermente diverso) non vengono riconosciuti.
- La data estratta dal testo (14 casi) potrebbe essere una data citata nella notizia invece di quella di pubblicazione.

---

## B – Indice e ricerca (`search/`)


1. **Doppio indice fisico (`index_base` e `index_it`) e similarità BM25:** L'analisi lessicale avviene in fase di indicizzazione, quindi abbiamo separato fisicamente gli indici per confrontare `StandardAnalyzer` (solo tokenizzazione e lowercase) e `ItalianAnalyzer` (rimozione di stopword, elisioni e *light stemming* italiano) usando `BM25Similarity` per la saturazione non lineare della frequenza dei termini e la normalizzazione sulla lunghezza del documento. Sui 10.914 articoli del dump, `index_it` occupa **16,63 MB** (costruito in 2.149 ms) contro i **18,59 MB** di `index_base` (3.168 ms), risparmiando il 10,5% di spazio e il 32% di tempo grazie alla riduzione del vocabolario e aumentando drasticamente il recall (es. su `"terremoti"` i risultati passano da 23 a 144).

2. **Boost sul titolo a tempo di query (`it_boost`):** Invece di duplicare l'indice per pesare il titolo, usiamo `MultiFieldQueryParser` sull'indice `it` assegnando peso `2.0` a `title` e `1.0` a `text`. Questo corregge la distorsione della normalizzazione sulla lunghezza di BM25 (che su `it` premiava articoli brevi con menzioni marginali nel corpo) e porta in cima gli articoli in cui i termini cercati costituiscono il tema centrale della notizia.

3. **Integrazione tra Stemming e Fuzzy Search adattivo (`it_boost_fuzzy`):** In Lucene `FuzzyQuery` non viene analizzata dal `QueryParser` standard e fallirebbe nel confrontare parole non troncate con le radici salvate da `ItalianAnalyzer`. Per questo pre-tokenizziamo i termini con `ItalianAnalyzer` e costruiamo una `BooleanQuery` che combina la query normale/frase (con boost `2.0` per preservare il ranking dei match esatti) e clausole `FuzzyQuery` con `prefixLength=2` e distanza di Levenshtein adattiva (`maxEdits=1` per radici di 4–6 caratteri, `maxEdits=2` per radici >= 7 caratteri), evitando che typo su parole corte (es. `"anconna"` -> `anconn`) collidano con parole frequenti (`"ancora"` -> `ancor`).

4. **Campi specializzati per le date e Snippet sicuri (`<mark>`):** La data è indicizzata in tripla forma (`StoredField` per la lettura, `IntPoint` numerico `YYYYMMDD` per range query veloci e `SortedDocValuesField` per l'ordinamento cronologico). Gli snippet sono generati con `Highlighter` e `SimpleHTMLFormatter("<mark>", "</mark>")` previa rimozione di parentesi angolari dal testo sorgente, rispettando il Contratto 3 e prevenendo problemi di rendering HTML nel frontend.

---

## C – Web e infrastruttura (`search/.../web/`, `web/`, `start.sh`)

1. **Javalin con un unico `Searcher` aperto all'avvio.** Javalin è un server leggero (una classe, avvio in circa un secondo, nessun application server da configurare). Gli indici vengono aperti una volta sola e condivisi tra le richieste, perché `IndexSearcher` di Lucene è thread-safe in lettura: riaprirli a ogni richiesta costerebbe tempo a ogni query.
2. **Controllo dei parametri prima di chiamare Lucene.** Query vuota, configurazione inesistente, `k` fuori da 1–100, `page < 1` → HTTP 400 con un messaggio JSON leggibile. Gli errori interni → HTTP 500 con un messaggio generico, senza dettagli tecnici nel client. Abbiamo posto dei limiti (`page × k ≤ 1000`, query ≤ 500 caratteri) per evitare richieste inutilmente costose. *Perché:* gli script di D e A chiamano l'API in automatico e devono distinguere un errore loro (400) da un guasto del server (500).
3. **Snippet sicuro.** Il frontend fa l'escape di tutto il testo e poi ripristina **solo** `<mark>` e `</mark>`; i link vengono accettati solo se iniziano con `http(s)://`. *Perché:* il testo viene da un wiki modificabile da chiunque; inserirlo come HTML senza controlli permetterebbe di iniettare script (XSS). È una seconda difesa, in aggiunta alla rimozione di `<` e `>` già fatta da B.
4. **Frontend in HTML/CSS/JS semplice, senza framework.** Nessuna build e nessuna dipendenza esterna, quindi funziona anche offline. Lo stato della ricerca sta nell'URL (`?q=...&config=...&page=...`): i link si possono condividere e il tasto "indietro" funziona. La modalità **"Confronta le 4 configurazioni"** affianca i primi 10 risultati di ciascuna e serve nella demo a mostrare l'effetto di stemming, boost e fuzzy.
5. **Un comando e nessuna dipendenza dalla rete durante la demo.** `./start.sh` compila, costruisce gli indici se mancano (circa 2 secondi su 10.914 articoli) e avvia il server. Dati, indici e pagina sono tutti in locale: dopo il primo avvio (che scarica le dipendenze Maven) `./start.sh -o` funziona senza rete.
6. **Test dell'API (JUnit, `mvn test`, 7 test).** Con un `Searcher` finto si verificano il formato del contratto 3 e tutti i casi di errore, senza bisogno degli indici. Con un mini-indice reale di 3 documenti si verifica l'integrazione con Lucene: `<mark>` nello snippet, il titolo che sale in cima con `it_boost`, l'errore di battitura "elezzioni" trovato solo da `it_boost_fuzzy`, e una query con sintassi rotta (`roma AND (`) che non deve dare errore 500.
7. **Licenza.** Il footer riporta **CC BY-SA 3.0**, cioè la licenza reale dichiarata nel dump (verificata da A), invece della "CC BY" indicata nel piano iniziale.
