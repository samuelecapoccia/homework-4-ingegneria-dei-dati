package it.uniroma3.wikinews.search;

import java.util.List;

public class SearchResponse {
    public String query;
    public String config;
    public int total;
    public int took_ms;
    public List<SearchResult> results;

    public SearchResponse() {}

    public SearchResponse(String query, String config, int total, int took_ms, List<SearchResult> results) {
        this.query = query;
        this.config = config;
        this.total = total;
        this.took_ms = took_ms;
        this.results = results;
    }

    public String getQuery() { return query; }
    public String getConfig() { return config; }
    public int getTotal() { return total; }
    public int getTook_ms() { return took_ms; }
    public List<SearchResult> getResults() { return results; }
}