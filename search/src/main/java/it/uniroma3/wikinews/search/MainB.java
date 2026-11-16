package it.uniroma3.wikinews.search;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

public class MainB {

    public static void main(String[] args) throws Exception {
        Path jsonlPath = args.length > 0
                ? Paths.get(args[0])
                : Paths.get("..", "data", "wikinews_clean.jsonl");

        boolean forceReindex = args.length > 1 && "--reindex".equalsIgnoreCase(args[1]);

        Path baseIndexDir = Paths.get("..", "data", "index_base");
        Path itIndexDir = Paths.get("..", "data", "index_it");

        if (forceReindex || !Files.exists(baseIndexDir) || !Files.exists(itIndexDir)) {
            Indexer indexer = new Indexer();
            indexer.buildAllIndices(jsonlPath, baseIndexDir, itIndexDir);
        } else {
            System.out.println("=== Indici già presenti in ../data/ (usa '--reindex' come 2° argomento per ricrearli) ===");
        }

        try (Searcher searcher = new Searcher(baseIndexDir, itIndexDir)) {
            System.out.println("\n--- TEST FUZZY OTTIMIZZATO ('terremotto anconna') ---");
            printSummary(searcher.search("terremotto anconna", "it_boost", 5, 1));
            printSummary(searcher.search("terremotto anconna", "it_boost_fuzzy", 5, 1));

            System.out.println("\n--- TEST NICE 1: Filtro per data (2016-01-01 .. 2016-12-31) e ordinamento cronologico ---");
            SearchResponse dateFiltered = searcher.search("terremoto", "it_boost", 5, 1, "2016-01-01", "2016-12-31", true);
            for (SearchResult r : dateFiltered.results) {
                System.out.printf("   #%d [id=%s, data=%s] %s%n", r.rank, r.id, r.date, r.title);
            }

            System.out.println("\n--- TEST NICE 2: Verifica automatica su 5 Query Note (Top-5) ---");
            runKnownQueriesTest(searcher);
        }
    }

    private static void runKnownQueriesTest(Searcher searcher) {
        record KnownQuery(String query, String config, String expectedDocId, String description) {}

        List<KnownQuery> tests = List.of(
                new KnownQuery("terremoti", "it", "43981", "Stemming plurale -> Terremoto centro Italia 2016"),
                new KnownQuery("terremoto salernitano", "it_boost", "2579", "Boost sul titolo -> Terremoto nel salernitano"),
                new KnownQuery("\"Protezione Civile\"", "it_boost", "28657", "Phrase query esatta -> Privatizzazione della Protezione Civile"),
                new KnownQuery("Bollettino Coronavirus 13 Marzo 2020", "it_boost", "48517", "Notizia specifica -> Bollettino Coronavirus 13 Marzo 2020"),
                new KnownQuery("ciclone Cleoptra Sardenga", "it_boost_fuzzy", "38731", "Tolleranza typo -> Ciclone Cleopatra, in Sardegna 18 morti")
        );

        int passed = 0;
        for (KnownQuery kq : tests) {
            SearchResponse resp = searcher.search(kq.query(), kq.config(), 5, 1);
            int foundRank = -1;
            for (SearchResult r : resp.results) {
                if (kq.expectedDocId().equals(r.id)) {
                    foundRank = r.rank;
                    break;
                }
            }
            boolean ok = foundRank != -1;
            if (ok) passed++;
            System.out.printf("[%s] Query: %-38s | Config: %-14s | Atteso ID=%-6s | Trovato Rank=%s (%s)%n",
                    ok ? "PASS" : "FAIL", kq.query(), kq.config(), kq.expectedDocId(),
                    ok ? "#" + foundRank : "NON NEI TOP-5", kq.description());
        }
        System.out.printf("Risultato finale test query note: %d/%d superati.%n", passed, tests.size());
    }

    private static void printSummary(SearchResponse resp) {
        System.out.printf("Config: %-15s | Query: %-20s | Total: %d | Took: %d ms%n",
                resp.config, resp.query, resp.total, resp.took_ms);
        for (SearchResult r : resp.results) {
            System.out.printf("   #%d [id=%s, score=%.4f] %s -> %s%n",
                    r.rank, r.id, r.score, r.title, r.snippet);
        }
    }
}