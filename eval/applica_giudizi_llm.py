"""Copia nel pool i giudizi del giudice LLM, prendendoli dalle sue risposte grezze (vedi GIUDICE_LLM.md).

Le risposte possono essere in formato completo (tutte le colonne del pool + motivo) oppure compatto
(query_id;doc_id;rilevanza;motivo), anche dentro blocchi ``` e con note in fondo. Le righe vengono abbinate al
pool usando (query_id, doc_id). Riempie solo le celle 'rilevanza' vuote, quindi non cancella le correzioni fatte a mano.

Uso (dalla radice del repo):
    python eval/applica_giudizi_llm.py
    python eval/applica_giudizi_llm.py --pool eval/pools/pool_D.csv --giudizi eval/giudizi_llm/*.txt
"""
import argparse
import csv
import io
import re
import sys
from pathlib import Path

from common import EVAL_DIR, POOL_COLUMNS, read_pool_csv

QID_RE = re.compile(r"^q\d+$")


def leggi_risposta(path):
    """dict (qid, doc_id) -> (rilevanza, motivo) estratto da una risposta grezza."""
    righe = Path(path).read_text(encoding="utf-8").splitlines()
    inizio = next(i for i, r in enumerate(righe) if r.strip().startswith("query_id;"))
    blocco = []
    for r in righe[inizio:]:
        if r.strip().startswith("```"):
            break
        blocco.append(r)
    giudizi = {}
    for row in csv.DictReader(io.StringIO("\n".join(blocco)), delimiter=";"):
        qid, doc = (row.get("query_id") or "").strip(), (row.get("doc_id") or "").strip()
        rel = (row.get("rilevanza") or "").strip()
        if QID_RE.match(qid) and doc and rel in {"0", "1", "2"}:   # scarta l'eventuale ultima riga troncata
            giudizi[(qid, doc)] = (rel, (row.get("motivo") or "").strip())
    return giudizi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=EVAL_DIR / "pools" / "pool_D.csv")
    ap.add_argument("--giudizi", nargs="+", default=sorted((EVAL_DIR / "giudizi_llm").glob("*.txt")))
    args = ap.parse_args()

    tutti = {}
    for f in args.giudizi:
        g = leggi_risposta(f)
        print(f"{Path(f).name}: {len(g)} giudizi validi")
        for k, v in g.items():
            if k in tutti and tutti[k][0] != v[0]:
                print(f"  ATTENZIONE: {k} giudicato in modo diverso in due risposte, tengo il primo")
            tutti.setdefault(k, v)

    pool = read_pool_csv(args.pool)
    riempite, gia_presenti, mancanti = 0, 0, []
    for row in pool:
        k = (row["query_id"].strip(), row["doc_id"].strip())
        row.setdefault("motivo", "")
        if (row.get("rilevanza") or "").strip():
            gia_presenti += 1
        elif k in tutti:
            row["rilevanza"], row["motivo"] = tutti[k]
            riempite += 1
        else:
            mancanti.append(k)
    estranei = sorted(set(tutti) - {(r["query_id"].strip(), r["doc_id"].strip()) for r in pool})

    with open(args.pool, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POOL_COLUMNS + ["motivo"], delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(pool)

    print(f"\n{args.pool}: {len(pool)} righe, riempite ora {riempite}, gia' giudicate {gia_presenti}, "
          f"senza giudizio {len(mancanti)}")
    if mancanti:
        print("  senza giudizio:", ", ".join(f"{q}/{d}" for q, d in mancanti))
    if estranei:
        print("  giudizi su documenti che non sono nel pool (ignorati):", ", ".join(f"{q}/{d}" for q, d in estranei))
    sys.exit(1 if mancanti else 0)


if __name__ == "__main__":
    main()
