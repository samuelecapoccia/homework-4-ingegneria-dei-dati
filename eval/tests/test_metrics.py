"""Unit test delle metriche su casi calcolati a mano.
Uso (dalla radice del repo):  python -m pytest eval/tests -q
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from metrics import judged_at_k, ndcg_at_k, precision_at_k, reciprocal_rank, p_value_randomizzazione  # noqa: E402

QRELS = {"d1": 2, "d2": 0, "d3": 1, "d4": 2}


def test_precision_divide_sempre_per_k():
    # rilevanti (>=1) tra i primi 10: d1, d3 -> 2/10, anche se il run ha solo 3 documenti
    assert precision_at_k(["d1", "d2", "d3"], QRELS) == pytest.approx(0.2)


def test_precision_soglia_2():
    assert precision_at_k(["d1", "d2", "d3"], QRELS, soglia=2) == pytest.approx(0.1)


def test_reciprocal_rank():
    assert reciprocal_rank(["d2", "x", "d3"], QRELS) == pytest.approx(1 / 3)
    assert reciprocal_rank(["d2", "x"], QRELS) == 0.0


def test_non_giudicati_sono_non_rilevanti():
    assert precision_at_k(["x", "y"], QRELS) == 0.0
    assert judged_at_k(["d1", "x"], QRELS) == pytest.approx(0.5)


def test_ndcg_calcolato_a_mano():
    # run: d2(0), d1(2), d3(1) -> DCG = 0/log2(2) + 2/log2(3) + 1/log2(4)
    dcg = 2 / math.log2(3) + 1 / 2
    # ideale: 2, 2, 1, 0 -> 2/1 + 2/log2(3) + 1/2
    idcg = 2 + 2 / math.log2(3) + 1 / 2
    assert ndcg_at_k(["d2", "d1", "d3"], QRELS) == pytest.approx(dcg / idcg)


def test_ndcg_perfetto_e_vuoto():
    assert ndcg_at_k(["d1", "d4", "d3", "d2"], QRELS) == pytest.approx(1.0)
    assert ndcg_at_k(["d1"], {"d1": 0}) == 0.0


def test_randomizzazione():
    a = [0.1] * 20
    assert p_value_randomizzazione(a, [0.9] * 20, iterazioni=2000) < 0.01   # differenza netta
    assert p_value_randomizzazione(a, a, iterazioni=2000) == 1.0            # nessuna differenza


def test_confronto_con_ir_measures_se_installato():
    ir = pytest.importorskip("ir_measures")
    qrels = [ir.Qrel("q", d, r) for d, r in QRELS.items()]
    run = [ir.ScoredDoc("q", d, s) for d, s in [("d2", 3.0), ("d1", 2.0), ("d3", 1.0)]]
    res = ir.calc_aggregate([ir.nDCG @ 10, ir.P @ 10, ir.RR], qrels, run)
    assert res[ir.nDCG @ 10] == pytest.approx(ndcg_at_k(["d2", "d1", "d3"], QRELS))
    assert res[ir.P @ 10] == pytest.approx(precision_at_k(["d2", "d1", "d3"], QRELS))
    assert res[ir.RR] == pytest.approx(reciprocal_rank(["d2", "d1", "d3"], QRELS))
