@echo off
title Asma3 Meny - FPL Advisor Server
cd /d "%~dp0"

:: 1. Try python in PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    python standalone_server.py
    goto :done
)

:: 2. Try py launcher
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 standalone_server.py
    goto :done
)

:: 3. Try default local AppData installations
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    "%LocalAppData%\Programs\Python\Python313\python.exe" standalone_server.py
    goto :done
)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    "%LocalAppData%\Programs\Python\Python312\python.exe" standalone_server.py
    goto :done
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" standalone_server.py
    goto :done
)
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    "%LocalAppData%\Programs\Python\Python310\python.exe" standalone_server.py
    goto :done
)

:: 4. Try standard Program Files installations
if exist "%ProgramFiles%\Python313\python.exe" (
    "%ProgramFiles%\Python313\python.exe" standalone_server.py
    goto :done
)
if exist "%ProgramFiles%\Python312\python.exe" (
    "%ProgramFiles%\Python312\python.exe" standalone_server.py
    goto :done
)
if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" standalone_server.py
    goto :done
)

echo.
echo ============================================================
echo  [!] Python is not installed or not found in system PATH.
echo.
echo  Please install Python from: https://www.python.org/downloads/
echo  IMPORTANT: Check the box "Add python.exe to PATH"
echo ============================================================
echo.
pause

:done
