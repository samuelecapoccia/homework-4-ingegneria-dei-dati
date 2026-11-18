"""Analisi degli errori (ruolo D): trova le query in cui la configurazione B fa peggio
della configurazione A e mette a confronto le due top-10 con i giudizi.

Uso (dalla radice del repo, dopo evaluate.py):
    python eval/error_analysis.py                                   # it_boost vs it_boost_fuzzy, 3 query
    python eval/error_analysis.py --a base --b it --n 3
    python eval/error_analysis.py --a it_boost --b it_boost_fuzzy --query q24
"""
import argparse
import json
from pathlib import Path

from common import (CONFIGS, DEFAULT_QRELS, DEFAULT_QUERIES, DEFAULT_RESULTS, DEFAULT_RUNS,
                    load_qrels, load_queries, load_runs)
from metrics import ndcg_at_k

ETICHETTA = {2: "2", 1: "1", 0: "0", None: "?"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="it_boost", choices=CONFIGS, help="configurazione di riferimento")
    ap.add_argument("--b", default="it_boost_fuzzy", choices=CONFIGS, help="configurazione sospettata di peggiorare")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--query", help="analizza solo questa query (es. q24)")
    ap.add_argument("--qrels", default=DEFAULT_QRELS)
    ap.add_argument("--runs", default=DEFAULT_RUNS)
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--out", default=DEFAULT_RESULTS)
    args = ap.parse_args()

    queries = {q["id"]: q for q in load_queries(args.queries)}
    qrels = load_qrels(args.qrels)
    runs = load_runs(args.runs)
    docs = json.loads((Path(args.runs) / "docs.json").read_text(encoding="utf-8"))

    delta = []
    for qid in queries:
        if qid not in qrels:
            continue
        na = ndcg_at_k(runs[args.a].get(qid, []), qrels[qid])
        nb = ndcg_at_k(runs[args.b].get(qid, []), qrels[qid])
        delta.append((nb - na, qid, na, nb))
    delta.sort()

    if args.query:
        scelte = [d for d in delta if d[1] == args.query]
    else:
        scelte = [d for d in delta if d[0] < 0][: args.n]
        peggiorate = sum(1 for d in delta if d[0] < 0)
        print(f"{args.b} peggiora rispetto a {args.a} in {peggiorate} query su {len(delta)}")
    if not scelte:
        print("Nessuna query da analizzare.")
        return

    md = [f"# Analisi errori: {args.a} vs {args.b}\n",
          "Rilevanza tra parentesi quadre (2 molto, 1 parz., 0 non rilevante, ? non giudicato).\n"]
    for d, qid, na, nb in scelte:
        q = queries[qid]
        md.append(f"## {qid} — `{q['query']}` ({q['tipo']})\n")
        md.append(f"nDCG@10: {args.a} = {na:.3f}, {args.b} = {nb:.3f} (Δ {d:+.3f})\n")
        md.append(f"| # | {args.a} | {args.b} |\n|---|---|---|")
        ra, rb = runs[args.a].get(qid, []), runs[args.b].get(qid, [])
        for i in range(max(len(ra), len(rb), 1)):
            celle = []
            for r in (ra, rb):
                if i < len(r):
                    rel = qrels[qid].get(r[i])
                    titolo = docs.get(r[i], {}).get("title", r[i]).replace("|", "/")
                    celle.append(f"[{ETICHETTA[rel]}] {titolo}")
                else:
                    celle.append("")
            md.append(f"| {i + 1} | {celle[0]} | {celle[1]} |")
        solo_b = [x for x in rb if x not in ra]
        md.append(f"\nEntrati con {args.b}: {len(solo_b)} documenti, di cui rilevanti (>=1): "
                  f"{sum(1 for x in solo_b if qrels[qid].get(x, 0) >= 1)}.\n")
        md.append("Causa (da scrivere a mano dopo aver guardato la tabella): ...\n")

    testo = "\n".join(md)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nome = out / f"analisi_errori_{args.a}_vs_{args.b}.md"
    nome.write_text(testo, encoding="utf-8")
    print(testo)
    print(f"\nSalvato in {nome}")


if __name__ == "__main__":
    main()
