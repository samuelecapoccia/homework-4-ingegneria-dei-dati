package it.uniroma3.wikinews.search;

import com.google.gson.Gson;
import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.it.ItalianAnalyzer;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.*;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.search.similarities.BM25Similarity;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.apache.lucene.util.BytesRef;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

public class Indexer {

    public void buildAllIndices(Path jsonlPath, Path baseIndexDir, Path itIndexDir) throws IOException {
        System.out.println("=== INIZIO INDICIZZAZIONE DA: " + jsonlPath + " ===");
        buildSingleIndex(jsonlPath, baseIndexDir, new StandardAnalyzer(), "base (StandardAnalyzer)");
        buildSingleIndex(jsonlPath, itIndexDir, new ItalianAnalyzer(), "it (ItalianAnalyzer)");
    }

    private void buildSingleIndex(Path jsonlPath, Path indexDir, Analyzer analyzer, String label) throws IOException {
        long startTime = System.currentTimeMillis();
        Files.createDirectories(indexDir);

        IndexWriterConfig config = new IndexWriterConfig(analyzer);
        config.setOpenMode(IndexWriterConfig.OpenMode.CREATE);
        config.setSimilarity(new BM25Similarity());

        int count = 0;
        Gson gson = new Gson();

        try (Directory dir = FSDirectory.open(indexDir);
             IndexWriter writer = new IndexWriter(dir, config);
             BufferedReader reader = Files.newBufferedReader(jsonlPath, StandardCharsets.UTF_8)) {

            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                Article art = gson.fromJson(line, Article.class);
                if (art == null || art.id == null || art.title == null || art.text == null) continue;

                Document doc = new Document();
                doc.add(new StringField("id", art.id, Field.Store.YES));
                doc.add(new StringField("url", art.url != null ? art.url : "", Field.Store.YES));
                doc.add(new TextField("title", art.title, Field.Store.YES));
                doc.add(new TextField("text", art.text, Field.Store.YES));

                String dateStr = (art.date != null && !art.date.isBlank()) ? art.date : "";
                doc.add(new StoredField("date", dateStr));
                doc.add(new SortedDocValuesField("date_sort", new BytesRef(dateStr)));
                int dateInt = parseDateToInt(dateStr);
                if (dateInt > 0) {
                    doc.add(new IntPoint("date_int", dateInt));
                }

                if (art.categories != null) {
                    for (String cat : art.categories) {
                        if (cat != null && !cat.isBlank()) {
                            doc.add(new StringField("categories", cat.trim(), Field.Store.YES));
                        }
                    }
                }

                writer.addDocument(doc);
                count++;
            }
            writer.commit();
        }

        long elapsedMs = System.currentTimeMillis() - startTime;
        long sizeBytes = getDirectorySize(indexDir);
        double sizeMb = sizeBytes / (1024.0 * 1024.0);

        System.out.printf("Indice [%s] -> Documenti: %d | Tempo: %d ms | Dimensione: %.2f MB (%d bytes)%n",
                label, count, elapsedMs, sizeMb, sizeBytes);
    }

    private int parseDateToInt(String dateStr) {
        if (dateStr == null || !dateStr.matches("\\d{4}-\\d{2}-\\d{2}")) return -1;
        return Integer.parseInt(dateStr.replace("-", ""));
    }

    private long getDirectorySize(Path dir) throws IOException {
        try (Stream<Path> walk = Files.walk(dir)) {
            return walk.filter(Files::isRegularFile)
                       .mapToLong(p -> {
                           try { return Files.size(p); }
                           catch (IOException e) { return 0L; }
                       }).sum();
        }
    }
}