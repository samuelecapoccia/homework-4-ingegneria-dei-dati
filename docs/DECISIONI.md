# Decisioni di progetto

Ogni membro annota qui le proprie scelte, con il motivo e i numeri che le supportano.

---

## A – Dati (`ingest/`)

Sorgente: dump di it.wikinews del 20 marzo 2025, formato Wikimedia Enterprise HTML. Contiene un solo file NDJSON da 591 MB con 12.261 pagine del namespace 0 (articoli).
Risultato: 10.914 articoli validi (89% delle pagine) in `data/wikinews_clean.jsonl`, statistiche in `data/stats.json`. Tempo di elaborazione: circa 6 minuti.

| Motivo di scarto | Pagine |
|---|---|
| Non pubblicate | 991 |
| Troppo corte (< 30 parole) | 320 |
| Titolo duplicato (tenuta la versione più recente) | 34 |
| Marcate "Da cancellare" | 1 |
| Pagina di servizio | 1 |
| Totale scartate | 1.347 |

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

Le pagine non pubblicate sono quasi sempre senza fonti, quindi non verificabili: per questo non hanno superato la revisione. Decisione confermata: restano escluse.
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
- Stesso titolo (34 casi): si tiene la versione con `date_modified` più recente.
- Testo identico con titoli diversi: si riconosce con un hash MD5 del testo (0 casi).

### 6. Categorie
Dal campo `categories` sono tolte le categorie di manutenzione ("Pubblicati", "Articoli archiviati", "Articoli da controllare per l'archiviazione", ecc.) e le categorie-data.
*Perché:* non descrivono l'argomento della notizia, e la data ha già il suo campo.

### 7. Licenza
Secondo il dump, i contenuti sono distribuiti con licenza CC BY-SA 3.0: servono l'attribuzione a Wikinews e la condivisione con la stessa licenza.

### Osservazioni sui dati (per le slide)
- Il corpus è sbilanciato nel tempo: il 54% degli articoli (5.856) è del periodo 2005–2008. Dal 2009 si scende a 150–560 articoli l'anno, e del 2025 ce ne sono solo 45 perché il dump è di marzo. Ordinare per data mostrerà soprattutto poche notizie recenti.
- Il corpus è sbilanciato nella geografia e nei temi: "Europa" compare in 7.895 articoli e "Italia" in 6.232, mentre lo sport è il tema più frequente (3.762). Le query su altre aree del mondo avranno pochi risultati: è un limite di copertura del dataset, non del motore.
- La lunghezza varia molto: mediana di 154 parole, media di 229, massimo di 15.335 (un valore anomalo). La normalizzazione per lunghezza di BM25 serve proprio a gestire questa variabilità.

### Prestazioni
Indicizzazione (misure di B, 10.914 documenti):

| Indice | Tempo | Dimensione su disco |
|---|---|---|
| base (StandardAnalyzer) | 3,17 s | 18,59 MB |
| it (ItalianAnalyzer) | 2,15 s | 16,63 MB (−10,5%) |

- L'indice italiano è più piccolo perché le stopword ("il", "di", "che"...) non vengono indicizzate e lo stemming riunisce più forme sotto un'unica radice ("elezioni"/"elezione"): ci sono meno termini distinti e meno occorrenze (*posting*).
- Verifica dell'ordine (C, 3 esecuzioni per ordine, JVM nuova ogni volta): base → it dà base 1.083 ms e it 682 ms; it → base dà it 1.006 ms e base 749 ms. Il primo indice costruito paga circa 300-400 ms di avvio della JVM, quindi l'ordine conta. A parità di posizione, però, l'indice italiano resta più veloce del 7-9%: non indicizzando le stopword scrive meno posting, e questo compensa il costo dello stemming. Conclusione: entrambi gli indici si costruiscono in circa 1 s; a parità di condizioni quello italiano è un po' più veloce e più piccolo del 10%.

Tempi di risposta dell'API (`perf/benchmark_api.py`, le 30 query di `eval/queries.tsv`, 10 query di warm-up escluse; Windows 11, JDK 17, server in locale; risultati in `data/perf.json`):

| Configurazione | Motore (`took_ms`) media / p95 | Richiesta HTTP completa media / p95 | Query senza risultati |
|---|---|---|---|
| base | 2,9 / 8,5 ms | 13,2 / 27,0 ms | 1 |
| it | 1,7 / 3,0 ms | 11,5 / 26,8 ms | 1 |
| it_boost | 2,2 / 4,0 ms | 14,9 / 28,1 ms | 1 |
| it_boost_fuzzy | 20,0 / 58,0 ms | 33,1 / 74,9 ms | 0 |

