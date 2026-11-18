"""Valutazione (ruolo D): P@10, MRR, nDCG@10 per configurazione e per tipo di query,
test di significativita' fra configurazioni consecutive, tabelle e grafici.

Uso (dalla radice del repo):
    python eval/evaluate.py
    python eval/evaluate.py --soglia 2      # P@10 e MRR contando come rilevanti solo i "2"

Output in eval/results/:
    risultati.md               tabelle pronte per le slide
    per_query.csv              metrica per ogni query e configurazione (serve all'analisi errori)
    metriche_per_config.png    grafico a barre metrica x configurazione
    ndcg_per_tipo.png          grafico a barre nDCG@10 per tipo di query
"""
import argparse
import csv
from pathlib import Path

from common import (CONFIGS, DEFAULT_QRELS, DEFAULT_QUERIES, DEFAULT_RESULTS, DEFAULT_RUNS, TIPI,
                    load_qrels, load_queries, load_runs)
from metrics import p_value_randomizzazione, valuta_query

METRICHE = ["P@10", "MRR", "nDCG@10"]
# Palette categoriale validata (slot 1-4), testo in grigio scuro: leggibile anche proiettato.
COLORI = {"base": "#2a78d6", "it": "#eb6834", "it_boost": "#1baf7a", "it_boost_fuzzy": "#eda100"}
TESTO, TESTO_2, GRIGLIA = "#0b0b0b", "#52514e", "#e4e3df"


def media(xs):
    return sum(xs) / len(xs) if xs else 0.0


def tabella_md(intestazione, righe):
    out = ["| " + " | ".join(intestazione) + " |", "|" + "---|" * len(intestazione)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in righe]
    return "\n".join(out)


