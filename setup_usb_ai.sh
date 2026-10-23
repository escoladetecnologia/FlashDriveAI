#!/usr/bin/env bash
# ==============================================================================
# setup_usb_ai.sh - Provisionamento Automatizado do USB AI Portátil (8 GB)
# ==============================================================================
# Uso: ./setup_usb_ai.sh [DIRETORIO_DESTINO]
# Exemplo: ./setup_usb_ai.sh /media/user/PENDRIVE
# ==============================================================================

set -euo pipefail

# Definição do diretório alvo (padrão: diretório atual ou primeiro argumento)
TARGET_DIR="${1:-.}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

echo "=================================================================="
echo "    PROVISIONADOR DE IA OFFLINE PORTÁTIL (ORÇAMENTO: 8 GB)       "
echo "=================================================================="
echo "Diretório de destino: $TARGET_DIR"
echo ""

# Função para checar espaço em disco
check_disk_space() {
    local label="$1"
    echo "--- [Espaço em Disco: $label] ---"
    df -h "$TARGET_DIR" | awk 'NR==1 || NR==2 {print "   " $0}'
    echo ""
}

# 1. Checagem inicial de dependências do host
for cmd in curl tar unzip awk grep; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "[ERRO] Ferramenta necessária '$cmd' não está instalada no host."
        exit 1
    fi
done

check_disk_space "Início do Provisionamento"

# 2. Criação rigorosa da árvore de diretórios
echo "==> Criando estrutura de diretórios em $TARGET_DIR..."
mkdir -p "$TARGET_DIR/boot_os"
mkdir -p "$TARGET_DIR/bin"
mkdir -p "$TARGET_DIR/models"
mkdir -p "$TARGET_DIR/agent"
mkdir -p "$TARGET_DIR/knowledge_base"

# Cria um arquivo de boas-vindas na base de conhecimento
cat << 'EOF' > "$TARGET_DIR/knowledge_base/sobre_sistema.txt"
SISTEMA DE IA PORTÁTIL OFFLINE (8 GB USB)
=========================================
Este pendrive contém uma instalação autossuficiente de Inteligência Artificial.
Hardware alvo: Computadores antigos/modestos x86_64 (sem GPU, 2 a 4 GB RAM).

Modelos disponíveis:
1. Llama-3.2-1B-Instruct (Q4_K_M): Ideal para conversação rápida, síntese e raciocínio direto.
2. Qwen2.5-1.5B-Instruct (Q4_K_M): Otimizado para lógica, código, bash e execução ReAct.

Diretórios principais:
- /bin: Binários estáticos do llama.cpp para Linux e Windows.
- /models: Modelos GGUF quantizados.
- /agent: Código do Agente ReAct (Python Standard Library puro).
- /knowledge_base: Pasta para seus documentos de consulta RAG local.
EOF

echo "✓ Estrutura de diretórios criada com sucesso."
echo ""

# 3. Download dos Binários Portáteis do llama.cpp
# Usamos a release estável b4500 (compatível com CPUs x86_64 com SSE4/AVX básico)
echo "==> [1/3] Obtendo binários estáticos do llama.cpp..."
BIN_DIR="$TARGET_DIR/bin"
LLAMA_TAG="b4500"

# 3.1 Binário Linux (Ubuntu/Debian x86_64 glibc compatível / estático)
if [ ! -f "$BIN_DIR/llama-server" ] || [ ! -f "$BIN_DIR/llama-cli" ]; then
    echo "    Baixando llama.cpp para Linux ($LLAMA_TAG)..."
    TMP_LINUX_ZIP="/tmp/llama_linux_${LLAMA_TAG}.zip"
    curl -L --retry 3 -C - \
        "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_TAG}/llama-${LLAMA_TAG}-bin-ubuntu-x64.zip" \
        -o "$TMP_LINUX_ZIP"
    
    echo "    Extraindo binários Linux..."
    unzip -q -o "$TMP_LINUX_ZIP" "build/bin/llama-cli" "build/bin/llama-server" -d "/tmp/llama_extract_linux" || \
    unzip -q -o "$TMP_LINUX_ZIP" "llama-cli" "llama-server" -d "/tmp/llama_extract_linux" 2>/dev/null || true

    find /tmp/llama_extract_linux -type f \( -name "llama-cli" -o -name "llama-server" -o -name "lib*.so*" \) \
        -exec cp {} "$BIN_DIR/" \;
    
    chmod +x "$BIN_DIR/llama-cli" "$BIN_DIR/llama-server" 2>/dev/null || true
    rm -rf "/tmp/llama_extract_linux" "$TMP_LINUX_ZIP"
    echo "    ✓ Binários Linux instalados em $BIN_DIR"
