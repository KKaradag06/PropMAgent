@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title PropMAgent - Lokaler KI-Immobilienassistent

echo ======================================================================
echo   PropMAgent - Ihr lokaler KI-Immobilien- ^& Vermietungsassistent
echo ======================================================================
echo.

:: 1. Python-Befehl ermitteln
set "PYTHON_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py"
    )
)

if not defined PYTHON_CMD (
    echo [FEHLER] Python wurde auf Ihrem Computer nicht gefunden!
    echo.
    echo PropMAgent benoetigt Python Version 3.10 oder neuer.
    echo.
    echo 1. Es oeffnet sich nun automatisch die Downloadseite im Browser.
    echo 2. WICHTIG: Setzen Sie ganz zu Beginn der Installation den Haken bei:
    echo    "Add python.exe to PATH"
    echo 3. Starten Sie anschliessend diese Datei erneut per Doppelklick.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. Pruefen, ob ein einsatzbereites Python existiert
set "RUNNER="
if exist "venv\Scripts\python.exe" (
    set "RUNNER=venv\Scripts\python.exe"
    echo [OK] Virtuelle Umgebung gefunden.
) else (
    :: Pruefen, ob im System-Python bereits streamlit installiert ist
    %PYTHON_CMD% -c "import streamlit" >nul 2>&1
    if !errorlevel! equ 0 (
        set "RUNNER=%PYTHON_CMD%"
        echo [OK] Vorhandene Python-Umgebung ist startbereit.
    )
)

:: Falls weder venv noch streamlit im System vorhanden ist: Einmalige Erstinstallation
if not defined RUNNER (
    echo [1/3] Erstinstallation: Richte isolierte Umgebung ein...
    %PYTHON_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo [2/3] Installiere benoetigte Komponenten...
    call venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    call venv\Scripts\python.exe -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [FEHLER] Installation der Bibliotheken fehlgeschlagen.
        pause
        exit /b 1
    )
    set "RUNNER=venv\Scripts\python.exe"
    echo [OK] Installation erfolgreich abgeschlossen!
    echo.
)

:: 3. Ollama im Hintergrund starten (falls installiert und noch nicht aktiv)
curl -s http://localhost:11434 >nul 2>&1
if !errorlevel! neq 0 (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        echo Starte lokalen Ollama-Dienst im Hintergrund...
        start "" ollama serve >nul 2>&1
        timeout /t 2 /nobreak >nul
    ) else (
        echo [Hinweis] Ollama ist nicht aktiv. Fuer KI-Briefe koennen Sie
        echo           Ollama unter https://ollama.com herunterladen.
        echo.
    )
)

:: 4. Streamlit Dashboard starten
echo.
echo ======================================================================
echo   PropMAgent wird gestartet...
echo ======================================================================
echo Das Dashboard oeffnet sich gleich automatisch im Browser!
echo Bitte lassen Sie dieses Fenster geoeffnet, solange Sie PropMAgent nutzen.
echo.

"%RUNNER%" -m streamlit run app.py

if !errorlevel! neq 0 (
    echo.
    echo [Hinweis] PropMAgent wurde beendet.
    pause
)
