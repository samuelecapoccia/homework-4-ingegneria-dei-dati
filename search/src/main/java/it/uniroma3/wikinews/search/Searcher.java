package it.uniroma3.wikinews.search;

import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.TokenStream;
import org.apache.lucene.analysis.it.ItalianAnalyzer;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.analysis.tokenattributes.CharTermAttribute;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.IntPoint;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.index.Term;
import org.apache.lucene.queryparser.classic.MultiFieldQueryParser;
import org.apache.lucene.queryparser.classic.ParseException;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.*;
import org.apache.lucene.search.highlight.*;
import org.apache.lucene.search.similarities.BM25Similarity;
import org.apache.lucene.store.FSDirectory;

import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

public class Searcher implements Closeable {

    private static final float TITLE_BOOST = 2.0f;
    private static final float TEXT_BOOST = 1.0f;
    private static final int SNIPPET_CHARS = 160;

    private final IndexReader baseReader;
    private final IndexReader itReader;
    private final IndexSearcher baseSearcher;
    private final IndexSearcher itSearcher;
    private final Analyzer baseAnalyzer;
    private final Analyzer itAnalyzer;

    public Searcher(Path baseIndexDir, Path itIndexDir) throws IOException {
        this.baseReader = DirectoryReader.open(FSDirectory.open(baseIndexDir));
        this.itReader = DirectoryReader.open(FSDirectory.open(itIndexDir));

        this.baseSearcher = new IndexSearcher(baseReader);
        this.baseSearcher.setSimilarity(new BM25Similarity());

        this.itSearcher = new IndexSearcher(itReader);
        this.itSearcher.setSimilarity(new BM25Similarity());

        this.baseAnalyzer = new StandardAnalyzer();
        this.itAnalyzer = new ItalianAnalyzer();
    }

    // Metodo ufficiale Contratto 2 (usato da C e D)
    public SearchResponse search(String queryStr, String config, int k, int page) {
        return search(queryStr, config, k, page, null, null, false);
    }

    // Estensione NICE: supporto a filtro per range di date (YYYY-MM-DD) e ordinamento per data
    public SearchResponse search(String queryStr, String config, int k, int page,
                                 String dateFrom, String dateTo, boolean sortByDateDesc) {
        long startTime = System.currentTimeMillis();

        if (queryStr == null || queryStr.isBlank()) {
            throw new IllegalArgumentException("La query non può essere vuota.");
        }
        if (config == null || !Set.of("base", "it", "it_boost", "it_boost_fuzzy").contains(config)) {
            throw new IllegalArgumentException("Configurazione non valida: " + config);
        }

        int safeK = Math.max(1, k);
        int safePage = Math.max(1, page);
        int startOffset = (safePage - 1) * safeK;
        int numHitsToCollect = startOffset + safeK;

        IndexSearcher activeSearcher = "base".equals(config) ? baseSearcher : itSearcher;
        Analyzer activeAnalyzer = "base".equals(config) ? baseAnalyzer : itAnalyzer;

        try {
            Query textQuery = buildQuery(queryStr.trim(), config, activeAnalyzer);
            Query finalQuery = applyDateFilter(textQuery, dateFrom, dateTo);

            int totalHits = activeSearcher.count(finalQuery);
            TopDocs topDocs;
            if (sortByDateDesc) {
                Sort sort = new Sort(new SortField("date_sort", SortField.Type.STRING, true));
                topDocs = activeSearcher.search(finalQuery, numHitsToCollect, sort);
            } else {
                topDocs = activeSearcher.search(finalQuery, numHitsToCollect);
            }

            StoredFields storedFields = activeSearcher.storedFields();
            List<SearchResult> results = new ArrayList<>();
            int endOffset = Math.min(topDocs.scoreDocs.length, startOffset + safeK);

            for (int i = startOffset; i < endOffset; i++) {
                ScoreDoc sd = topDocs.scoreDocs[i];
                Document doc = storedFields.document(sd.doc);

                String id = doc.get("id");
                String title = doc.get("title");
                String rawText = doc.get("text");
                String date = doc.get("date");
                String url = doc.get("url");
                float safeScore = Float.isNaN(sd.score) ? 0.0f : sd.score;

                String snippet = buildSnippet(textQuery, activeAnalyzer, rawText);
                results.add(new SearchResult(i + 1, id, title, snippet, date, url, safeScore));
            }

            int tookMs = (int) (System.currentTimeMillis() - startTime);
            return new SearchResponse(queryStr, config, totalHits, tookMs, results);

        } catch (Exception e) {
            throw new RuntimeException("Errore durante l'esecuzione della ricerca: " + e.getMessage(), e);
        }
    }

