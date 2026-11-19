# Risultati della valutazione

30 query giudicate, 433 giudizi. Rilevante per P@10 e MRR: rilevanza >= 1. nDCG@10 usa la scala graduata 0/1/2. Documenti non giudicati = non rilevanti.

## Medie per configurazione

| config | P@10 | MRR | nDCG@10 | judged@10 |
|---|---|---|---|---|
| base | 0.547 | 0.713 | 0.627 | 1.000 |
| it | 0.567 | 0.739 | 0.656 | 1.000 |
| it_boost | 0.567 | 0.716 | 0.653 | 1.000 |
| it_boost_fuzzy | 0.637 | 0.854 | 0.767 | 1.000 |

## nDCG@10 per tipo di query (tra parentesi il numero di query)

| tipo | base | it | it_boost | it_boost_fuzzy |
|---|---|---|---|---|
| keyword (8) | 0.702 | 0.748 | 0.489 | 0.535 |
| persona/luogo (8) | 0.752 | 0.793 | 0.938 | 0.935 |
| frase (7) | 0.908 | 0.917 | 0.937 | 0.937 |
| errore_battitura (7) | 0.117 | 0.132 | 0.232 | 0.671 |

## P@10 per tipo di query

| tipo | base | it | it_boost | it_boost_fuzzy |
|---|---|---|---|---|
| keyword (8) | 0.438 | 0.500 | 0.400 | 0.412 |
| persona/luogo (8) | 0.787 | 0.812 | 0.850 | 0.850 |
| frase (7) | 0.857 | 0.829 | 0.843 | 0.843 |
| errore_battitura (7) | 0.086 | 0.100 | 0.157 | 0.443 |

## Ogni configurazione contro la precedente

Δ = differenza delle medie; query migliorate/peggiorate/invariate; p = test di randomizzazione appaiato, 10.000 permutazioni (* = p < 0,05).

| confronto | metrica | Δ | migl./pegg./inv. | p |
|---|---|---|---|---|
| base → it | nDCG@10 | +0.029 | 11/11/8 | 0.082 |
| base → it | P@10 | +0.020 | 5/2/23 | 0.223 |
| it → it_boost | nDCG@10 | -0.002 | 16/9/5 | 0.963 |
| it → it_boost | P@10 | +0.000 | 8/5/17 | 1.000 |
| it_boost → it_boost_fuzzy | nDCG@10 | +0.114 | 11/1/18 | 0.004 * |
| it_boost → it_boost_fuzzy | P@10 | +0.070 | 5/0/25 | 0.065 |

Query senza alcun documento rilevante nel pool (nDCG = 0 per tutte le config): q30
