#!/usr/bin/env bash
# Avvia tutto in locale con un solo comando:
#   compila search/, costruisce gli indici se mancano (pochi secondi) e apre http://localhost:7070
# Opzioni passate a Maven, es.:  ./start.sh -o   (offline, dopo il primo avvio)
#                                PORT=8080 ./start.sh
set -e
cd "$(dirname "$0")/search"
exec mvn -q compile exec:java@web "$@"
