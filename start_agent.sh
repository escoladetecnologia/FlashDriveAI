#!/usr/bin/env bash
# ==============================================================================
# start_agent.sh - Inicializador Inteligente para Linux (Live USB ou Host)
# ==============================================================================
# Detecta hardware (CPU, Threads, RAM livre) e ajusta parâmetros do llama.cpp
# para prevenir estouro de memória (OOM Killer) em máquinas modestas.
# ==============================================================================

set -euo pipefail

# Garante execução a partir da raiz do pendrive
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo "    INICIALIZANDO AMBIENTE DE IA OFFLINE (LINUX)                  "
echo "=================================================================="

# 1. Verificação do interpretador Python 3
if ! command -v python3 &>/dev/null; then
    echo "[ERRO CRÍTICO] Python 3 não encontrado no sistema."
    echo "Instale o python3 ou execute pelo Live USB (Alpine/antiX)."
    exit 1
fi

# 2. Detecção e Ajuste de Threads da CPU
TOTAL_CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 2)
if [ "$TOTAL_CORES" -gt 2 ]; then
    # Em CPUs quad-core ou superiores, deixa 1 thread livre para o SO não congelar
    RECOMMENDED_THREADS=$((TOTAL_CORES - 1))
elif [ "$TOTAL_CORES" -eq 2 ]; then
    RECOMMENDED_THREADS=2
else
    RECOMMENDED_THREADS=1
fi
export THREADS="${THREADS:-$RECOMMENDED_THREADS}"

# 3. Detecção de Memória RAM Disponível
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 2097152)
AVAIL_MEM_KB=$(grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 1048576)

TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))
AVAIL_MEM_MB=$((AVAIL_MEM_KB / 1024))

echo "[Hardware Detectado]"
echo "   CPU Cores: $TOTAL_CORES | Threads configuradas para IA: $THREADS"
echo "   RAM Total: ${TOTAL_MEM_MB} MB | RAM Disponível: ${AVAIL_MEM_MB} MB"

# 4. Ajuste dinâmico de Contexto para evitar OOM (Out Of Memory)
if [ "$AVAIL_MEM_MB" -lt 1200 ]; then
    echo "   [!] Memória restrita (< 1.2 GB livre). Reduzindo contexto para 1024 tokens."
    export CTX_SIZE=1024
elif [ "$AVAIL_MEM_MB" -lt 2500 ]; then
    echo "   [*] Memória intermediária. Contexto padrão: 2048 tokens."
    export CTX_SIZE=2048
else
    echo "   [*] Memória confortável. Contexto: 2048 tokens (expansível via CTX_SIZE)."
    export CTX_SIZE="${CTX_SIZE:-2048}"
fi

# 5. Permissões de Execução nos Binários
if [ -d "$SCRIPT_DIR/bin" ]; then
    chmod +x "$SCRIPT_DIR/bin/llama-server" 2>/dev/null || true
    chmod +x "$SCRIPT_DIR/bin/llama-cli" 2>/dev/null || true
fi

echo "------------------------------------------------------------------"
echo "Lançando Agente ReAct..."
echo "------------------------------------------------------------------"

# 6. Executa o Agente Python
exec python3 "$SCRIPT_DIR/agent/agent.py"
