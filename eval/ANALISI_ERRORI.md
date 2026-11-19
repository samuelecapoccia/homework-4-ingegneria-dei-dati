# Analisi degli errori (scritta a mano)

Le tabelle con le top-10 affiancate e i giudizi le genera `error_analysis.py` in `results/analisi_errori_<A>_vs_<B>.md`.
Le cause, invece, sono scritte qui, perché i file generati vengono riscritti a ogni esecuzione.

Numeri finali: **30 query, 433 giudizi** (pool di A, C e D, giudicati da un LLM con controllo alla cieca).

| config | P@10 | MRR | nDCG@10 |
|---|---|---|---|
| base | 0,547 | 0,713 | 0,627 |
| it | 0,567 | 0,739 | 0,656 |
| it_boost | 0,567 | 0,716 | 0,653 |
| it_boost_fuzzy | **0,637** | **0,854** | **0,767** |

| passo | Δ nDCG@10 | query migliorate / peggiorate | p |
|---|---|---|---|
| base → it (+ ItalianAnalyzer) | +0,029 | 11 / 11 | 0,082 |
| it → it_boost (+ boost sul titolo) | −0,002 | 16 / 9 | 0,963 |
| it_boost → it_boost_fuzzy (+ fuzzy) | **+0,114** | 11 / 1 | **0,004** |

## 1. Il boost sul titolo premia le parole generiche (it → it_boost)

**Media quasi nulla, effetti opposti.** Il boost migliora 16 query e ne peggiora 9: la media non si muove (−0,002), ma
per tipo di query sì.

| tipo | it | it_boost |
|---|---|---|
| persona/luogo (8) | 0,793 | **0,938** |
| keyword (8) | 0,748 | **0,489** |

**Meccanismo.** La query è un OR di termini, e ogni termine viene cercato in `title^2` e in `text`. Un titolo corto
con 1-2 parole generiche della query prende un punteggio alto: c'è il boost, e BM25 normalizza sulla lunghezza del
campo, che per un titolo è minima. Questo punteggio supera quello di un articolo che contiene tutte le parole, ma solo
nel testo. Se la parola che distingue il bisogno compare raramente nei titoli, il boost porta in cima documenti sbagliati.

| query | nDCG@10 it → it_boost | cosa succede |
|---|---|---|
| q04 "dimissioni del papa" | 0,832 → **0,000** | Salgono le dimissioni di Mbeki, Monti, Previti, Koizumi, Follini…: "dimissioni" nel titolo, del papa nessuna traccia. Nessuno dei 9 documenti nuovi è rilevante |
| q06 "elezioni presidenziali americane" | 0,825 → 0,131 | Salgono le presidenziali di Polonia, Russia, Bolivia e Senegal. "Americane" nei titoli non compare (si scrive "USA"): vocabulary mismatch |
| q01 "naufragio nave da crociera" | 0,922 → 0,617 | Salgono titoli con "naufragio" o "nave" che non riguardano navi da crociera |
| q03 "incidente centrale nucleare" | 0,995 → 0,791 | Salgono "demolita la centrale nucleare", "incidente alla centrale idroelettrica", "centrale nucleare a rischio razzi" |

**Conclusione.** Il boost sul titolo funziona quando la query è il nome di un'entità (persona/luogo) e peggiora quando
la query descrive un tema con parole comuni (keyword).

## 2. Il fuzzy: il miglioramento più forte, con un limite (it_boost → it_boost_fuzzy)

- **Errori di battitura: nDCG@10 da 0,232 a 0,671.** Migliora 11 query e ne peggiora solo 1.

| query | it_boost | it_boost_fuzzy |
|---|---|---|
| q28 "Wikipeida" | 0,00 (0 risultati) | **1,00** |
| q29 "calciopolli Juventus" | 0,19 | **1,00** |
| q26 "olimpiadi Pechinno" | 0,00 | **0,80** |
| q24 "terremotto Haiti" | 0,66 | 0,89 |
| q27 "mondiali di calcio Sudafrca" | 0,43 | 0,66 |
| q25 "Michael Shumacher" | 0,35 | **0,35** |
| q30 "Brexti referendum" | 0,00 | 0,00 |

