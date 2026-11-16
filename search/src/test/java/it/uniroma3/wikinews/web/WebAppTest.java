package it.uniroma3.wikinews.web;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.javalin.Javalin;
import it.uniroma3.wikinews.search.Indexer;
import it.uniroma3.wikinews.search.SearchResponse;
import it.uniroma3.wikinews.search.SearchResult;
import it.uniroma3.wikinews.search.Searcher;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Test dell'API REST (contratto 3).
 * 1) Con un Searcher FINTO: verificano formato della risposta e gestione degli errori, senza indici.
 * 2) Con un Searcher REALE su un mini-indice di 3 documenti: verificano l'integrazione con Lucene.
 */
class WebAppTest {

    private final HttpClient http = HttpClient.newHttpClient();
    private Javalin app;

    @AfterEach
    void stop() {
        if (app != null) app.stop();
    }

    private static final WebApp.SearchFunction FAKE = (q, config, k, page) ->
            new SearchResponse(q, config, 1, 3, List.of(
                    new SearchResult((page - 1) * k + 1, "42", "Titolo di prova",
                            "testo con <mark>" + q + "</mark>", "2020-01-01",
                            "https://it.wikinews.org/wiki/Prova", 1.5f)));

    private HttpResponse<String> get(String pathAndQuery) throws Exception {
        URI uri = URI.create("http://localhost:" + app.port() + pathAndQuery);
        return http.send(HttpRequest.newBuilder(uri).GET().build(), HttpResponse.BodyHandlers.ofString());
    }

    private static String enc(String s) {
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }

    // ------------------------------------------------------------ Searcher finto

    @Test
    void rispostaValidaRispettaIlContratto() throws Exception {
        app = WebApp.create(FAKE, null).start(0);
        HttpResponse<String> r = get("/api/search?q=roma&config=it&k=10&page=2");
        assertEquals(200, r.statusCode());
        assertTrue(r.headers().firstValue("Content-Type").orElse("").startsWith("application/json"));

        JsonObject body = JsonParser.parseString(r.body()).getAsJsonObject();
        for (String f : List.of("query", "config", "total", "took_ms", "results")) {
            assertTrue(body.has(f), "manca il campo " + f);
        }
        assertEquals("roma", body.get("query").getAsString());
        assertEquals("it", body.get("config").getAsString());

        JsonObject first = body.getAsJsonArray("results").get(0).getAsJsonObject();
        for (String f : List.of("rank", "id", "title", "snippet", "date", "url", "score")) {
            assertTrue(first.has(f), "manca il campo results[]." + f);
        }
        assertEquals(11, first.get("rank").getAsInt());              // pagina 2, k=10
        assertTrue(r.body().contains("<mark>roma</mark>"));          // <mark> non escapato nel JSON
    }

    @Test
    void parametriDiDefault() throws Exception {
        app = WebApp.create(FAKE, null).start(0);
        JsonObject body = JsonParser.parseString(get("/api/search?q=roma").body()).getAsJsonObject();
        assertEquals(WebApp.DEFAULT_CONFIG, body.get("config").getAsString());
    }

    @Test
    void erroriRestituiscono400ConMessaggio() throws Exception {
        app = WebApp.create(FAKE, null).start(0);
        String[] bad = {
                "/api/search",                              // q mancante
                "/api/search?q=",                           // q vuota
                "/api/search?q=" + enc("   "),              // q solo spazi
                "/api/search?q=roma&config=inesistente",    // config sbagliata
                "/api/search?q=roma&k=abc",                 // k non numerico
                "/api/search?q=roma&k=0",
                "/api/search?q=roma&k=101",
                "/api/search?q=roma&page=0",
                "/api/search?q=roma&k=100&page=11",         // troppo profondo
                "/api/search?q=" + "a".repeat(501),         // troppo lunga
        };
        for (String url : bad) {
            HttpResponse<String> r = get(url);
            assertEquals(400, r.statusCode(), url);
            JsonObject body = JsonParser.parseString(r.body()).getAsJsonObject();
            assertFalse(body.get("error").getAsString().isBlank(), url);
        }
    }

