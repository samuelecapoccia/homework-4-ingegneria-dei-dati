# eval/ – Valutazione (ruolo D)

Qui vanno: `queries.tsv` (id, query, tipo), gli script di pooling e di valutazione,
i pool da giudicare (`pool_A.csv`, `pool_C.csv`, `pool_D.csv`), `qrels.txt` (formato TREC) e i grafici.

Gli script chiamano l'API REST, che si avvia dalla radice del repository con `./start.sh`
(endpoint: `http://localhost:7070/api/search?q=...&config=...&k=10&page=1`).
