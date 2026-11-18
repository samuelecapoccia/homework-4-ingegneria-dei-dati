"""Metriche di valutazione, scritte a mano per poterle spiegare all'orale.
Convenzioni come trec_eval: i documenti non giudicati contano come non rilevanti.

ranking : lista di doc_id in ordine (rank 1 per primo)
qrels_q : dict doc_id -> rilevanza (0, 1, 2) per UNA query
"""
import math


def precision_at_k(ranking, qrels_q, k=10, soglia=1):
    """Frazione dei primi k che sono rilevanti (rilevanza >= soglia).
    Si divide sempre per k, anche se il sistema ha restituito meno di k risultati."""
    rilevanti = sum(1 for d in ranking[:k] if qrels_q.get(d, 0) >= soglia)
    return rilevanti / k


def reciprocal_rank(ranking, qrels_q, k=10, soglia=1):
    """1 / posizione del primo rilevante nei primi k (0 se non ce n'e')."""
    for pos, d in enumerate(ranking[:k], start=1):
        if qrels_q.get(d, 0) >= soglia:
            return 1.0 / pos
    return 0.0


def ndcg_at_k(ranking, qrels_q, k=10):
    """nDCG@k con guadagno = rilevanza graduata (0/1/2) e sconto log2(pos + 1).
    L'ideale (IDCG) ordina TUTTI i documenti giudicati della query per rilevanza."""
    dcg = sum(qrels_q.get(d, 0) / math.log2(pos + 1) for pos, d in enumerate(ranking[:k], start=1))
    ideale = sorted(qrels_q.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(pos + 1) for pos, g in enumerate(ideale, start=1))
    return dcg / idcg if idcg > 0 else 0.0


def judged_at_k(ranking, qrels_q, k=10):
    """Quota dei primi k che ha un giudizio: se scende molto, le metriche sono sottostimate."""
    top = ranking[:k]
    return sum(1 for d in top if d in qrels_q) / len(top) if top else 1.0


def valuta_query(ranking, qrels_q, k=10, soglia=1):
    return {
        "P@10": precision_at_k(ranking, qrels_q, k, soglia),
        "MRR": reciprocal_rank(ranking, qrels_q, k, soglia),
        "nDCG@10": ndcg_at_k(ranking, qrels_q, k),
        "judged@10": judged_at_k(ranking, qrels_q, k),
    }


def p_value_randomizzazione(a, b, iterazioni=10000, seed=0):
    """Test di randomizzazione appaiato (bilaterale) sulle differenze per query.
    H0: le due configurazioni sono intercambiabili, quindi il segno di ogni
    differenza e' casuale. p = quota di permutazioni con |media| >= quella osservata."""
    import random
    diffs = [y - x for x, y in zip(a, b)]
    osservata = abs(sum(diffs) / len(diffs))
    rng = random.Random(seed)
    estreme = 0
    for _ in range(iterazioni):
        s = sum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(s / len(diffs)) >= osservata - 1e-12:
            estreme += 1
    return (estreme + 1) / (iterazioni + 1)
