package it.uniroma3.wikinews.web;

import com.google.gson.GsonBuilder;
import io.javalin.Javalin;
import io.javalin.http.Context;
import io.javalin.http.staticfiles.Location;
import io.javalin.json.JavalinGson;
import it.uniroma3.wikinews.search.Indexer;
import it.uniroma3.wikinews.search.SearchResponse;
import it.uniroma3.wikinews.search.Searcher;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.store.FSDirectory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Ruolo C - Server web (Javalin).
 *
 * GET /api/search?q=...&config=...&k=10&page=1   (contratto 3)
 * GET /api/health                                (controllo rapido che il server sia su)
 * /                                              pagina web statica (cartella web/)
 *
 * Avvio: dalla cartella search/  ->  mvn compile exec:java@web
 * Se gli indici non esistono vengono costruiti al primo avvio da data/wikinews_clean.jsonl.
 */
public class WebApp {

    /** Contratto 2 visto dal server: basta una funzione con questa firma (Searcher reale o finto). */
    @FunctionalInterface
    public interface SearchFunction {
        SearchResponse search(String query, String config, int k, int page);
    }

    public static final List<String> CONFIGS = List.of("base", "it", "it_boost", "it_boost_fuzzy");
    public static final String DEFAULT_CONFIG = "it_boost";
    public static final int DEFAULT_K = 10;
    public static final int MAX_K = 100;
    public static final int MAX_DEPTH = 1000;      // page * k massimo (evita paginazioni assurde)
    public static final int MAX_QUERY_CHARS = 500;

    public static void main(String[] args) throws IOException {
        Path dataDir = Paths.get(setting("WIKINEWS_DATA", "../data")).toAbsolutePath().normalize();
        Path webDir = Paths.get(setting("WIKINEWS_WEB", "../web")).toAbsolutePath().normalize();
        int port = Integer.parseInt(setting("PORT", "7070"));

        Path baseIdx = dataDir.resolve("index_base");
        Path itIdx = dataDir.resolve("index_it");

        if (!indexExists(baseIdx) || !indexExists(itIdx)) {
            Path jsonl = dataDir.resolve("wikinews_clean.jsonl");
            if (!Files.exists(jsonl)) {
                System.err.println("ERRORE: indici assenti e file " + jsonl + " non trovato. Vedi README (passo 'Dati').");
                System.exit(1);
            }
            System.out.println("Indici non trovati: li costruisco da " + jsonl + " (pochi secondi)...");
            new Indexer().buildAllIndices(jsonl, baseIdx, itIdx);
        }

        Searcher searcher = new Searcher(baseIdx, itIdx);   // aperto una sola volta, thread-safe in lettura
        Javalin app = create(searcher::search, webDir).start(port);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            app.stop();
            try { searcher.close(); } catch (IOException ignored) { }
        }));
        System.out.println("\n>>> Wikinews Search pronto: http://localhost:" + app.port() + "/\n");
    }

    /** Crea l'app senza avviarla: usato da main() e dai test (con un Searcher finto). */
    public static Javalin create(SearchFunction searcher, Path webDir) {
        Javalin app = Javalin.create(cfg -> {
            cfg.showJavalinBanner = false;
            // disableHtmlEscaping: i tag <mark> restano leggibili nel JSON invece di <mark>
            cfg.jsonMapper(new JavalinGson(new GsonBuilder().disableHtmlEscaping().create(), false));
            if (webDir != null && Files.isDirectory(webDir)) {
                String realDir = realPath(webDir);   // Jetty rifiuta i percorsi con link simbolici
                cfg.staticFiles.add(sf -> {
                    sf.hostedPath = "/";
                    sf.directory = realDir;
                    sf.location = Location.EXTERNAL;
                });
            }
        });

        app.get("/api/health", ctx -> ctx.json(Map.of("status", "ok")));
        app.get("/api/search", ctx -> handleSearch(ctx, searcher));

        app.exception(BadRequest.class, (e, ctx) -> error(ctx, 400, e.getMessage()));
        app.exception(IllegalArgumentException.class, (e, ctx) -> error(ctx, 400, e.getMessage()));
        app.exception(Exception.class, (e, ctx) -> {
            e.printStackTrace();
            error(ctx, 500, "Errore interno durante la ricerca.");
        });
        app.error(404, ctx -> {
            if (ctx.path().startsWith("/api/")) error(ctx, 404, "Endpoint inesistente: " + ctx.path());
        });
        return app;
    }

    private static void handleSearch(Context ctx, SearchFunction searcher) {
        String q = ctx.queryParam("q");
        if (q == null || q.isBlank()) throw new BadRequest("Il parametro 'q' è obbligatorio e non può essere vuoto.");
        q = q.trim();
        if (q.length() > MAX_QUERY_CHARS) throw new BadRequest("Query troppo lunga (max " + MAX_QUERY_CHARS + " caratteri).");

        String config = ctx.queryParam("config");
        if (config == null || config.isBlank()) config = DEFAULT_CONFIG;
        if (!CONFIGS.contains(config)) {
            throw new BadRequest("Configurazione inesistente: '" + config + "'. Valori ammessi: " + CONFIGS);
        }

        int k = intParam(ctx, "k", DEFAULT_K);
        int page = intParam(ctx, "page", 1);
        if (k < 1 || k > MAX_K) throw new BadRequest("'k' deve essere tra 1 e " + MAX_K + ".");
        if (page < 1) throw new BadRequest("'page' deve essere >= 1.");
        if ((long) page * k > MAX_DEPTH) throw new BadRequest("Pagina troppo profonda: page*k deve essere <= " + MAX_DEPTH + ".");

        SearchResponse resp = searcher.search(q, config, k, page);
        ctx.json(resp);
    }

    private static int intParam(Context ctx, String name, int def) {
        String v = ctx.queryParam(name);
        if (v == null || v.isBlank()) return def;
        try {
            return Integer.parseInt(v.trim());
        } catch (NumberFormatException e) {
            throw new BadRequest("Il parametro '" + name + "' deve essere un numero intero.");
        }
    }

    private static void error(Context ctx, int status, String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("error", message);
        body.put("status", status);
        ctx.status(status).json(body);
    }

    private static String realPath(Path p) {
        try {
            return p.toRealPath().toString();
        } catch (IOException e) {
            return p.toAbsolutePath().toString();
        }
    }

    private static boolean indexExists(Path dir) {
        if (!Files.isDirectory(dir)) return false;
        try (FSDirectory d = FSDirectory.open(dir)) {
            return DirectoryReader.indexExists(d);
        } catch (IOException e) {
            return false;
        }
    }

    /** Legge prima la system property (-Dnome=...), poi la variabile d'ambiente, poi il default. */
    private static String setting(String name, String def) {
        String v = System.getProperty(name);
        if (v == null || v.isBlank()) v = System.getenv(name);
        return (v == null || v.isBlank()) ? def : v;
    }

    /** Errore dovuto ai parametri della richiesta -> HTTP 400. */
    static class BadRequest extends RuntimeException {
        BadRequest(String msg) { super(msg); }
    }
}
