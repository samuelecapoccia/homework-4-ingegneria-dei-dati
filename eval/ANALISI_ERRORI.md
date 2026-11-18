# Analisi degli errori (scritta a mano)

Le tabelle con le top-10 affiancate e i giudizi le genera `error_analysis.py` in `results/analisi_errori_<A>_vs_<B>.md`.
Le cause, invece, sono scritte qui, perché i file generati vengono riscritti a ogni esecuzione.

> **Stato: PRELIMINARE.** I numeri si riferiscono alle 10 query di D (giudice LLM con controllo a campione,
> kappa 0,84). Vanno riverificati sui risultati finali con tutte le 30 query.

## 1. Il boost sul titolo premia le parole generiche (it → it_boost)

**Meccanismo.** La query è un OR di termini, e ogni termine viene cercato in `title^2` e in `text`.
Un titolo corto che contiene 2 parole generiche della query prende un punteggio alto: c'è il boost, e BM25 normalizza
sulla lunghezza del campo, che per un titolo è minima. Questo punteggio supera quello di un articolo che contiene
tutte le parole, ma solo nel testo. Se la parola che distingue il bisogno compare raramente nei titoli, il boost
porta in cima documenti sbagliati.

| query | nDCG@10 it → it_boost | cosa succede |
|---|---|---|
| q06 "elezioni presidenziali americane" | 0,825 → **0,131** | Salgono le presidenziali di Polonia, Russia, Bolivia e Senegal, che hanno "elezioni presidenziali" nel titolo. "Americane" nei titoli quasi non compare: si scrive "USA" o "Stati Uniti" (vocabulary mismatch). Dei 6 documenti che entrano nella top-10, solo 1 è rilevante |
| q03 "incidente centrale nucleare" | 0,995 → 0,791 | Salgono "demolita la centrale nucleare" (nessun incidente), "incidente alla centrale idroelettrica" (non nucleare) e "centrale nucleare a rischio razzi" (incidente non avvenuto): 2 parole su 3 nel titolo, ma il significato è diverso |
| q18 "Stazione Spaziale Internazionale" | 0,912 → 0,848 | Sale al 2° posto un evento divulgativo per bambini che ha la frase esatta nel titolo |

**Dove invece il boost aiuta.** Nelle query persona/luogo l'nDCG@10 passa da 0,77 a 0,88: lì il titolo nomina
esattamente l'entità cercata.

**Conclusione.** Il boost sul titolo funziona quando la query è il nome di un'entità e peggiora quando la query
descrive un tema con parole comuni.

## 2. Il fuzzy: dove aiuta e dove no (it_boost → it_boost_fuzzy)

- **Aiuta sulle query con errori di battitura:** l'nDCG@10 medio passa da 0,36 a 0,52. Il caso più netto è
  q28 "Wikipeida", che ha 0 risultati con base, it e it_boost e 10 con il fuzzy (dal pooling).
- **Effetto trascurabile su q09 "Valentino Rossi"** (Δ nDCG -0,024). Non entrano documenti nuovi: le clausole fuzzy
  sulle varianti di "valentin" e "ross" cambiano solo un po' l'ordine.
- **"terremotto anconna"** (test esplorativo di B, vedi `STRATEGIA_TEST.md`). Il fuzzy trova 254 risultati e mette in
  cima articoli su Ancona senza terremoti. Nel corpus però non c'è nessun articolo su un terremoto ad Ancona: è un
  problema di ordinamento (l'IDF di "Ancona", termine raro, supera quello di "terremoto"), non di documenti persi.
- **Costo:** latenza media 13,6 ms contro 1,9 ms, circa 7 volte di più (`STRATEGIA_TEST.md`).

## 3. q30 "Brexti referendum": i rilevanti esistono ma nessuna configurazione li porta nella top-10

Nel corpus ci sono 3 articoli che contengono "brexit". Il più rilevante è *Il Regno Unito esce dall'Unione Europea*
(id 43253). **Nessuno dei 3 contiene "referendum".** La copertura di Wikinews non ha un articolo sul referendum del
2016 con quella parola.

| articolo | rank "Brexti referendum" (it_boost_fuzzy) | rank "Brexit referendum" (it_boost, scritta giusta) |
|---|---|---|
| 43253 Il Regno Unito esce dall'Unione Europea | 77 | 33 |
| 51220 Rishi Sunak nuovo leader dei conservatori | >100 | 32 |
| 50986 Permesso di lavoro negato a un calciatore olandese | >100 | 34 |

- **Il fuzzy fa la sua parte, ma non basta.** Senza fuzzy "brexti" non corrisponde a niente e l'articolo 43253 non
  viene proprio trovato. Con il fuzzy viene trovato ("brext" ↔ "brexit", 1 modifica), ma solo al 77° posto: la
  clausola fuzzy ha un peso più basso del match esatto.
- **Anche con la query scritta giusta resta al 33° posto.** Vale lo stesso meccanismo della sezione 1. Decine di
  articoli con "referendum" nel titolo (Bolivia, Venezuela, Italia, Ungheria, …) superano un articolo che contiene il
  termine raro "brexit" solo nel testo.
- **Effetto sulle metriche.** Nessun documento rilevante entra nel pool (top-10 di 4 configurazioni), quindi per q30
  nDCG@10, P@10 e MRR valgono 0 per tutte le configurazioni. La query non aiuta a distinguere le configurazioni, ma
  documenta un limite reale del sistema.

## 4. Lezioni per la valutazione

- **Con poche query un singolo giudizio sposta i numeri.** Nel caso di q18 conta la differenza tra il giudizio di D e
  quello dell'LLM su un solo documento. Nessuna differenza tra configurazioni è significativa (tutti i p > 0,05 sulle
  10 query).
- **Le query senza documenti rilevanti valgono 0 per tutti e non distinguono le configurazioni.** Per questo le query
  sono state controllate sul corpus prima del pooling. q30 mostra però che "ci sono articoli candidati" non vuol dire
  "il sistema li trova".

## Sviluppi possibili (non applicati: il motore è congelato e regolarlo sulle query di test sarebbe overfitting)

- Boost sul titolo più basso, oppure applicato solo quando tutti i termini compaiono nel titolo.
- Richiedere una quota minima di termini (*minimum should match*), così un documento con 2 parole generiche su 3 non
  supera uno che le ha tutte.
- Sinonimi in fase di query (americane → USA, Stati Uniti).
- Fuzzy solo per i termini che non esistono nel vocabolario dell'indice (stile "forse cercavi…"). Si eviterebbero le
  espansioni inutili su parole già corrette, come in q09.
