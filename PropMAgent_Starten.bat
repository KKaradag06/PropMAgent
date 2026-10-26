@echo off
chcp 65001 >nul
title PropMAgent - Lokaler KI-Immobilienassistent

echo ======================================================================
echo   PropMAgent - Ihr lokaler KI-Immobilien- ^& Vermietungsassistent
echo ======================================================================
echo.

:: 1. Python-Verfuegbarkeit pruefen
set PYTHON_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    )
)

if "%PYTHON_CMD%"=="" (
    echo [FEHLER] Python wurde auf Ihrem Computer nicht gefunden!
    echo.
    echo PropMAgent benoetigt Python (Version 3.10 oder neuer).
    echo.
    echo So installieren Sie Python:
    echo 1. Es oeffnet sich nun automatisch die Downloadseite in Ihrem Browser.
    echo 2. WICHTIG: Setzen Sie ganz zu Beginn der Installation unten den Haken bei:
    echo    [x] "Add python.exe to PATH"
    echo 3. Starten Sie anschliessend diese Datei erneut mit einem Doppelklick.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. Pruefen, ob die virtuelle Umgebung (venv) existiert
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Erstinstallation: Richte isolierte Umgebung ein...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo [2/3] Installiere benoetigte Komponenten (dauert beim 1. Start ca. 1-2 Minuten)...
    call venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    call venv\Scripts\python.exe -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [FEHLER] Fehler bei der Installation der Programmbibliotheken.
        pause
        exit /b 1
    )
    echo [OK] Installation erfolgreich abgeschlossen!
    echo.
) else (
    echo [OK] Python-Umgebung gefunden.
)

:: 3. Ollama Pruefung (optional im Hintergrund starten, falls verfuegbar)
curl -s http://localhost:11434 >nul 2>&1
if %errorlevel% neq 0 (
    where ollama >nul 2>&1
    if %errorlevel% equ 0 (
        echo Starte lokalen Ollama KI-Dienst im Hintergrund...
        start "" ollama serve >nul 2>&1
        timeout /t 2 /nobreak >nul
    ) else (
        echo [Hinweis] Ollama ist nicht aktiv. Fuer KI-Briefe koennen Sie Ollama
        echo           spaeter unter https://ollama.com herunterladen.
        echo.
    )
)

:: 4. Streamlit Dashboard starten
echo [3/3] Starte PropMAgent...
echo Das Web-Dashboard oeffnet sich gleich automatisch in Ihrem Standard-Browser!
echo (Hinweis: Schliessen Sie dieses schwarze Fenster erst, wenn Sie mit PropMAgent fertig sind.)
echo.

call venv\Scripts\python.exe -m streamlit run app.py

if %errorlevel% neq 0 (
    echo.
    echo [Hinweis] Die Anwendung wurde beendet.
    pause
)
