@echo off
REM Avvio su Windows: compila, costruisce gli indici se mancano, apre http://localhost:7070
cd /d "%~dp0search"
mvn -q compile exec:java@web %*
