"""Pooling (ruolo D).

Per ogni query chiama l'API con le 4 configurazioni, prende i primi k risultati,
li unisce senza duplicati, li mescola (seed fisso), nasconde la configurazione
di provenienza e divide le query fra i giudici A, C, D.

Produce:
  eval/pools/pool_A.csv, pool_C.csv, pool_D.csv   -> da giudicare (colonna 'rilevanza')
  eval/pools/assegnazione.tsv                     -> quale giudice ha quale query
  eval/runs/<config>.run                          -> le classifiche in formato TREC (servono a evaluate.py)
  eval/runs/docs.json                             -> id -> titolo/url/data (serve a error_analysis.py)

Uso (dalla radice del repo, con l'API di C avviata):
    python eval/pool.py
    python eval/pool.py --solo-run                     # rigenera solo i run (es. dopo una modifica di B)
    python eval/pool.py --solo-nuovi eval/qrels.txt    # pool_extra_X.csv con i soli documenti non ancora giudicati
Non sovrascrive pool gia' esistenti (servirebbe --forza).
"""
import argparse
import json
import random
import re
from pathlib import Path

from common import (CONFIGS, DEFAULT_API, DEFAULT_CORPUS, DEFAULT_POOLS, DEFAULT_QUERIES,
                    DEFAULT_RUNS, DEFAULT_TOPICS, GIUDICI, TIPI, load_qrels, load_queries,
                    load_topics, save_run, search_api, write_pool_csv)

ESTRATTO_CHARS = 400
TAG_RE = re.compile(r"</?mark>")


def assegna_giudici(queries, giudici):
    """Round-robin sulle query ordinate per tipo: ogni giudice riceve ~10 query
    con un mix di tutti e 4 i tipi (cosi' nessuno giudica solo i casi facili)."""
    ordinate = sorted(queries, key=lambda q: (TIPI.index(q["tipo"]), q["id"]))
    return {q["id"]: giudici[i % len(giudici)] for i, q in enumerate(ordinate)}


def carica_estratti(corpus_path):
    """Inizio dell'articolo dal JSONL di A: e' uguale per tutte le configurazioni,
    a differenza dello snippet, che (con o senza stemming) potrebbe rivelare la config."""
    estratti = {}
    with open(corpus_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            testo = " ".join(d.get("text", "").split())
            estratti[str(d["id"])] = testo[:ESTRATTO_CHARS] + ("..." if len(testo) > ESTRATTO_CHARS else "")
    return estratti


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--topics", default=DEFAULT_TOPICS)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--runs", default=DEFAULT_RUNS)
    ap.add_argument("--out", default=DEFAULT_POOLS)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--solo-run", action="store_true", help="aggiorna solo eval/runs, non i pool")
    ap.add_argument("--solo-nuovi", metavar="QRELS", help="pool_extra_X.csv con i documenti assenti da QRELS")
    ap.add_argument("--forza", action="store_true", help="sovrascrive i pool esistenti (perdi i giudizi!)")
    args = ap.parse_args()

    # protezione: rilanciare il pooling dopo aver giudicato cancellerebbe i giudizi
    if not args.solo_run and not args.forza:
        prefisso = "pool_extra_" if args.solo_nuovi else "pool_"
        esistenti = [p for p in (Path(args.out) / f"{prefisso}{g}.csv" for g in GIUDICI) if p.exists()]
        if esistenti:
            raise SystemExit(f"Esistono gia' {', '.join(p.name for p in esistenti)}: non li sovrascrivo "
                             f"(conterranno i giudizi). Usa --forza solo se sei sicuro.")

    queries = load_queries(args.queries)
    topics = load_topics(args.topics)
    runs = {cfg: {} for cfg in CONFIGS}
    docs_info = {}

    # 1) interrogazione dell'API: 30 query x 4 config
    for q in queries:
        for cfg in CONFIGS:
            resp = search_api(args.api, q["query"], cfg, k=args.k, page=1)
            risultati = resp.get("results", [])[: args.k]
            runs[cfg][q["id"]] = [(str(r["id"]), float(r.get("score", 0.0))) for r in risultati]
            for r in risultati:
                docs_info.setdefault(str(r["id"]), {
                    "title": r.get("title", ""), "url": r.get("url", ""),
                    "date": r.get("date") or "", "snippet": TAG_RE.sub("", r.get("snippet", "")),
                })
        print(f"{q['id']}  " + "  ".join(f"{c}={len(runs[c][q['id']])}" for c in CONFIGS) + f"   {q['query']}")

    runs_dir = Path(args.runs)
    for cfg in CONFIGS:
        save_run(runs_dir / f"{cfg}.run", runs[cfg], tag=cfg)
    with open(runs_dir / "docs.json", "w", encoding="utf-8") as f:
        json.dump(docs_info, f, ensure_ascii=False, indent=1)
    print(f"\nRun salvati in {runs_dir}/")
    if args.solo_run:
        return

    # 2) pool: unione senza duplicati, poi shuffle (la config di provenienza sparisce)
    gia_giudicati = load_qrels(args.solo_nuovi) if args.solo_nuovi else {}
    estratti = carica_estratti(args.corpus) if Path(args.corpus).exists() else {}
    if not estratti:
        print(f"ATTENZIONE: {args.corpus} non trovato, uso lo snippet dell'API come estratto")

    rng = random.Random(args.seed)
    assegnazione = assegna_giudici(queries, GIUDICI)
    righe = {g: [] for g in GIUDICI}
    dimensioni = []
    for q in queries:
        pool = []
        for cfg in CONFIGS:
            for doc_id, _ in runs[cfg][q["id"]]:
                if doc_id not in pool and doc_id not in gia_giudicati.get(q["id"], {}):
                    pool.append(doc_id)
        rng.shuffle(pool)
        dimensioni.append(len(pool))
        for doc_id in pool:
            info = docs_info[doc_id]
            righe[assegnazione[q["id"]]].append({
                "query_id": q["id"], "query": q["query"],
                "bisogno_informativo": topics[q["id"]]["bisogno_informativo"],
                "doc_id": doc_id, "titolo": info["title"], "data": info["date"], "url": info["url"],
                "estratto": estratti.get(doc_id, info["snippet"]), "rilevanza": "",
            })

    out = Path(args.out)
    prefisso = "pool_extra_" if args.solo_nuovi else "pool_"
    for g in GIUDICI:
        if righe[g]:
            write_pool_csv(out / f"{prefisso}{g}.csv", righe[g])
    if not args.solo_nuovi:
        with open(out / "assegnazione.tsv", "w", encoding="utf-8", newline="\n") as f:
            f.write("query_id\tgiudice\n")
            for q in queries:
                f.write(f"{q['id']}\t{assegnazione[q['id']]}\n")

    print(f"\nPool: {sum(dimensioni)} coppie query-documento, media {sum(dimensioni)/len(dimensioni):.1f} "
          f"per query (min {min(dimensioni)}, max {max(dimensioni)}; il massimo teorico e' {args.k*len(CONFIGS)})")
    for g in GIUDICI:
        nq = len({r['query_id'] for r in righe[g]})
        print(f"  giudice {g}: {nq} query, {len(righe[g])} righe -> {out / (prefisso + g + '.csv')}")


if __name__ == "__main__":
    main()
