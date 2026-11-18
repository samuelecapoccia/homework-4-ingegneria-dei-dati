"""
benchmark_api.py - Ruolo A: misura i tempi di risposta dell'API di ricerca (contratto 3).

Per ogni configurazione esegue le stesse query e calcola media, mediana, 95° percentile e massimo
della latenza, sia lato client (tempo totale della richiesta HTTP) sia lato server (took_ms).
Le prime query (warm-up) non vengono contate: la JVM deve ancora "scaldarsi" (compilazione JIT, cache).

Le query si prendono da:
  - queries.tsv di D, se passato con --queries (colonna "query");
  - altrimenti si generano dai titoli del corpus (2 parole a caso per titolo, seed fisso -> riproducibile).

Uso (solo libreria standard, niente da installare):
  python perf/benchmark_api.py --base-url http://localhost:7070 --corpus data/wikinews_clean.jsonl
  python perf/benchmark_api.py --base-url http://localhost:7070 --queries eval/queries.tsv
"""
import argparse
import csv
import json
import random
import re
import statistics
import time
import urllib.parse
import urllib.request

CONFIGS = ["base", "it", "it_boost", "it_boost_fuzzy"]


def queries_from_tsv(path):
    with open(path, encoding="utf-8") as f:
        return [row["query"] for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if row.get("query")]


def queries_from_corpus(path, n, seed=42):
    """Query realistiche: 2 parole significative prese dal titolo di articoli a caso."""
    with open(path, encoding="utf-8") as f:
        titles = [json.loads(line)["title"] for line in f]
    rnd = random.Random(seed)
    queries = []
    while len(queries) < n:
        words = [w for w in re.findall(r"\w+", rnd.choice(titles)) if len(w) > 3]
        if len(words) >= 2:
            queries.append(" ".join(rnd.sample(words, 2)))
    return queries


def call(base_url, query, config, k):
    params = urllib.parse.urlencode({"q": query, "config": config, "k": k, "page": 1})
    t0 = time.perf_counter()
    with urllib.request.urlopen(f"{base_url}/api/search?{params}", timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    client_ms = (time.perf_counter() - t0) * 1000
    return client_ms, body.get("took_ms"), body.get("total", 0)


def p95(values):
    return statistics.quantiles(values, n=20)[-1] if len(values) >= 2 else values[0]


def summarize(values):
    return {
        "media_ms": round(statistics.mean(values), 1),
        "mediana_ms": round(statistics.median(values), 1),
        "p95_ms": round(p95(values), 1),
        "max_ms": round(max(values), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:7070")
    ap.add_argument("--queries", help="queries.tsv di D (opzionale)")
    ap.add_argument("--corpus", default="data/wikinews_clean.jsonl")
    ap.add_argument("--n", type=int, default=100, help="numero di query se generate dal corpus")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--out", default="data/perf.json")
    args = ap.parse_args()

    queries = queries_from_tsv(args.queries) if args.queries else queries_from_corpus(args.corpus, args.n)
    print(f"{len(queries)} query, {len(CONFIGS)} configurazioni, warm-up di {args.warmup} query\n")

    # Warm-up: non misurato
    for q in queries[: args.warmup]:
        for c in CONFIGS:
            try:
                call(args.base_url, q, c, args.k)
            except Exception:
                pass

    results = {}
    for c in CONFIGS:
        client, server, zero_hits, errors = [], [], 0, 0
        for q in queries:
            try:
                ms, took, total = call(args.base_url, q, c, args.k)
            except Exception as e:
                errors += 1
                print(f"  errore [{c}] '{q}': {e}")
                continue
            client.append(ms)
            if took is not None:
                server.append(took)
            zero_hits += total == 0
        results[c] = {
            "query_eseguite": len(client),
            "errori": errors,
            "query_senza_risultati": zero_hits,
            "client": summarize(client) if client else None,
            "server_took": summarize(server) if server else None,
        }

    print(f"{'config':<16}{'media':>8}{'mediana':>9}{'p95':>8}{'max':>8}{'0 ris.':>8}{'errori':>8}   (ms, lato client)")
    for c, r in results.items():
        s = r["client"] or {}
        print(f"{c:<16}{s.get('media_ms', '-'):>8}{s.get('mediana_ms', '-'):>9}{s.get('p95_ms', '-'):>8}"
              f"{s.get('max_ms', '-'):>8}{r['query_senza_risultati']:>8}{r['errori']:>8}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"n_query": len(queries), "k": args.k, "risultati": results, "query": queries},
                  f, ensure_ascii=False, indent=2)
    print(f"\nSalvato in {args.out}")


if __name__ == "__main__":
    main()