    @Test
    void erroreInternoRestituisce500() throws Exception {
        app = WebApp.create((q, c, k, p) -> { throw new RuntimeException("indice rotto"); }, null).start(0);
        HttpResponse<String> r = get("/api/search?q=roma");
        assertEquals(500, r.statusCode());
        assertFalse(r.body().contains("indice rotto"), "i dettagli interni non devono arrivare al client");
    }

    @Test
    void endpointInesistente404() throws Exception {
        app = WebApp.create(FAKE, null).start(0);
        assertEquals(404, get("/api/xyz").statusCode());
    }

    @Test
    void servePaginaWeb(@TempDir Path web) throws Exception {
        Files.writeString(web.resolve("index.html"), "<html>ok</html>");
        app = WebApp.create(FAKE, web).start(0);
        HttpResponse<String> r = get("/");
        assertEquals(200, r.statusCode());
        assertTrue(r.body().contains("ok"));
    }

    // ------------------------------------------------------------ Searcher reale (mini-indice)

    @Test
    void integrazioneConSearcherReale(@TempDir Path dir) throws Exception {
        Path jsonl = dir.resolve("mini.jsonl");
        Files.writeString(jsonl, String.join("\n",
                "{\"id\":\"1\",\"title\":\"Terremoto in Abruzzo\",\"text\":\"Un forte terremoto ha colpito L'Aquila e l'Abruzzo nella notte.\",\"date\":\"2009-04-06\",\"categories\":[\"Italia\"],\"url\":\"https://it.wikinews.org/wiki/1\"}",
                "{\"id\":\"2\",\"title\":\"Elezioni a Roma\",\"text\":\"Si sono svolte le elezioni comunali a Roma con alta affluenza.\",\"date\":\"2016-06-05\",\"categories\":[\"Politica\"],\"url\":\"https://it.wikinews.org/wiki/2\"}",
                "{\"id\":\"3\",\"title\":\"Calcio: la Roma vince\",\"text\":\"La squadra ha vinto la partita di campionato. Nessun terremoto in classifica.\",\"date\":null,\"categories\":[],\"url\":\"https://it.wikinews.org/wiki/3\"}"
        ), StandardCharsets.UTF_8);
        new Indexer().buildAllIndices(jsonl, dir.resolve("base"), dir.resolve("it"));

        try (Searcher searcher = new Searcher(dir.resolve("base"), dir.resolve("it"))) {
            app = WebApp.create(searcher::search, null).start(0);

            for (String config : WebApp.CONFIGS) {
                HttpResponse<String> r = get("/api/search?q=terremoto&config=" + config);
                assertEquals(200, r.statusCode(), config);
                JsonObject body = JsonParser.parseString(r.body()).getAsJsonObject();
                assertTrue(body.get("total").getAsInt() >= 1, config);
                JsonArray res = body.getAsJsonArray("results");
                assertTrue(res.get(0).getAsJsonObject().get("snippet").getAsString().contains("<mark>"), config);
            }

            // con il boost sul titolo il doc 1 (terremoto nel titolo) deve essere primo
            JsonObject boosted = JsonParser.parseString(get("/api/search?q=terremoto&config=it_boost").body()).getAsJsonObject();
            assertEquals("1", boosted.getAsJsonArray("results").get(0).getAsJsonObject().get("id").getAsString());

            // errore di battitura: trovato solo dalla configurazione fuzzy
            JsonObject noFuzzy = JsonParser.parseString(get("/api/search?q=" + enc("elezzioni") + "&config=it_boost").body()).getAsJsonObject();
            JsonObject fuzzy = JsonParser.parseString(get("/api/search?q=" + enc("elezzioni") + "&config=it_boost_fuzzy").body()).getAsJsonObject();
            assertEquals(0, noFuzzy.get("total").getAsInt());
            assertEquals("2", fuzzy.getAsJsonArray("results").get(0).getAsJsonObject().get("id").getAsString());

            // query con sintassi Lucene rotta: non deve dare 500
            assertEquals(200, get("/api/search?q=" + enc("roma AND (") + "&config=it").statusCode());
        }
    }
}
