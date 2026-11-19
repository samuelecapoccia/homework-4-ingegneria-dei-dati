# Risultati della valutazione

30 query giudicate, 433 giudizi. Rilevante per P@10 e MRR: rilevanza >= 1. nDCG@10 usa la scala graduata 0/1/2. Documenti non giudicati = non rilevanti.

## Medie per configurazione

| config | P@10 | MRR | nDCG@10 | judged@10 |
|---|---|---|---|---|
| base | 0.560 | 0.727 | 0.631 | 1.000 |
| it | 0.580 | 0.747 | 0.653 | 1.000 |
| it_boost | 0.577 | 0.721 | 0.659 | 1.000 |
| it_boost_fuzzy | 0.647 | 0.862 | 0.768 | 1.000 |

## nDCG@10 per tipo di query (tra parentesi il numero di query)

| tipo | base | it | it_boost | it_boost_fuzzy |
|---|---|---|---|---|
| keyword (8) | 0.705 | 0.740 | 0.538 | 0.579 |
| persona/luogo (8) | 0.760 | 0.793 | 0.929 | 0.926 |
| frase (7) | 0.899 | 0.898 | 0.921 | 0.921 |
| errore_battitura (7) | 0.133 | 0.147 | 0.228 | 0.649 |

## P@10 per tipo di query

| tipo | base | it | it_boost | it_boost_fuzzy |
|---|---|---|---|---|
| keyword (8) | 0.475 | 0.525 | 0.425 | 0.438 |
| persona/luogo (8) | 0.800 | 0.825 | 0.863 | 0.863 |
| frase (7) | 0.843 | 0.829 | 0.843 | 0.843 |
| errore_battitura (7) | 0.100 | 0.114 | 0.157 | 0.443 |

## Ogni configurazione contro la precedente

Δ = differenza delle medie; query migliorate/peggiorate/invariate; p = test di randomizzazione appaiato, 10.000 permutazioni (* = p < 0,05).

| confronto | metrica | Δ | migl./pegg./inv. | p |
|---|---|---|---|---|
| base → it | nDCG@10 | +0.021 | 10/13/7 | 0.106 |
| base → it | P@10 | +0.020 | 5/1/24 | 0.159 |
| it → it_boost | nDCG@10 | +0.007 | 18/8/4 | 0.884 |
| it → it_boost | P@10 | -0.003 | 8/4/18 | 1.000 |
| it_boost → it_boost_fuzzy | nDCG@10 | +0.108 | 11/1/18 | 0.008 * |
| it_boost → it_boost_fuzzy | P@10 | +0.070 | 5/0/25 | 0.065 |

Query senza alcun documento rilevante nel pool (nDCG = 0 per tutte le config): q30