    private Query applyDateFilter(Query mainQuery, String dateFrom, String dateTo) {
        int minDate = parseDateToInt(dateFrom, 10101);
        int maxDate = parseDateToInt(dateTo, 99991231);
        if (minDate == 10101 && maxDate == 99991231) {
            return mainQuery;
        }
        Query dateRangeQuery = IntPoint.newRangeQuery("date_int", minDate, maxDate);
        return new BooleanQuery.Builder()
                .add(mainQuery, BooleanClause.Occur.MUST)
                .add(dateRangeQuery, BooleanClause.Occur.FILTER)
                .build();
    }

    private int parseDateToInt(String dateStr, int defaultVal) {
        if (dateStr == null || !dateStr.matches("\\d{4}-\\d{2}-\\d{2}")) return defaultVal;
        return Integer.parseInt(dateStr.replace("-", ""));
    }

    private Query buildQuery(String q, String config, Analyzer analyzer) throws ParseException, IOException {
        String safeQuery = escapeUnbalancedQuotes(q);

        switch (config) {
            case "base":
            case "it": {
                QueryParser parser = new QueryParser("text", analyzer);
                return safeParse(parser, safeQuery);
            }
            case "it_boost": {
                Map<String, Float> boosts = Map.of("title", TITLE_BOOST, "text", TEXT_BOOST);
                MultiFieldQueryParser parser = new MultiFieldQueryParser(new String[]{"title", "text"}, analyzer, boosts);
                return safeParse(parser, safeQuery);
            }
            case "it_boost_fuzzy": {
                Map<String, Float> boosts = Map.of("title", TITLE_BOOST, "text", TEXT_BOOST);
                MultiFieldQueryParser parser = new MultiFieldQueryParser(new String[]{"title", "text"}, analyzer, boosts);
                Query exactOrPhraseQuery = safeParse(parser, safeQuery);

                BooleanQuery.Builder builder = new BooleanQuery.Builder();
                builder.add(new BoostQuery(exactOrPhraseQuery, 2.0f), BooleanClause.Occur.SHOULD);

                if (!safeQuery.contains("\"")) {
                    List<String> stemmedTokens = tokenize(safeQuery, analyzer);
                    for (String token : stemmedTokens) {
                        if (token.length() >= 4) {
                            int maxEdits = (token.length() >= 7) ? 2 : 1;
                            Query fuzzyTitle = new FuzzyQuery(new Term("title", token), maxEdits, 2);
                            Query fuzzyText = new FuzzyQuery(new Term("text", token), maxEdits, 2);
                            builder.add(new BoostQuery(fuzzyTitle, TITLE_BOOST), BooleanClause.Occur.SHOULD);
                            builder.add(new BoostQuery(fuzzyText, TEXT_BOOST), BooleanClause.Occur.SHOULD);
                        }
                    }
                }
                return builder.build();
            }
            default:
                return new MatchNoDocsQuery();
        }
    }

    private Query safeParse(QueryParser parser, String q) throws ParseException {
        try {
            return parser.parse(q);
        } catch (ParseException e) {
            return parser.parse(QueryParser.escape(q));
        }
    }

    private String escapeUnbalancedQuotes(String q) {
        long quoteCount = q.chars().filter(ch -> ch == '"').count();
        if (quoteCount % 2 != 0) {
            return q.replace("\"", "");
        }
        return q;
    }

    private List<String> tokenize(String text, Analyzer analyzer) throws IOException {
        List<String> tokens = new ArrayList<>();
        try (TokenStream ts = analyzer.tokenStream("text", text)) {
            CharTermAttribute attr = ts.addAttribute(CharTermAttribute.class);
            ts.reset();
            while (ts.incrementToken()) {
                tokens.add(attr.toString());
            }
            ts.end();
        }
        return tokens;
    }

    private String buildSnippet(Query query, Analyzer analyzer, String rawText) {
        if (rawText == null || rawText.isBlank()) return "";
        String cleanText = rawText.replace("<", " ").replace(">", " ").replaceAll("\\s+", " ").trim();

        try {
            SimpleHTMLFormatter formatter = new SimpleHTMLFormatter("<mark>", "</mark>");
            QueryScorer scorer = new QueryScorer(query);
            Highlighter highlighter = new Highlighter(formatter, scorer);
            highlighter.setTextFragmenter(new SimpleSpanFragmenter(scorer, SNIPPET_CHARS));

            String fragment = highlighter.getBestFragment(analyzer, "text", cleanText);
            if (fragment != null && !fragment.isBlank()) {
                return fragment;
            }
        } catch (Exception ignored) {
        }

        if (cleanText.length() <= SNIPPET_CHARS) {
            return cleanText;
        }
        return cleanText.substring(0, SNIPPET_CHARS) + "...";
    }

    @Override
    public void close() throws IOException {
        baseReader.close();
        itReader.close();
    }
}