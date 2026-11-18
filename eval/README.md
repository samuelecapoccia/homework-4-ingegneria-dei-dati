# eval/ — Test e valutazione (ruolo D)

Requisiti: Python 3.8+, `pip install -r eval/requirements.txt` (matplotlib serve solo per i grafici, pytest per i test).
Tutti i comandi si lanciano **dalla radice del repository**, con l'API di C avviata (`./start.sh`, su Windows `start.bat`).

| File | Cosa contiene |
|---|---|
| `queries.tsv` | 30 query (contratto 5): 8 keyword, 8 persona/luogo, 7 frase, 7 errore_battitura |
| `topics.tsv` | bisogno informativo di ogni query (quello che si giudica) e termini per il controllo sul corpus |
| `queries_riserva.tsv` | 1 query di riserva per tipo, se una query non ha articoli nel corpus |
| `LINEE_GUIDA_GIUDIZI.md` | cosa vale 0, 1, 2 |

## Procedura

```bash
python eval/check_queries.py      # 1. ogni query ha articoli candidati nel corpus? (non usa il motore)
python eval/pool.py               # 2. pool_A/C/D.csv in eval/pools/ + classifiche in eval/runs/
#                                    3. A, C, D compilano la colonna 'rilevanza' del proprio pool
python eval/build_qrels.py        # 4. pool giudicati -> eval/qrels.txt (segnala righe vuote o sbagliate)
python eval/evaluate.py           # 5. tabelle e grafici in eval/results/
python eval/error_analysis.py     # 6. query in cui it_boost_fuzzy peggiora rispetto a it_boost
python -m pytest eval/tests -q    #    test delle metriche
```

Se B modifica il motore dopo il pooling:
```bash
python eval/pool.py --solo-run                     # aggiorna le classifiche
python eval/pool.py --solo-nuovi eval/qrels.txt    # pool_extra_X.csv con i soli documenti nuovi da giudicare
```
`evaluate.py` avvisa se la quota di documenti giudicati nei top-10 (judged@10) scende sotto 0,95.

Altri confronti: `python eval/error_analysis.py --a base --b it`, oppure `--query q13` per una query precisa.
