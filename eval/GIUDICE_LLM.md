# Giudizi delle query di D con un LLM (LLM-as-a-judge)

Le 10 query assegnate a D (vedi `pools/assegnazione.tsv`) sono state giudicate da un modello linguistico.
Le 20 query di A e C sono state giudicate a mano.

## Come è stato fatto

- **Conversazione nuova**, fuori dal progetto di lavoro. Il giudice non sapeva nulla del sistema, delle configurazioni o dei risultati attesi, e aveva solo il pool cieco e le linee guida.
- **Input:** `pools/pool_D.csv`, in ordine casuale e senza indicazione della configurazione da cui arriva ogni documento.
- **Base del giudizio:** solo titolo, data ed estratto (l'inizio dell'articolo). Il giudice non apriva i link.
- **Modello e data:** Claude (claude.ai), modello `Opus 5.5 Extra`, 18/11/2026.
- **Due sessioni in incognito, con lo stesso prompt.** La chat in incognito non può creare file, quindi il giudice ha risposto con il CSV scritto come testo.
  - **Sessione 1:** ha ricevuto il prompt qui sotto. La risposta si è interrotta per la lunghezza massima dopo 72 righe, con 5 query complete: q03, q06, q09, q12, q15.
  - **Sessione 2:** ha ricevuto lo stesso prompt con due sole modifiche: giudicare solo q18, q21, q24, q27 e q30, e rispondere con 4 colonne (`query_id;doc_id;rilevanza;motivo`). Ha restituito 77 righe.
- **Risposte originali:** sono salvate senza modifiche in `giudizi_llm/risposta_sessione1.txt` e `risposta_sessione2.txt`.
- **Unione:** `applica_giudizi_llm.py` le copia in `pools/pool_D.csv` abbinandole per (query_id, doc_id). Il risultato sono 149 giudizi su 149 righe: 65 valgono 2, 25 valgono 1, 59 valgono 0.
- **Controllo:** `build_qrels.py --file pool_D.csv` verifica che tutti i valori siano 0, 1 o 2. D ha poi riletto un campione di righe (vedi sotto).

## Note del giudice (dalla sessione 2)

- **q18:** quattro missioni dirette alla ISS valgono 1 perché la stazione non è nominata nell'estratto. È l'effetto del giudizio fatto solo sull'estratto (vedi Limiti).
- **q21:** in due articoli su Torino 2006 l'estratto è quasi tutto menu di navigazione. Quindi in alcuni articoli la pulizia dell'HTML non ha tolto i navbox: va segnalato ad A.
- **q30:** nel pool non c'è nessun articolo sulla Brexit, quindi tutte le righe valgono 0. Nel corpus però ci sono articoli candidati (`check_queries.py` ne trova 3): nessuna configurazione li porta nei primi 10, nemmeno il fuzzy. È un fallimento di recall, da approfondire nell'analisi degli errori.

## Prompt usato (identico, copiato nella nuova chat insieme al file pool_D.csv)

```
Sei un valutatore di rilevanza per un esperimento di Information Retrieval in stile TREC.
Ti allego un file CSV (separatore ;) in cui ogni riga è una coppia (query, articolo di Wikinews in italiano).
Colonne: query_id, query, bisogno_informativo, doc_id, titolo, data, url, estratto, rilevanza.

COMPITO
Per ogni riga scrivi nella colonna "rilevanza" un valore 0, 1 o 2 che dica quanto l'articolo soddisfa il
"bisogno_informativo". Conta il bisogno informativo, non le parole della query: alcune query contengono errori di
battitura e la versione intesa è indicata tra parentesi quadre.

SCALA
2 = molto rilevante: l'articolo parla principalmente di ciò che descrive il bisogno informativo.
1 = parzialmente rilevante: il tema è presente ma secondario, oppure è citato con qualche informazione utile.
0 = non rilevante: il tema manca, è nominato solo di sfuggita, oppure si tratta di un omonimo.
Casi frequenti:
- stesso evento visto da un'altra angolazione (es. il processo dopo un naufragio) -> 2 se l'evento è il tema principale;
- nome presente solo in un ordine d'arrivo, in una classifica o in un elenco -> 1;
- pagine di servizio, elenchi o calendari senza contenuto informativo sul tema -> 0.
Nel dubbio tra due valori scegli il più basso.

REGOLE
- Giudica usando solo titolo, data ed estratto. Non aprire i link e non cercare sul web.
- Leggi e giudica tu ogni riga. Non usare regole automatiche, punteggi o confronti di parole chiave scritti in codice:
  il codice può servire solo a leggere e scrivere il file.
- Giudica ogni riga indipendentemente dalle altre e dal loro ordine. Non cercare di indovinare quale sistema ha
  prodotto il documento.
- Non modificare, riordinare o cancellare righe o colonne. Aggiungi solo una colonna finale "motivo" con una frase
  breve (al massimo 15 parole) che giustifica il valore.
- Restituisci il file completo come CSV con separatore ;, codifica UTF-8, nome pool_D.csv.
- Alla fine dimmi quante righe hai giudicato 0, 1 e 2, e quali righe (se ce ne sono) erano impossibili da giudicare.
```

## Controllo umano a campione

D ha rigiudicato alla cieca 20 righe scelte a caso (2 per query, seed 7), senza vedere il giudizio dell'LLM: accordo 18/20 (90%), kappa di Cohen 0.84. Nei 2 casi di disaccordo vale il giudizio di D (`giudizi_llm/controllo_D.csv`).

## Limiti

- Le query hanno giudici di natura diversa: una persona per quelle di A e C, un LLM per quelle di D. Il confronto tra le
  configurazioni resta equo, perché ogni query ha un solo giudice per tutte e 4 le configurazioni e il pool è cieco.
  I confronti tra tipi di query, invece, possono risentire del giudice.
- Il giudice LLM vede solo l'inizio dell'articolo: un articolo rilevante solo più avanti nel testo può essere sottostimato.
