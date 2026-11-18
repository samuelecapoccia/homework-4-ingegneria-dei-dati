"""Funzioni condivise dagli script di valutazione (ruolo D).

Tutti i percorsi di default sono relativi alla radice del repository,
quindi gli script si lanciano dalla radice:  python eval/<script>.py
"""
import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent

# Contratto 4: nomi fissi. L'ordine e' quello "a gradini" (ogni config aggiunge una cosa).
CONFIGS = ["base", "it", "it_boost", "it_boost_fuzzy"]
# Contratto 5: tipi di query.
TIPI = ["keyword", "persona/luogo", "frase", "errore_battitura"]
GIUDICI = ["A", "C", "D"]

DEFAULT_API = "http://localhost:7070/api/search"
DEFAULT_QUERIES = EVAL_DIR / "queries.tsv"
DEFAULT_TOPICS = EVAL_DIR / "topics.tsv"
DEFAULT_CORPUS = REPO_DIR / "data" / "wikinews_clean.jsonl"
DEFAULT_RUNS = EVAL_DIR / "runs"
DEFAULT_POOLS = EVAL_DIR / "pools"
DEFAULT_QRELS = EVAL_DIR / "qrels.txt"
DEFAULT_RESULTS = EVAL_DIR / "results"


# ---------------------------------------------------------------- query e topic
def _read_tsv(path):
    """TSV letto a mano (niente modulo csv): le query di tipo 'frase'
    contengono virgolette e il modulo csv le interpreterebbe come quoting."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            rows.append(dict(zip(header, line.split("\t"))))
    return rows


def load_queries(path=DEFAULT_QUERIES):
    """Lista di dict {id, query, tipo} nell'ordine del file."""
    queries = _read_tsv(path)
    for q in queries:
        if q["tipo"] not in TIPI:
            raise ValueError(f"{q['id']}: tipo '{q['tipo']}' non previsto dal contratto 5")
    return queries


def load_topics(path=DEFAULT_TOPICS):
    """dict id -> {bisogno_informativo, termini_controllo}."""
    return {r["id"]: r for r in _read_tsv(path)}


# ---------------------------------------------------------------- API REST (contratto 3)
def search_api(api, query, config, k=10, page=1, timeout=30):
    params = urllib.parse.urlencode({"q": query, "config": config, "k": k, "page": page})
    url = f"{api}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} per q={query!r} config={config}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"API non raggiungibile su {api} ({e.reason}). "
                           f"Hai avviato il server di C (./start.sh)?") from e


# ---------------------------------------------------------------- run (formato TREC)
def save_run(path, run, tag):
    """run: dict qid -> lista di (doc_id, score) gia' in ordine di rank."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for qid, docs in run.items():
            for rank, (doc_id, score) in enumerate(docs, start=1):
                if any(c.isspace() for c in doc_id):
                    raise ValueError(f"doc_id con spazi ({doc_id!r}): rompe il formato TREC, avvisa A")
                f.write(f"{qid} Q0 {doc_id} {rank} {score:.6f} {tag}\n")


def load_run(path):
    """dict qid -> lista di doc_id ordinata per rank."""
    tmp = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 6:
                continue
            qid, _, doc_id, rank = parts[0], parts[1], parts[2], int(parts[3])
            tmp.setdefault(qid, []).append((rank, doc_id))
    return {qid: [d for _, d in sorted(lst)] for qid, lst in tmp.items()}


def load_runs(runs_dir=DEFAULT_RUNS):
    runs = {}
    for cfg in CONFIGS:
        p = Path(runs_dir) / f"{cfg}.run"
        if not p.exists():
            raise FileNotFoundError(f"Manca {p}: lancia prima python eval/pool.py")
        runs[cfg] = load_run(p)
    return runs


# ---------------------------------------------------------------- qrels (formato TREC)
def load_qrels(path=DEFAULT_QRELS):
    """dict qid -> {doc_id: rilevanza}."""
    qrels = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) != 4:
                continue
            qid, _, doc_id, rel = parts
            qrels.setdefault(qid, {})[doc_id] = int(rel)
    return qrels


# ---------------------------------------------------------------- CSV dei pool
POOL_COLUMNS = ["query_id", "query", "bisogno_informativo", "doc_id",
                "titolo", "data", "url", "estratto", "rilevanza"]


def write_pool_csv(path, rows):
    """';' + BOM UTF-8: cosi' Excel italiano lo apre gia' in colonne e con gli accenti giusti."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POOL_COLUMNS, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def read_pool_csv(path):
    """Legge un pool giudicato, qualunque sia il separatore (; , tab) e la codifica
    con cui l'ha salvato il giudice (Excel puo' salvare in cp1252)."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    first_line = text.splitlines()[0]
    delim = max([";", ",", "\t"], key=first_line.count)
    return list(csv.DictReader(io.StringIO(text), delimiter=delim))