def grafico_barre(gruppi, valori, titolo, ylabel, path):
    """gruppi: etichette sull'asse x; valori: dict config -> lista (uno per gruppo)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib non installato: salto i grafici (pip install matplotlib)")
        return
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    n = len(CONFIGS)
    larghezza = 0.8 / n
    for i, cfg in enumerate(CONFIGS):
        xs = [g + (i - (n - 1) / 2) * larghezza for g in range(len(gruppi))]
        barre = ax.bar(xs, valori[cfg], width=larghezza, color=COLORI[cfg], label=cfg,
                       edgecolor="white", linewidth=1.5, zorder=3)
        for b, v in zip(barre, valori[cfg]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", va="bottom",
                    fontsize=7.5, color=TESTO_2)
    ax.set_xticks(range(len(gruppi)))
    ax.set_xticklabels(gruppi, color=TESTO, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(ylabel, color=TESTO_2)
    ax.set_title(titolo, color=TESTO, fontsize=12, loc="left", pad=28)
    ax.grid(axis="y", color=GRIGLIA, linewidth=0.8, zorder=0)
    for lato in ("top", "right", "left"):
        ax.spines[lato].set_visible(False)
    ax.spines["bottom"].set_color(TESTO_2)
    ax.tick_params(axis="y", colors=TESTO_2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.legend(ncol=n, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9,
              handlelength=1, handleheight=1)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qrels", default=DEFAULT_QRELS)
    ap.add_argument("--runs", default=DEFAULT_RUNS)
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--out", default=DEFAULT_RESULTS)
    ap.add_argument("--soglia", type=int, default=1, help="rilevanza minima per P@10 e MRR (default 1)")
    args = ap.parse_args()

    queries = load_queries(args.queries)
    qrels = load_qrels(args.qrels)
    runs = load_runs(args.runs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    valutate = [q for q in queries if q["id"] in qrels]
    mancanti = [q["id"] for q in queries if q["id"] not in qrels]
    if mancanti:
        print(f"ATTENZIONE: {len(mancanti)} query senza giudizi, escluse: {', '.join(mancanti)}")
    senza_rilevanti = [q["id"] for q in valutate if max(qrels[q["id"]].values()) == 0]

    # per query e configurazione
    per_query = {cfg: {} for cfg in CONFIGS}
    for cfg in CONFIGS:
        for q in valutate:
            per_query[cfg][q["id"]] = valuta_query(runs[cfg].get(q["id"], []), qrels[q["id"]],
                                                   k=10, soglia=args.soglia)
    with open(out / "per_query.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "query", "tipo", "config"] + METRICHE + ["judged@10"])
        for q in valutate:
            for cfg in CONFIGS:
                m = per_query[cfg][q["id"]]
                w.writerow([q["id"], q["query"], q["tipo"], cfg] +
                           [f"{m[x]:.4f}" for x in METRICHE + ["judged@10"]])

    def media_cfg(cfg, metrica, tipo=None):
        return media([per_query[cfg][q["id"]][metrica] for q in valutate if tipo in (None, q["tipo"])])

    # tabella 1: medie per configurazione
    t1 = [[cfg] + [f"{media_cfg(cfg, m):.3f}" for m in METRICHE + ["judged@10"]] for cfg in CONFIGS]
    # tabelle 2-3: per tipo di query
    tipi_presenti = [t for t in TIPI if any(q["tipo"] == t for q in valutate)]
    n_tipo = {t: sum(1 for q in valutate if q["tipo"] == t) for t in tipi_presenti}
    t2 = [[f"{t} ({n_tipo[t]})"] + [f"{media_cfg(c, 'nDCG@10', t):.3f}" for c in CONFIGS] for t in tipi_presenti]
    t3 = [[f"{t} ({n_tipo[t]})"] + [f"{media_cfg(c, 'P@10', t):.3f}" for c in CONFIGS] for t in tipi_presenti]
    # tabella 4: ogni configurazione contro la precedente (un gradino alla volta)
    t4 = []
    for prima, dopo in zip(CONFIGS, CONFIGS[1:]):
        for m in ["nDCG@10", "P@10"]:
            a = [per_query[prima][q["id"]][m] for q in valutate]
            b = [per_query[dopo][q["id"]][m] for q in valutate]
            vince = sum(1 for x, y in zip(a, b) if y > x + 1e-9)
            perde = sum(1 for x, y in zip(a, b) if y < x - 1e-9)
            p = p_value_randomizzazione(a, b)
            t4.append([f"{prima} → {dopo}", m, f"{media(b) - media(a):+.3f}",
                       f"{vince}/{perde}/{len(a) - vince - perde}", f"{p:.3f}" + (" *" if p < 0.05 else "")])

    n_giudizi = sum(len(qrels[q["id"]]) for q in valutate)
    md = [f"# Risultati della valutazione\n",
          f"{len(valutate)} query giudicate, {n_giudizi} "
          f"giudizi. Rilevante per P@10 e MRR: rilevanza >= {args.soglia}. "
          f"nDCG@10 usa la scala graduata 0/1/2. Documenti non giudicati = non rilevanti.\n",
          "## Medie per configurazione\n", tabella_md(["config"] + METRICHE + ["judged@10"], t1),
          "\n## nDCG@10 per tipo di query (tra parentesi il numero di query)\n",
          tabella_md(["tipo"] + CONFIGS, t2),
          "\n## P@10 per tipo di query\n", tabella_md(["tipo"] + CONFIGS, t3),
          "\n## Ogni configurazione contro la precedente\n",
          "Δ = differenza delle medie; query migliorate/peggiorate/invariate; p = test di randomizzazione "
          "appaiato, 10.000 permutazioni (* = p < 0,05).\n",
          tabella_md(["confronto", "metrica", "Δ", "migl./pegg./inv.", "p"], t4)]
    if senza_rilevanti:
        md.append(f"\nQuery senza alcun documento rilevante nel pool (nDCG = 0 per tutte le config): "
                  f"{', '.join(senza_rilevanti)}")
    poco_giudicati = [cfg for cfg in CONFIGS if media_cfg(cfg, "judged@10") < 0.95]
    if poco_giudicati:
        md.append(f"\nATTENZIONE: judged@10 < 0,95 per {', '.join(poco_giudicati)}: i run sono cambiati dopo il "
                  f"pooling. Lancia `python eval/pool.py --solo-nuovi eval/qrels.txt` e fai giudicare i pool_extra.")
    testo = "\n".join(md) + "\n"
    (out / "risultati.md").write_text(testo, encoding="utf-8")
    print(testo)

    grafico_barre(METRICHE, {c: [media_cfg(c, m) for m in METRICHE] for c in CONFIGS},
                  f"Efficacia delle 4 configurazioni ({len(valutate)} query)", "valore medio",
                  out / "metriche_per_config.png")
    grafico_barre([f"{t}\n({n_tipo[t]} query)" for t in tipi_presenti],
                  {c: [media_cfg(c, "nDCG@10", t) for t in tipi_presenti] for c in CONFIGS},
                  "nDCG@10 per tipo di query", "nDCG@10 medio", out / "ndcg_per_tipo.png")
    print(f"File in {out}/: risultati.md, per_query.csv, metriche_per_config.png, ndcg_per_tipo.png")


if __name__ == "__main__":
    main()
