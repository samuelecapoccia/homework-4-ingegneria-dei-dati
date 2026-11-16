# Wikinews Search

Motore di ricerca con interfaccia web sulle notizie in italiano di [it.wikinews.org](https://it.wikinews.org).
Homework 4 – Ingegneria dei Dati, Università Roma Tre (prof. Merialdo).

Il sistema confronta 4 configurazioni del motore (Lucene, BM25):

| Config | Analizzatore | Campi | Extra |
|---|---|---|---|
| `base` | StandardAnalyzer | testo | – |
| `it` | ItalianAnalyzer (stopword + stemming) | testo | – |
| `it_boost` | ItalianAnalyzer | titolo (boost 2) + testo | – |
| `it_boost_fuzzy` | ItalianAnalyzer | titolo (boost 2) + testo | tolleranza agli errori di battitura |

## Requisiti

- **JDK 17+** e **Maven 3.8+** (motore e server web)
- **Python 3.10+** solo per rigenerare i dati (`ingest/`) e per la valutazione (`eval/`, `perf/`)

## Avvio rapido

```bash
# 1. dati: metti in data/ il file wikinews_clean.jsonl (oppure generalo, vedi sotto)
# 2. avvio (compila, costruisce gli indici se mancano, avvia il server)
./start.sh            # Windows: start.bat
```

Apri **http://localhost:7070**. Il primo avvio scarica le dipendenze Maven (serve la rete);
da lì in poi funziona senza rete con `./start.sh -o`. Porta diversa: `PORT=8080 ./start.sh`.

## Struttura del repository

```
ingest/   (A) dump -> data/wikinews_clean.jsonl + data/stats.json
perf/     (A) benchmark delle latenze dell'API
search/   (B, C) progetto Maven: indicizzatore e Searcher Lucene (B), server Javalin (C)
web/      (C) pagina web: index.html, style.css, app.js
eval/     (D) query, pooling, giudizi, metriche
docs/     DECISIONI.md: scelte progettuali di ciascun ruolo
data/     dump, JSONL e indici (escluso da git, si rigenera)
```

## Dati: dal dump al JSONL

```bash
mkdir -p data
curl -L -o data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz \
  https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz
pip install -r ingest/requirements.txt
python ingest/parse_dump.py --dump data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz \
  --out data/wikinews_clean.jsonl --stats data/stats.json
```

Circa 6 minuti; risultato: 10.914 articoli. Formato di ogni riga:
`{"id", "title", "text", "date": "YYYY-MM-DD" | null, "categories": [...], "url"}`.

## Indici

`./start.sh` crea `data/index_base` e `data/index_it` automaticamente se non esistono (pochi secondi).
Per ricostruirli a mano (ad esempio dopo aver rigenerato il JSONL) e lanciare i test di B:

```bash
cd search && mvn compile exec:java -Dexec.args="../data/wikinews_clean.jsonl --reindex"
```

## API REST

`GET /api/search?q=...&config=...&k=10&page=1`

| Parametro | Obbligatorio | Default | Vincoli |
|---|---|---|---|
| `q` | sì | – | non vuota, max 500 caratteri; `"..."` per cercare una frase |
| `config` | no | `it_boost` | `base`, `it`, `it_boost`, `it_boost_fuzzy` |
| `k` | no | 10 | 1–100 |
| `page` | no | 1 | ≥ 1, con `page × k ≤ 1000` |

Esempio:

```bash
curl "http://localhost:7070/api/search?q=terremoto%20abruzzo&config=it_boost&k=3"
```

```json
{"query": "terremoto abruzzo", "config": "it_boost", "total": 235, "took_ms": 12,
 "results": [{"rank": 1, "id": "...", "title": "...", "snippet": "... <mark>terremoto</mark> ...",
              "date": "2009-04-06", "url": "https://it.wikinews.org/wiki/...", "score": 9.87}]}
```

Lo snippet è testo semplice con i termini trovati tra `<mark>` e `</mark>`.
Errori: `400` per parametri non validi, `404` per endpoint inesistente, `500` per errore interno,
sempre con corpo `{"error": "messaggio", "status": codice}`. `GET /api/health` restituisce `{"status": "ok"}`.

## Interfaccia web

- casella di ricerca e menu per scegliere la configurazione;
- risultati con titolo cliccabile (apre l'articolo su Wikinews), data, snippet evidenziato, score;
- numero di risultati, tempo impiegato, paginazione;
- **"Confronta le 4 configurazioni"**: mostra affiancati i primi 10 risultati di ciascuna (utile nella demo);
- lo stato sta nell'URL, ad esempio `http://localhost:7070/?q=terremoto&config=it&page=2`.

## Test

```bash
cd search && mvn test                     # test dell'API (C): contratto, errori, integrazione con Lucene
cd search && mvn compile exec:java        # test di B: 5 query note, fuzzy, filtro per data
python perf/benchmark_api.py --corpus data/wikinews_clean.jsonl   # latenze (server avviato)
```

La valutazione dell'efficacia (Precision@10, MRR, nDCG@10 sulle 4 configurazioni) è in `eval/`.

## Licenza dei contenuti

I testi provengono da Wikinews in italiano (dump del 20/03/2025) e sono distribuiti con licenza
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.it). L'attribuzione è visibile nel footer
dell'interfaccia e ogni risultato rimanda all'articolo originale.

## Gruppo

A – Dati · B – Indice e ricerca · C – Web e infrastruttura · D – Test e valutazione
