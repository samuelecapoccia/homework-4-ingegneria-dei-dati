"""Controllo delle query SUL CORPUS (non sul motore): per ogni query conta quanti
articoli contengono i 'termini_controllo' di topics.tsv. Serve solo a scartare
query senza documenti rilevanti, senza farsi influenzare dal ranking del sistema.

Uso (dalla radice del repo):
    python eval/check_queries.py
    python eval/check_queries.py --queries eval/queries_riserva.tsv
"""
import argparse
import json

from common import DEFAULT_CORPUS, DEFAULT_QUERIES, DEFAULT_TOPICS, load_queries, load_topics

MIN_CANDIDATI = 3


def parse_controllo(spec):
    """'a|b,c' -> [['a','b'], ['c']]: ogni gruppo (virgola) deve comparire, '|' = alternative."""
    return [[alt.strip().lower() for alt in g.split("|") if alt.strip()]
            for g in spec.split(",") if g.strip()]


def matches(text, groups):
    return all(any(alt in text for alt in group) for group in groups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--topics", default=DEFAULT_TOPICS)
    args = ap.parse_args()

    queries = load_queries(args.queries)
    topics = load_topics(args.topics)
    groups = {q["id"]: parse_controllo(topics[q["id"]]["termini_controllo"]) for q in queries}
    in_titolo = {q["id"]: [] for q in queries}
    in_testo = {q["id"]: 0 for q in queries}

    n_docs = 0
    with open(args.corpus, encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            n_docs += 1
            title = doc.get("title", "").lower()
            full = title + " " + doc.get("text", "").lower()
            for qid, g in groups.items():
                if matches(full, g):
                    in_testo[qid] += 1
                    if matches(title, g):
                        in_titolo[qid].append(doc.get("title", ""))

    print(f"Corpus: {n_docs} articoli\n")
    print(f"{'id':<5}{'tipo':<18}{'nel testo':>10}{'nel titolo':>12}  query")
    deboli = []
    for q in queries:
        qid = q["id"]
        flag = "" if in_testo[qid] >= MIN_CANDIDATI else "   <-- POCHI CANDIDATI"
        print(f"{qid:<5}{q['tipo']:<18}{in_testo[qid]:>10}{len(in_titolo[qid]):>12}  {q['query']}{flag}")
        if flag:
            deboli.append(qid)
    print("\nEsempi di titoli (max 2 per query):")
    for q in queries:
        for t in in_titolo[q["id"]][:2]:
            print(f"  {q['id']}: {t}")
    if deboli:
        print(f"\nDa sostituire con una query di riserva dello stesso tipo: {', '.join(deboli)}")
    else:
        print("\nTutte le query hanno almeno", MIN_CANDIDATI, "articoli candidati: OK")


if __name__ == "__main__":
    main()