- **q25 "Shumacher": il fuzzy non corregge**, come previsto dalla configurazione di B. Con `prefixLength=2` le prime due
  lettere devono essere esatte, e "sh" non è "sc". È il prezzo della scelta che rende il fuzzy veloce e ne limita le
  espansioni.
- **Unico peggioramento: q09 "Valentino Rossi"** (Δ −0,024). Non entrano documenti nuovi: le clausole fuzzy sulle
  varianti di "valentin" e "ross" cambiano solo un po' l'ordine.
- **"terremotto anconna"** (test esplorativo di B, vedi `STRATEGIA_TEST.md`). Il fuzzy mette in cima articoli su Ancona
  senza terremoti, ma nel corpus non c'è nessun articolo su un terremoto ad Ancona: è un problema di ordinamento
  (l'IDF di "Ancona", termine raro), non di documenti persi.
- **Costo:** circa 20 ms contro circa 2 ms (7-10 volte di più), sempre sotto i 100 ms (`STRATEGIA_TEST.md`).

## 3. q30 "Brexti referendum": i rilevanti esistono ma nessuna configurazione li porta nella top-10

Nel corpus ci sono 3 articoli che contengono "brexit". Il più rilevante è *Il Regno Unito esce dall'Unione Europea*
(id 43253). **Nessuno dei 3 contiene "referendum".**

| articolo | rank "Brexti referendum" (it_boost_fuzzy) | rank "Brexit referendum" (it_boost, scritta giusta) |
|---|---|---|
| 43253 Il Regno Unito esce dall'Unione Europea | 77 | 33 |
| 51220 Rishi Sunak nuovo leader dei conservatori | >100 | 32 |
| 50986 Permesso di lavoro negato a un calciatore olandese | >100 | 34 |

- **Il fuzzy fa la sua parte, ma non basta.** Senza fuzzy "brexti" non corrisponde a niente; con il fuzzy l'articolo
  viene trovato ("brext" ↔ "brexit", 1 modifica), ma solo al 77° posto.
- **Anche con la query scritta giusta resta al 33° posto.** Vale lo stesso meccanismo della sezione 1: decine di
  articoli con "referendum" nel titolo superano un articolo che contiene il termine raro "brexit" solo nel testo.
- **Effetto sulle metriche.** Nessun documento rilevante entra nel pool, quindi per q30 tutte le metriche valgono 0 per
  tutte le configurazioni. La query non distingue le configurazioni, ma documenta un limite reale del sistema.

## 4. ItalianAnalyzer (base → it): un piccolo guadagno, non significativo

+0,029 di nDCG@10 (p = 0,082), con 11 query migliorate e 11 peggiorate. I cali più grandi sono piccoli e riguardano due
frasi esatte (q20 "Giro d'Italia" −0,077, q18 "Stazione Spaziale Internazionale" −0,056): in entrambe cambiano solo
1-2 documenti in classifica. Il vantaggio concreto, oltre alla qualità, è un indice più piccolo del 10%.

## 5. Lezioni per la valutazione

- **La media nasconde effetti di segno opposto.** Il boost ha una media nulla ma cambia molto per tipo di query: per
  questo riportiamo i risultati anche per tipo.
- **Con 30 query solo un effetto grande è significativo.** Il fuzzy lo è (p = 0,004), ItalianAnalyzer e boost no.
- **Le query senza documenti rilevanti valgono 0 per tutti** e non distinguono le configurazioni (q30).

## Sviluppi possibili (non applicati: il motore è congelato e regolarlo sulle query di test sarebbe overfitting)

- Boost sul titolo più basso, oppure applicato solo quando tutti i termini compaiono nel titolo.
- Richiedere una quota minima di termini (*minimum should match*).
- Sinonimi in fase di query (americane → USA, Stati Uniti).
- Fuzzy solo per i termini che non esistono nel vocabolario dell'indice (stile "forse cercavi…"), con `prefixLength`
  più basso per correggere anche le prime lettere.
