"""
check_non_pubblicati.py - verifica se le pagine NON pubblicate sono bozze o notizie vere.

Confronta i template usati dalle pagine non pubblicate con quelli delle pubblicate:
un template frequente tra le non pubblicate e raro tra le pubblicate (es. "In sviluppo",
"Abbandonato") indica una bozza. Legge solo il JSON, senza parsing HTML: e' veloce.

Uso:
  python ingest/check_non_pubblicati.py data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz
"""
import json
import re
import sys
from collections import Counter

from parse_dump import PUBLISHED_MARKERS, iter_lines


def main():
    pub_t, non_t = Counter(), Counter()
    n_pub = n_non = n_non_no_template = 0

    for line in iter_lines(sys.argv[1]):
        rec = json.loads(line)
        cats = {re.sub(r"^Categoria:", "", c.get("name", "")).lower()
                for c in rec.get("categories") or []}
        if any("da cancellare" in c for c in cats):
            continue
        temps = {t.get("name", "") for t in rec.get("templates") or []}
        if cats & PUBLISHED_MARKERS:
            n_pub += 1
            pub_t.update(temps)
        else:
            n_non += 1
            non_t.update(temps)
            if not temps:
                n_non_no_template += 1

    print(f"pubblicate: {n_pub}   non pubblicate: {n_non}   (non pubblicate senza template: {n_non_no_template})\n")
    print(f"{'% non pubbl.':>12} {'% pubbl.':>9}  template")
    for t, c in non_t.most_common(30):
        print(f"{c / n_non:12.1%} {pub_t[t] / max(n_pub, 1):9.1%}  {t}")


if __name__ == "__main__":
    main()
