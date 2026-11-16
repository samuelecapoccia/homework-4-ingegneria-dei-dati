"""
parse_dump.py - Ruolo A: dump Wikinews (Wikimedia Enterprise HTML) -> JSONL pulito + stats.json

Output (contratto 1), una riga per articolo:
  {"id", "title", "text", "date", "categories", "url"}

Uso:
  # campione per B (si ferma dopo 100 articoli validi)
  python ingest/parse_dump.py --dump data/itwikinews-...tar.gz --out data/sample_100.jsonl --limit 100

  # dataset completo per B e D + statistiche
  python ingest/parse_dump.py --dump data/itwikinews-...tar.gz --out data/wikinews_clean.jsonl --stats data/stats.json
"""
import argparse
import hashlib
import json
import re
import statistics
import tarfile
import time
from collections import Counter

from bs4 import BeautifulSoup

try:
    import lxml  # noqa: F401  (parser HTML piu' veloce, se installato)
    HTML_PARSER = "lxml"
except ImportError:
    HTML_PARSER = "html.parser"

# ---------------------------------------------------------------- parametri
MIN_WORDS = 30  # sotto questa soglia l'articolo e' considerato vuoto/stub

# Sezioni da togliere: non sono contenuto della notizia, aggiungerebbero rumore all'indice
DROP_SECTIONS = {
    "fonti", "notizie correlate", "collegamenti esterni", "note",
    "voci correlate", "altri progetti", "bibliografia",
}
# Elementi HTML da togliere: tabelle, box, riferimenti, didascalie, elementi tecnici
DROP_SELECTORS = [
    "table", "style", "script", "figure", "sup.reference", "ol.references",
    ".mw-references-wrap", ".navbox", ".infobox", ".metadata", ".noprint",
    ".mw-editsection", ".hatnote", "meta",
]
SERVICE_TITLES = {"pagina principale"}

# Un articolo e' una notizia "vera" solo se e' stato pubblicato (o poi archiviato):
# le altre pagine sono bozze mai passate dalla revisione della comunita'
PUBLISHED_MARKERS = {"pubblicati", "articoli archiviati"}

# Categorie di manutenzione: utili per filtrare, ma non sono argomenti -> tolte dal campo categories
SERVICE_CATEGORIES = {
    "pubblicati", "articoli archiviati", "articoli da controllare per l'archiviazione",
    "articoli con box interwiki verso wikipedia", "notizie da prima pagina",
}

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
DATE_RE = re.compile(r"\b(\d{1,2})[º°]?\s+(" + "|".join(MESI) + r")\s+(\d{4})\b", re.IGNORECASE)


