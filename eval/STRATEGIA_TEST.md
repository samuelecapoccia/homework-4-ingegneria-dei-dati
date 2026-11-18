# Strategia di test

Il sistema è verificato su 6 livelli, dal singolo componente fino alla qualità dei risultati vista dall'utente.
Ogni livello risponde a una domanda diversa. I livelli 1-5 sono automatici e si rilanciano con un comando, il livello 6 richiede giudizi umani.

| # | Livello | Domanda | Chi | Comando | Esito (18/11/2026, Mac di D) |
|---|---|---|---|---|---|
| 1 | Riproducibilità dei dati | Il JSONL si rigenera identico dal dump, su un'altra macchina? | A (script), D (verifica) | `python ingest/parse_dump.py --dump data/...tar.gz --out data/wikinews_clean.jsonl --stats data/stats.json` | **10.914 articoli**, lo stesso numero indicizzato da B. 12.261 righe lette, scartate 991 non pubblicate, 320 troppo corte, 34 con titolo duplicato, 2 altre. 46 s |
| 2 | Unit test delle metriche | P@10, MRR e nDCG@10 sono calcolate bene? | D | `python -m pytest eval/tests -q` | **7 superati** su casi calcolati a mano. 1 saltato: il confronto con ir_measures, che non è installato |
| 3 | Contratto dell'API e integrazione | L'API rispetta il contratto 3 e gestisce gli errori? | C | `cd search && mvn test` (JUnit) | **7/7 superati**: formato e paginazione, valori di default, 400 su parametri non validi, 500 senza dettagli interni, 404, pagina web, integrazione con un mini-indice Lucene reale (boost, fuzzy, sintassi rotta) |
| 4 | Query note (known-item) | Il documento atteso finisce in cima? | B | `cd search && mvn compile exec:java` | **5/5 al rank 1**: stemming, boost del titolo, frase esatta, notizia specifica, errore di battitura |
| 5 | Prestazioni | Quanto costa ogni configurazione? | A (script), D (misura con le 30 query) | `python perf/benchmark_api.py --queries eval/queries.tsv` | Vedi la tabella qui sotto. 0 errori |
| 6 | Efficacia | Quale configurazione dà risultati migliori, e su quali query? | D (giudizi di A, C, D) | `eval/pool.py`, poi `build_qrels.py`, poi `evaluate.py` | In corso: vedi `eval/results/risultati.md` |

## Prestazioni (livello 5)

Latenza lato client in ms sulle 30 query di valutazione, dopo 10 query di riscaldamento.

| config | media | mediana | p95 | max | query senza risultati |
|---|---|---|---|---|---|
| base | 1,8 | 1,8 | 2,7 | 2,9 | 1 |
| it | 1,6 | 1,6 | 2,6 | 3,2 | 1 |
| it_boost | 1,9 | 1,8 | 3,1 | 3,9 | 1 |
| it_boost_fuzzy | 13,6 | 11,9 | 38,5 | 40,5 | 0 |

- Il fuzzy costa circa 7 volte di più (13,6 contro 1,9 ms di media), perché ogni termine si espande in tutte le parole del vocabolario entro 1-2 modifiche. Resta comunque sotto i 41 ms.
- L'unica query senza risultati per base, it e it_boost è "Wikipeida" (q28). Solo il fuzzy la recupera.
- Indicizzazione (misure di B): base 3,17 s e 18,59 MB, it 2,15 s e 16,63 MB. La differenza di tempo dipende in parte dall'ordine di costruzione: il primo indice paga l'avvio della JVM.
- Il benchmark legge `queries.tsv` con `csv.DictReader`, che toglie le virgolette alle query di tipo frase. Quindi le frasi sono state misurate come semplici parole chiave.

## Test esplorativo: "terremotto anconna" (livello 4)

- Con it_boost: 0 risultati. Con it_boost_fuzzy: 254 risultati, ma ai primi due posti ci sono articoli su Ancona che non parlano di terremoti.
- Verifica sul corpus: un solo articolo contiene sia "Ancona" sia "terremot", ed è il riepilogo del campionato di Serie B 2008-2009 (id 22782, posizione 85 con il fuzzy). Non parla di un terremoto ad Ancona. **Nel corpus non c'è nessuna risposta corretta**, quindi il fuzzy non perde documenti rilevanti: il difetto riguarda solo cosa mostra in cima.
- Probabile causa dell'ordine: l'IDF. "Ancona" è un termine raro e pesa più di "terremoto", che è frequente. In più gli articoli brevi con "Ancona" anche nel titolo sono favoriti da BM25 e dal boost sul titolo.
- Lezione per la valutazione: una query senza documenti rilevanti non distingue le configurazioni (nDCG = 0 per tutte). Per questo le 30 query di valutazione sono state controllate sul corpus prima del pooling (`eval/check_queries.py`).
