@echo off
setlocal

:: --- CONFIG ---
set "FEATURE=%~1"
if "%FEATURE%"=="" (
    set "FEATURE=Add login functionality with JWT in Spring Boot"
)

set "VENV_DIR=.venv"
set "PYTHON=python"

echo -----------------------------------------------
echo 🚀 Starting multi-agent pipeline for:
echo     %FEATURE%
echo -----------------------------------------------

:: --- STEP 1: Create virtual environment if needed ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo 🛠️  Creating virtual environment...
    %PYTHON% -m venv %VENV_DIR%
)

:: --- STEP 2: Activate venv and install dependencies ---
call "%VENV_DIR%\Scripts\activate.bat"

echo 📦 Installing required packages...
pip install ag2[openai]
pip install --upgrade pip
pip install autogen requests

:: --- STEP 3: Run multi-agent interaction ---
echo ▶️  Running interaction...
%PYTHON% toolkit.py run "%FEATURE%"

:: --- STEP 4: Find latest log file ---
for /f "delims=" %%i in ('dir /b /od run_*.log') do (
    set "LATEST_LOG=%%i"
)

if not defined LATEST_LOG (
    echo ❌ No run_*.log file found!
    exit /b 1
)

echo 📝 Converting log: %LATEST_LOG%
%PYTHON% toolkit.py log2md "%LATEST_LOG%" demo_output.md

:: --- STEP 5: Extract Java classes from markdown ---
echo 💡 Extracting Java files...
%PYTHON% toolkit.py md2java demo_output.md

echo.
echo ✅ Done! Java files are in: extracted_src\
endlocal