# ---------------------------------------------------------------- lettura in streaming
def iter_lines(dump_path):
    """Legge il tar.gz riga per riga senza estrarlo su disco ne' caricarlo in memoria."""
    with tarfile.open(dump_path, "r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            for line in tar.extractfile(member):
                line = line.strip()
                if line:
                    yield line


# ---------------------------------------------------------------- pulizia HTML
def html_to_text(html):
    """Ritorna (testo_pulito, is_redirect)."""
    soup = BeautifulSoup(html, HTML_PARSER)

    # Pagine redirect: Parsoid le marca con <link rel="mw:PageProp/redirect">
    if soup.find("link", rel=lambda v: v and "mw:PageProp/redirect" in v):
        return "", True

    for sel in DROP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    for h in soup.find_all(["h2", "h3"]):
        if h.decomposed:
            continue
        if h.get_text(" ", strip=True).lower() in DROP_SECTIONS:
            section = h.find_parent("section")  # Parsoid racchiude ogni sezione in <section>
            if section is not None:
                section.decompose()
            else:  # fallback: togli tutto fino al prossimo h2
                for sib in list(h.find_next_siblings()):
                    if sib.name == "h2":
                        break
                    sib.decompose()
                h.decompose()

    text = soup.get_text(" ")
    text = " ".join(text.split())                    # spazi multipli -> uno
    text = re.sub(r"\s+([,.;:!?)\]])", r"\1", text)  # "Roma , ieri" -> "Roma, ieri"
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text, False


# ---------------------------------------------------------------- data di pubblicazione
def parse_it_date(s):
    m = DATE_RE.search(s)
    if not m:
        return None
    day, month, year = int(m.group(1)), MESI[m.group(2).lower()], int(m.group(3))
    if not (1 <= day <= 31 and 2000 <= year <= 2030):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def extract_date(categories, text, date_created):
    """
    date_modified e' la data dell'ULTIMA MODIFICA (es. un bot nel 2024): NON si usa,
    perche' una data sbagliata e' peggio di una data mancante (null, ammesso dal contratto).
    date_created e' la creazione della pagina: buona approssimazione della pubblicazione.
    Ordine di preferenza: categoria-data -> date_created -> data a inizio testo -> null.
    Ritorna (data, fonte) per poter contare in stats.json da dove arriva ogni data.
    """
    for c in categories:
        d = parse_it_date(c)
        if d and DATE_RE.fullmatch(c.strip()):
            return d, "categoria"
    if date_created:
        return date_created[:10], "date_created"
    d = parse_it_date(text[:300])
    if d:
        return d, "testo"
    return None, "mancante"


# ---------------------------------------------------------------- record -> documento
def build_doc(rec):
    """Ritorna (doc, None) se valido, (None, motivo_scarto) altrimenti."""
    ns = (rec.get("namespace") or {}).get("identifier")
    if ns not in (0, None):
        return None, "namespace_non_0"

    title = (rec.get("name") or "").strip()
    if not title:
        return None, "senza_titolo"
    if title.lower() in SERVICE_TITLES:
        return None, "pagina_di_servizio"

    categories = []
    for c in rec.get("categories") or []:
        name = c.get("name", "") if isinstance(c, dict) else str(c)
        name = re.sub(r"^(Categoria|Category):", "", name).strip()
        if name:
            categories.append(name)

    # Pagine marcate per la cancellazione: non sono notizie valide
    # (controllo prima del parsing HTML, che e' la parte lenta)
    if any("da cancellare" in c.lower() for c in categories):
        return None, "da_cancellare"
    if not any(c.lower() in PUBLISHED_MARKERS for c in categories):
        return None, "non_pubblicato"

    html = (rec.get("article_body") or {}).get("html") or ""
    if not html:
        return None, "senza_html"

    text, is_redirect = html_to_text(html)
    if is_redirect:
        return None, "redirect"
    if len(text.split()) < MIN_WORDS:
        return None, "troppo_corto"

    date, date_source = extract_date(categories, text, rec.get("date_created"))

    doc = {
        "id": str(rec.get("identifier") or title),
        "title": title,
        "text": text,
        "date": date,
        "categories": [c for c in categories
                       if c.lower() not in SERVICE_CATEGORIES and not DATE_RE.fullmatch(c)],
        "url": rec.get("url") or "https://it.wikinews.org/wiki/" + title.replace(" ", "_"),
    }
    return (doc, date_source), None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stats", help="percorso di stats.json (opzionale)")
    ap.add_argument("--limit", type=int, help="fermati dopo N articoli validi (per il campione)")
    args = ap.parse_args()

    t0 = time.time()
    discarded = Counter()
    unpublished_cats = Counter()
    unpublished_examples = []
    by_title = {}  # titolo -> (date_modified, doc, date_source)
    n_lines = 0

    for line in iter_lines(args.dump):
        n_lines += 1
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            discarded["json_non_valido"] += 1
            continue

        result, reason = build_doc(rec)
        if reason:
            discarded[reason] += 1
            if reason == "non_pubblicato":  # per poter giustificare il filtro nelle slide
                unpublished_cats.update(
                    re.sub(r"^Categoria:", "", c.get("name", "")) for c in rec.get("categories") or []
                )
                if len(unpublished_examples) < 10:
                    unpublished_examples.append(rec.get("name"))
            continue
        doc, date_source = result

        # Stesso titolo comparso piu' volte: si tiene la versione modificata per ultima
        tkey = doc["title"].lower()
        modified = rec.get("date_modified") or ""
        if tkey in by_title:
            discarded["titolo_duplicato"] += 1
            if modified <= by_title[tkey][0]:
                continue
        by_title[tkey] = (modified, doc, date_source)

        if len(by_title) % 1000 == 0:
            print(f"  {len(by_title)} articoli validi ({n_lines} righe lette)...")
        if args.limit and len(by_title) >= args.limit:
            break

    # Scrittura + duplicati di testo identico (stesso articolo con titoli diversi)
    date_sources, years, cats, lengths, seen_hashes = Counter(), Counter(), Counter(), [], set()
    with open(args.out, "w", encoding="utf-8") as out:
        for _, doc, date_source in by_title.values():
            hkey = hashlib.md5(doc["text"].encode("utf-8")).hexdigest()
            if hkey in seen_hashes:
                discarded["testo_duplicato"] += 1
                continue
            seen_hashes.add(hkey)
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            lengths.append(len(doc["text"].split()))
            date_sources[date_source] += 1
            if doc["date"]:
                years[doc["date"][:4]] += 1
            cats.update(doc["categories"])

    elapsed = round(time.time() - t0, 1)
    stats = {
        "righe_lette": n_lines,
        "articoli_validi": len(lengths),
        "scarti_per_motivo": dict(discarded.most_common()),
        "parole_media": round(statistics.mean(lengths), 1) if lengths else 0,
        "parole_mediana": statistics.median(lengths) if lengths else 0,
        "parole_min_max": [min(lengths), max(lengths)] if lengths else [0, 0],
        "fonte_della_data": dict(date_sources),
        "articoli_per_anno": dict(sorted(years.items())),
        "top_20_categorie": cats.most_common(20),
        "non_pubblicati_top_categorie": unpublished_cats.most_common(15),
        "non_pubblicati_esempi": unpublished_examples,
        "tempo_secondi": elapsed,
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if args.stats:
        with open(args.stats, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
