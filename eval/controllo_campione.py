"""Controllo a campione, alla cieca, dei giudizi del giudice LLM (ruolo D).

Sceglie a caso N righe per query (seed fisso). Per ognuna mostra query, bisogno informativo, titolo ed estratto
SENZA il giudizio dell'LLM, chiede il tuo valore (0/1/2) e solo dopo mostra quello dell'LLM.
Alla fine calcola accordo e kappa di Cohen e salva il confronto in eval/giudizi_llm/controllo_<giudice>.csv.
Nei disaccordi vale il tuo giudizio, che viene scritto in pool_D.csv.

Uso (dalla radice del repo):
    python eval/controllo_campione.py            # 2 righe per query = 20 righe
    python eval/controllo_campione.py --n 1      # 1 riga per query = 10 righe
    python eval/controllo_campione.py --pool eval/pools/pool_A.csv   # controllo di A (salva controllo_A.csv)
"""
import argparse
import csv
import random
import textwrap
from collections import Counter
from pathlib import Path

from common import EVAL_DIR, POOL_COLUMNS, read_pool_csv


def kappa_cohen(a, b):
    """Accordo oltre il caso: (accordo osservato - atteso) / (1 - atteso)."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(a) | set(b))
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def chiedi_valore():
    while True:
        v = input("  Il tuo giudizio (0/1/2): ").strip()
        if v in {"0", "1", "2"}:
            return v
        print("  Scrivi solo 0, 1 o 2.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=EVAL_DIR / "pools" / "pool_D.csv")
    ap.add_argument("--n", type=int, default=2, help="righe per query")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    pool = read_pool_csv(args.pool)
    per_query = {}
    for row in pool:
        per_query.setdefault(row["query_id"], []).append(row)
    rng = random.Random(args.seed)
    campione = [r for qid in sorted(per_query) for r in rng.sample(per_query[qid], min(args.n, len(per_query[qid])))]

    print(f"Controllo alla cieca di {len(campione)} righe ({args.n} per query). Per ogni riga decidi tu, poi vedi l'LLM.\n")
    umano, llm, confronto = [], [], []
    for i, r in enumerate(campione, start=1):
        print(f"[{i}/{len(campione)}] {r['query_id']}  query: {r['query']}")
        print(textwrap.fill("Bisogno: " + r["bisogno_informativo"], 110, initial_indent="  ", subsequent_indent="  "))
        print(f"  Titolo: {r['titolo']}  ({r['data']})")
        print(textwrap.fill("Estratto: " + r["estratto"], 110, initial_indent="  ", subsequent_indent="  "))
        print(f"  URL: {r['url']}")
        v = chiedi_valore()
        l = r["rilevanza"].strip()
        esito = "D'ACCORDO" if v == l else "DISACCORDO"
        print(f"  LLM: {l}  ({r.get('motivo', '')})  -> {esito}\n")
        umano.append(v)
        llm.append(l)
        confronto.append({"query_id": r["query_id"], "doc_id": r["doc_id"], "umano": v, "llm": l})
        if v != l:                       # vale il giudizio umano
            r["motivo"] = f"{r.get('motivo', '')} [corretto da D: LLM aveva {l}]".strip()
            r["rilevanza"] = v

    n = len(umano)
    accordi = sum(x == y for x, y in zip(umano, llm))
    k = kappa_cohen(umano, llm)
    giudice = Path(args.pool).stem.replace("pool_", "")      # A, C o D
    out = EVAL_DIR / "giudizi_llm" / f"controllo_{giudice}.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "doc_id", "umano", "llm"], delimiter=";")
        w.writeheader()
        w.writerows(confronto)
    with open(args.pool, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POOL_COLUMNS + ["motivo"], delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(pool)

    frase = (f"{giudice} ha rigiudicato alla cieca {n} righe scelte a caso ({args.n} per query, seed {args.seed}), senza vedere "
             f"il giudizio dell'LLM: accordo {accordi}/{n} ({accordi / n:.0%}), kappa di Cohen {k:.2f}. "
             f"Nei {n - accordi} casi di disaccordo vale il giudizio di {giudice} (`giudizi_llm/{out.name}`).")
    md = EVAL_DIR / "GIUDICE_LLM.md"
    testo = md.read_text(encoding="utf-8")
    segnaposto = "D ha riletto `<numero>` righe scelte a caso e non era d'accordo con il giudice su `<numero>` di queste."
    if segnaposto in testo:
        md.write_text(testo.replace(segnaposto, frase), encoding="utf-8")
        print("Aggiornato GIUDICE_LLM.md")
    print(f"\nAccordo: {accordi}/{n} ({accordi / n:.0%})   kappa di Cohen: {k:.2f}")
    print(f"Confronto salvato in {out}; disaccordi corretti in {args.pool}")
    print("\n" + frase)


if __name__ == "__main__":
    main()
