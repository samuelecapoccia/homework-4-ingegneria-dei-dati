package it.uniroma3.wikinews.search;

public class SearchResult {
    public int rank;
    public String id;
    public String title;
    public String snippet;
    public String date;
    public String url;
    public float score;

    public SearchResult() {}

    public SearchResult(int rank, String id, String title, String snippet, String date, String url, float score) {
        this.rank = rank;
        this.id = id;
        this.title = title;
        this.snippet = snippet;
        this.date = date;
        this.url = url;
        this.score = score;
    }

    public int getRank() { return rank; }
    public String getId() { return id; }
    public String getTitle() { return title; }
    public String getSnippet() { return snippet; }
    public String getDate() { return date; }
    public String getUrl() { return url; }
    public float getScore() { return score; }
}