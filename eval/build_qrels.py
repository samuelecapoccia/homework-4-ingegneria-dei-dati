"""Unisce i pool giudicati (pool_*.csv e pool_extra_*.csv) in qrels.txt (formato TREC):
    query_id 0 doc_id rilevanza

Uso (dalla radice del repo):
    python eval/build_qrels.py            # segnala righe vuote o valori non validi e le salta
    python eval/build_qrels.py --strict   # si ferma se manca anche un solo giudizio
    python eval/build_qrels.py --file pool_D.csv   # solo il tuo pool (risultati preliminari)
"""
import argparse
import sys
from pathlib import Path

from common import DEFAULT_POOLS, DEFAULT_QRELS, read_pool_csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", default=DEFAULT_POOLS)
    ap.add_argument("--out", default=DEFAULT_QRELS)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--file", default="pool_*.csv", help="quali pool leggere (default: tutti)")
    args = ap.parse_args()

    files = sorted(Path(args.pools).glob(args.file))
    if not files:
        sys.exit(f"Nessun pool_*.csv in {args.pools}")

    giudizi = {}          # (qid, doc_id) -> lista di valori (piu' di uno solo se la coppia e' in piu' file)
    problemi = []
    for path in files:
        for n, row in enumerate(read_pool_csv(path), start=2):   # riga 1 = intestazione
            qid, doc_id = row["query_id"].strip(), row["doc_id"].strip()
            val = (row.get("rilevanza") or "").strip().replace(",", ".")
            if val in {"0", "1", "2", "0.0", "1.0", "2.0"}:
                giudizi.setdefault((qid, doc_id), []).append(int(float(val)))
            else:
                problemi.append(f"{path.name} riga {n}: {qid} {doc_id} rilevanza={val!r}")

    if problemi:
        print(f"{len(problemi)} giudizi mancanti o non validi (devono essere 0, 1 o 2):")
        for p in problemi[:20]:
            print("  " + p)
        if len(problemi) > 20:
            print(f"  ... e altri {len(problemi) - 20}")
        if args.strict:
            sys.exit(1)

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for (qid, doc_id), valori in sorted(giudizi.items()):
            # stesso documento giudicato piu' volte: mediana, per pari quella bassa (scelta prudente)
            valore = sorted(valori)[(len(valori) - 1) // 2]
            f.write(f"{qid} 0 {doc_id} {valore}\n")

    n_q = len({q for q, _ in giudizi})
    dist = {v: sum(1 for vs in giudizi.values() if sorted(vs)[(len(vs) - 1) // 2] == v) for v in (0, 1, 2)}
    print(f"Scritto {args.out}: {len(giudizi)} giudizi su {n_q} query "
          f"(0: {dist[0]}, 1: {dist[1]}, 2: {dist[2]}) da {len(files)} file")


if __name__ == "__main__":
    main()