- Il fuzzy costa circa 10 volte di più nel motore (20 ms contro 2 ms): ogni termine della query viene espanso in tutte le varianti entro la distanza di modifica ammessa, e ognuna va cercata e valutata. In cambio è l'unica configurazione che trova risultati per "Wikipeida".
- Restano comunque tutti sotto i 100 ms, la soglia sotto cui una risposta è percepita come immediata. Quindi la scelta del fuzzy si decide sulla qualità dei risultati, non sulla velocità.
- Le differenze tra base, it e it_boost (1-2 ms) sono dentro il rumore di misura.
- Il tempo della richiesta HTTP completa aggiunge circa 10 ms costanti, dovuti alla nuova connessione per ogni richiesta e allo stack di rete di Windows: dipende dalla macchina, non dal motore. Per confrontare le configurazioni si usa il tempo del motore (`took_ms`), che coincide nell'ordine di grandezza con le misure di D sulla sua macchina.

### Limiti noti
- Alcuni box di navigazione (es. negli articoli su Torino 2006) usano classi HTML diverse da `.navbox` e restano nel testo pulito (segnalato durante i giudizi di rilevanza). La correzione è semplice (aggiungere il selettore), ma non è stata applicata: rigenerare il JSONL cambierebbe gli indici dopo il pooling, e i giudizi non corrisponderebbero più al sistema valutato.
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

## D – Test e valutazione

- **Query.** 30 query bilanciate sui 4 tipi (8/8/7/7), ricavate da articoli reali di it.wikinews.org e non dal sistema. Ogni query ha un bisogno informativo scritto (`eval/topics.tsv`, come i topic TREC): si giudica la risposta al bisogno, non la presenza delle parole. Il controllo "la query ha articoli nel corpus" si fa sul JSONL con una ricerca di sottostringhe, non con il motore, per non scegliere query su cui il sistema va già bene.
- **Pooling cieco.** Per ogni query si uniscono i top-10 delle 4 configurazioni senza duplicati, in ordine casuale (seed 42) e senza indicare la configurazione. Come estratto si usa l'inizio dell'articolo preso dal JSONL e non lo snippet, perché lo snippet cambia con l'analizzatore e farebbe capire da quale configurazione arriva il documento. Le query sono distribuite fra A, C e D a rotazione dentro ogni tipo. B non giudica.
- **Metriche.** P@10 e MRR considerano rilevanti i giudizi 1 e 2. nDCG@10 usa la scala 0/1/2 e premia i documenti molto rilevanti nelle prime posizioni. I documenti non giudicati contano come non rilevanti (convenzione di trec_eval). judged@10 mostra quando questa ipotesi diventa pesante. Le metriche sono implementate a mano (circa 30 righe) e verificate con unit test su casi calcolati a mano.
- **Esperimento a gradini.** Il confronto segue l'ordine base → it → it_boost → it_boost_fuzzy. Ogni configurazione aggiunge una sola modifica, quindi la differenza misura l'effetto di quella scelta (analizzatore italiano, boost sul titolo, fuzzy). I risultati sono separati per tipo di query, perché per esempio il fuzzy dovrebbe servire soprattutto sugli errori di battitura e può peggiorare le altre query.
- **Significatività.** Con 30 query una piccola differenza può essere casuale. Per questo si usa un test di randomizzazione appaiato (10.000 permutazioni), che non richiede l'ipotesi di normalità, insieme al conteggio delle query migliorate, peggiorate e invariate.
- **Strategia di test a livelli** (`eval/STRATEGIA_TEST.md`). Ogni livello risponde a una domanda diversa: i dati sono riproducibili? le metriche sono giuste? l'API rispetta il contratto? le query note funzionano? quanto costa ogni configurazione? quale configurazione dà i risultati migliori? I primi cinque livelli si rilanciano con un comando; l'ultimo richiede giudizi umani.
- **Riproducibilità come test.** Il JSONL è stato rigenerato dal dump su una macchina diversa da quella di A: 10.914 articoli, lo stesso numero indicizzato da B. Il risultato non dipende quindi dall'ambiente di chi l'ha prodotto.
- **Prestazioni misurate sulle stesse 30 query della valutazione**, così costo ed efficacia si confrontano sulle stesse richieste. Il fuzzy costa circa 7 volte di più (13,6 contro 1,9 ms di media): un prezzo che deve essere giustificato da un guadagno sulle query con errori di battitura.
- **Giudici.** Tutti e tre i pool sono giudicati da un LLM (LLM-as-a-judge) con un prompt fisso (`eval/GIUDICE_LLM.md`) e un controllo umano alla cieca su 20 righe per pool: kappa D 0,84, C 0,61, A 0,45; i disaccordi trovati sono corretti nei pool. Il giudice di D non sapeva nulla del sistema, quelli di A e C conoscevano il progetto. Ogni query ha un solo giudice per tutte e 4 le configurazioni e il pool è cieco, quindi il confronto tra configurazioni resta equo.
- **Risultati (30 query, 433 giudizi).** nDCG@10: base 0,631, it 0,653, it_boost 0,659, it_boost_fuzzy 0,768. Solo il fuzzy migliora in modo significativo (+0,108, p = 0,008). Il boost sul titolo ha media quasi nulla ma effetti opposti: persona/luogo 0,79 → 0,93, keyword 0,74 → 0,54. Dettagli e cause in `eval/ANALISI_ERRORI.md`.
