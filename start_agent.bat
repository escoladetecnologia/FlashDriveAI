@echo off
rem ==============================================================================
rem start_agent.bat - Inicializador Portatil para Windows (Sem necessidade de Boot)
rem ==============================================================================
rem Detecta hardware (CPU Cores, Memoria) e ajusta as variaveis de execucao.
rem ==============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ==================================================================
echo     INICIALIZANDO AMBIENTE DE IA OFFLINE (WINDOWS HOST)           
echo ==================================================================

rem 1. Verificacao de instalacao do Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO CRITICO] Python 3 nao encontrado no PATH do Windows.
    echo Instale o Python 3 ou utilize o Live USB para dar boot.
    pause
    exit /b 1
)

rem 2. Deteccao de Threads de CPU
set /a CORES=%NUMBER_OF_PROCESSORS%
set /a THREADS=%CORES%

set THREADS=%THREADS%
echo [Hardware Detectado]
echo    Processadores logicos: %CORES% ^| Threads para IA: %THREADS%

rem 3. Deteccao de Memoria RAM Livre via PowerShell
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)"') do (
    set FREE_RAM_MB=%%a
)

echo    RAM Livre estimada: %FREE_RAM_MB% MB

rem 4. Ajuste Dinamico de Contexto
if %FREE_RAM_MB% LSS 1200 (
    echo    [!] Memoria livre baixa. Ajustando contexto para 1024 tokens.
    set CTX_SIZE=1024
) else (
    echo    [*] Memoria suficiente. Contexto: 2048 tokens.
    set CTX_SIZE=2048
)

echo ------------------------------------------------------------------
echo Iniciando Agente ReAct...
echo ------------------------------------------------------------------

python "%~dp0agent\agent.py"

pause
