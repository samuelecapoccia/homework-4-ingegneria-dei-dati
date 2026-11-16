"""
inspect_dump.py - Ruolo A, passo 1: guardare com'e' fatto il dump PRIMA di scrivere il parser.

Stampa i file contenuti nel .tar.gz e la struttura (chiavi, tipi, valori troncati)
del primo record, piu' un pezzo dell'HTML del corpo.

Uso:
  python ingest/inspect_dump.py data/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz
  python ingest/inspect_dump.py data/...tar.gz --count     # conta anche le righe (legge tutto)
"""
import argparse
import json
import tarfile


def describe(obj, indent=0, maxlen=100):
    """Stampa ricorsivamente la struttura di un oggetto JSON."""
    pad = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                size = f" (len={len(v)})" if isinstance(v, list) else ""
                print(f"{pad}{k}: {type(v).__name__}{size}")
                describe(v, indent + 1, maxlen)
            else:
                val = repr(v)
                print(f"{pad}{k}: {type(v).__name__} = {val[:maxlen]}{'...' if len(val) > maxlen else ''}")
    elif isinstance(obj, list) and obj:
        print(f"{pad}[0]:")
        describe(obj[0], indent + 1, maxlen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--count", action="store_true", help="conta le righe di ogni file (lento)")
    args = ap.parse_args()

    first_shown = False
    with tarfile.open(args.dump, "r|gz") as tar:  # "r|gz" = lettura in streaming
        for member in tar:
            if not member.isfile():
                continue
            print(f"\n=== FILE: {member.name} ({member.size / 1e6:.1f} MB)")
            f = tar.extractfile(member)
            n = 0
            for line in f:
                if not line.strip():
                    continue
                n += 1
                if not first_shown:
                    rec = json.loads(line)
                    print("\n--- STRUTTURA DEL PRIMO RECORD ---")
                    describe(rec)
                    html = (rec.get("article_body") or {}).get("html", "")
                    print("\n--- PRIMI 2000 CARATTERI DELL'HTML ---")
                    print(html[:2000])
                    first_shown = True
                if not args.count:
                    break
            if args.count:
                print(f"righe: {n}")


if __name__ == "__main__":
    main()