else
    echo "    ✓ Binários Linux já presentes."
fi

# 3.2 Binário Windows (.exe para execução portátil sem boot)
if [ ! -f "$BIN_DIR/llama-server.exe" ] || [ ! -f "$BIN_DIR/llama-cli.exe" ]; then
    echo "    Baixando llama.cpp para Windows ($LLAMA_TAG - AVX x64)..."
    TMP_WIN_ZIP="/tmp/llama_win_${LLAMA_TAG}.zip"
    curl -L --retry 3 -C - \
        "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_TAG}/llama-${LLAMA_TAG}-bin-win-avx-x64.zip" \
        -o "$TMP_WIN_ZIP"

    echo "    Extraindo binários Windows..."
    unzip -q -o "$TMP_WIN_ZIP" -d "/tmp/llama_extract_win"
    find /tmp/llama_extract_win -type f \( -name "*.exe" -o -name "*.dll" \) \
        -exec cp {} "$BIN_DIR/" \;
    rm -rf "/tmp/llama_extract_win" "$TMP_WIN_ZIP"
    echo "    ✓ Binários Windows instalados em $BIN_DIR"
else
    echo "    ✓ Binários Windows já presentes."
fi

check_disk_space "Após Binários"

# 4. Download dos Modelos GGUF Quantizados
MODELS_DIR="$TARGET_DIR/models"

# Modelo 1: Llama-3.2-1B-Instruct-Q4_K_M (~800 MB)
LLAMA_FILE="$MODELS_DIR/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
if [ ! -f "$LLAMA_FILE" ]; then
    echo "==> [2/3] Baixando Modelo 1: Llama-3.2-1B-Instruct-Q4_K_M (~800 MB)..."
    curl -L --progress-bar --retry 5 -C - \
        "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf" \
        -o "$LLAMA_FILE"
    echo "    ✓ Llama-3.2-1B baixado com sucesso."
else
    echo "==> [2/3] Modelo 1 já existe: $LLAMA_FILE"
fi

check_disk_space "Após Modelo 1"

# Modelo 2: Qwen2.5-1.5B-Instruct-Q4_K_M (~1.1 GB)
QWEN_FILE="$MODELS_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
if [ ! -f "$QWEN_FILE" ]; then
    echo "==> [3/3] Baixando Modelo 2: Qwen2.5-1.5B-Instruct-Q4_K_M (~1.1 GB)..."
    curl -L --progress-bar --retry 5 -C - \
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf" \
        -o "$QWEN_FILE"
    echo "    ✓ Qwen2.5-1.5B baixado com sucesso."
else
    echo "==> [3/3] Modelo 2 já existe: $QWEN_FILE"
fi

check_disk_space "Final do Provisionamento"

echo "=================================================================="
echo "    PROVISIONAMENTO CONCLUÍDO COM SUCESSO!                       "
echo "=================================================================="
echo "Árvore de arquivos gerada:"
ls -lh "$TARGET_DIR/bin" 2>/dev/null || true
ls -lh "$TARGET_DIR/models" 2>/dev/null || true
echo "Para executar o Agente:"
echo "  No Linux:   cd $TARGET_DIR && ./start_agent.sh"
echo "  No Windows: Conecte o pendrive e execute start_agent.bat"
echo "=================================================================="
