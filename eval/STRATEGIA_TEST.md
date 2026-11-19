# Strategia di test

Il sistema è verificato su 6 livelli, dal singolo componente fino alla qualità dei risultati vista dall'utente.
Ogni livello risponde a una domanda diversa. I livelli 1-5 sono automatici e si rilanciano con un comando, il livello 6 richiede giudizi umani.

| # | Livello | Domanda | Chi | Comando | Esito (18/11/2026, Mac di D) |
|---|---|---|---|---|---|
| 1 | Riproducibilità dei dati | Il JSONL si rigenera identico dal dump, su un'altra macchina? | A (script), D (verifica) | `python ingest/parse_dump.py --dump data/...tar.gz --out data/wikinews_clean.jsonl --stats data/stats.json` | **10.914 articoli**, lo stesso numero indicizzato da B. 12.261 righe lette, scartate 991 non pubblicate, 320 troppo corte, 34 con titolo duplicato, 2 altre. 46 s |
| 2 | Unit test delle metriche | P@10, MRR e nDCG@10 sono calcolate bene? | D | `python -m pytest eval/tests -q` | **7 superati** su casi calcolati a mano. 1 saltato: il confronto con ir_measures, che non è installato |
| 3 | Contratto dell'API e integrazione | L'API rispetta il contratto 3 e gestisce gli errori? | C | `cd search && mvn test` (JUnit) | **7/7 superati**: formato e paginazione, valori di default, 400 su parametri non validi, 500 senza dettagli interni, 404, pagina web, integrazione con un mini-indice Lucene reale (boost, fuzzy, sintassi rotta) |
| 4 | Query note (known-item) | Il documento atteso finisce in cima? | B | `cd search && mvn compile exec:java` | **5/5 al rank 1**: stemming, boost del titolo, frase esatta, notizia specifica, errore di battitura |
| 5 | Prestazioni | Quanto costa ogni configurazione? | A (misure ufficiali), D (replica su un'altra macchina) | `python perf/benchmark_api.py --queries eval/queries.tsv` | Vedi le tabelle qui sotto. 0 errori |
| 6 | Efficacia | Quale configurazione dà risultati migliori, e su quali query? | D (giudizi LLM sui pool di A, C, D, controllati alla cieca) | `eval/pool.py`, poi `build_qrels.py`, poi `evaluate.py` | **30 query, 433 giudizi.** nDCG@10: base 0,627, it 0,656, it_boost 0,653, it_boost_fuzzy **0,767**. Solo il fuzzy migliora in modo significativo (+0,114, p = 0,004). Dettagli in `results/risultati.md` |

## Prestazioni (livello 5)

**Misure ufficiali (A):** tempo del motore (`took_ms`), Windows 11, JDK 17, 30 query, 10 di riscaldamento escluse.
Le query di tipo frase sono misurate come frasi.

| config | media | p95 | query senza risultati |
|---|---|---|---|
| base | 2,9 ms | 8,5 ms | 1 |
| it | 1,7 ms | 3,0 ms | 1 |
| it_boost | 2,2 ms | 4,0 ms | 1 |
| it_boost_fuzzy | 20,0 ms | 58,0 ms | 0 |

**Replica (D):** latenza lato client, Mac (Apple Silicon). In questa misura le query di tipo frase erano ancora
misurate come parole chiave: è stata fatta prima della correzione `QUOTE_NONE`.

| config | media | p95 |
|---|---|---|
| base | 1,8 ms | 2,7 ms |
| it | 1,6 ms | 2,6 ms |
| it_boost | 1,9 ms | 3,1 ms |
| it_boost_fuzzy | 13,6 ms | 38,5 ms |

- **Le due macchine danno lo stesso quadro.** Il fuzzy costa 7-10 volte di più, perché ogni termine si espande in
  tutte le parole del vocabolario entro 1-2 modifiche. Resta comunque sotto i 100 ms, la soglia di risposta percepita
  come immediata. Le differenze tra base, it e it_boost (1-2 ms) sono nel rumore di misura.
- L'unica query senza risultati per base, it e it_boost è "Wikipeida" (q28). Solo il fuzzy la recupera.
- **Indicizzazione:** entrambi gli indici si costruiscono in circa 1 s. La misura con l'ordine invertito (3 esecuzioni
  per ordine, JVM nuova ogni volta) mostra due effetti:
  - il primo indice paga 300-400 ms di avvio della JVM (base → it: base 1083 ms, it 682 ms; it → base: it 1006 ms,
    base 749 ms);
  - a parità di posizione l'indice italiano resta più veloce del 7-9% e più piccolo del 10% (16,63 contro 18,59 MB),
    perché senza stopword scrive meno postings.

## Test esplorativo: "terremotto anconna" (livello 4)

- Con it_boost: 0 risultati. Con it_boost_fuzzy: 254 risultati, ma ai primi due posti ci sono articoli su Ancona che non parlano di terremoti.
- Verifica sul corpus: un solo articolo contiene sia "Ancona" sia "terremot", ed è il riepilogo del campionato di Serie B 2008-2009 (id 22782, posizione 85 con il fuzzy). Non parla di un terremoto ad Ancona. **Nel corpus non c'è nessuna risposta corretta**, quindi il fuzzy non perde documenti rilevanti: il difetto riguarda solo cosa mostra in cima.
- Probabile causa dell'ordine: l'IDF. "Ancona" è un termine raro e pesa più di "terremoto", che è frequente. In più gli articoli brevi con "Ancona" anche nel titolo sono favoriti da BM25 e dal boost sul titolo.
- Lezione per la valutazione: una query senza documenti rilevanti non distingue le configurazioni (nDCG = 0 per tutte). Per questo le 30 query di valutazione sono state controllate sul corpus prima del pooling (`eval/check_queries.py`).
