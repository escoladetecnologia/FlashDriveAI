"""
tools.py - Ferramentas nativas do Agente ReAct (Apenas Biblioteca Padrão)
========================================================================
Desenvolvido com foco em segurança (prevenção de Path Traversal), eficiência
em I/O e restrição de tamanho de contexto para modelos de 1B a 1.5B.
"""

import os
import re
from pathlib import Path

# Obtém o caminho absoluto da pasta raiz do USB e da base de conhecimento
CURRENT_DIR = Path(__file__).resolve().parent
USB_ROOT = CURRENT_DIR.parent
KB_DIR = (USB_ROOT / "knowledge_base").resolve()

# Garante que a pasta de conhecimento existe
KB_DIR.mkdir(parents=True, exist_ok=True)


def get_kb_files() -> list:
    """Retorna lista de nomes dos arquivos presentes na base de conhecimento."""
    try:
        return [f.name for f in KB_DIR.iterdir() if f.is_file()]
    except Exception:
        return []


def _normalize_name(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return s.lower().replace(" ", "_").replace("-", "_")


def _sanitize_path(filename: str) -> Path:
    """
    Previne ataques de Path Traversal garantindo que o arquivo permaneça dentro de KB_DIR.
    """
    clean_raw = filename.strip().strip("'\"` ").replace("..", "")
    clean_name = os.path.basename(clean_raw)
    target = (KB_DIR / clean_name).resolve()
    if not str(target).startswith(str(KB_DIR)):
        raise ValueError("Acesso negado: tentativa de escape do diretório da base de conhecimento.")
    return target


def search_kb(query: str) -> str:
    """
    Busca palavras-chave nos arquivos .txt e .md dentro da pasta /knowledge_base.
    Retorna nome do arquivo, número da linha e trechos relevantes.
    """
    query = query.strip()
    if not query:
        return "Erro: Termo de busca vazio."

    terms = [re.escape(t.lower()) for t in query.split() if t.strip()]
    if not terms:
        return "Erro: Nenhum termo válido para busca."

    pattern = re.compile("|".join(terms), re.IGNORECASE)
    results = []
    total_chars = 0
    max_chars = 1200  # Evita estourar a janela de contexto de 2048 tokens

    valid_extensions = {".txt", ".md", ".log", ".csv", ".json", ".py", ".sh"}

    for root, _, files in os.walk(KB_DIR):
        for file in sorted(files):
            file_path = Path(root) / file
            if file_path.suffix.lower() not in valid_extensions:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, start=1):
                        line_stripped = line.strip()
                        if pattern.search(line_stripped):
                            rel_name = file_path.name
                            snippet = f"[{rel_name}:L{line_num}] {line_stripped}"
                            results.append(snippet)
                            total_chars += len(snippet)
                            if total_chars >= max_chars or len(results) >= 8:
                                break
            except Exception as e:
                continue
        if total_chars >= max_chars or len(results) >= 8:
            break

    if not results:
        # Se não achou ocorrências, lista os arquivos disponíveis para ajudar o modelo
        existing_files = [f.name for f in KB_DIR.iterdir() if f.is_file()]
        files_str = ", ".join(existing_files) if existing_files else "Nenhum arquivo"
        return f"Nenhuma correspondência para '{query}'. Arquivos disponíveis: {files_str}"

    return "\n".join(results)


def read_file(filename: str) -> str:
    """
    Lê o conteúdo de um arquivo de texto da pasta /knowledge_base.
    Limita a leitura a 1500 caracteres para preservar a janela de contexto de modelos 1B.
    """
    try:
        available_files = [f for f in KB_DIR.iterdir() if f.is_file()]
        if not available_files:
            return "A pasta /knowledge_base está vazia. Nenhum arquivo para ler."

        raw_name = filename.strip().strip("'\"` ")
        
        # Se o argumento for genérico ou vazio e houver apenas 1 arquivo na base, usa ele
        if len(available_files) == 1 and (not raw_name or raw_name.lower() in ("dele", "nele", "arquivo", "o arquivo", "it", "file", "este", "esse")):
            target_file = available_files[0]
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(1500)
                is_truncated = f.read(1) != ""
            truncated_notice = "\n...[conteúdo truncado para poupar memória RAM]..." if is_truncated else ""
            return f"=== Início do arquivo {target_file.name} ===\n{content}{truncated_notice}\n=== Fim ==="

        path = _sanitize_path(raw_name)
        if not path.exists():
            # 1. Busca case-insensitive direta
            matches = [f for f in available_files if f.name.lower() == path.name.lower()]
            # 2. Busca sem acentos e normalizada
            if not matches:
                norm_req = _normalize_name(path.name)
                matches = [f for f in available_files if _normalize_name(f.name) == norm_req]
            # 3. Busca desconsiderando extensão (.txt, .md)
            if not matches:
                norm_req_stem = _normalize_name(path.stem)
                matches = [f for f in available_files if _normalize_name(f.stem) == norm_req_stem]
            # 4. Busca parcial no nome
            if not matches:
                norm_req = _normalize_name(raw_name)
                matches = [f for f in available_files if norm_req in _normalize_name(f.name)]

            if matches:
                path = matches[0]
            else:
                names_list = [f.name for f in available_files]
                return f"Erro: Arquivo '{raw_name}' não encontrado. Arquivos existentes na base: {', '.join(names_list)}"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(1500)
            is_truncated = f.read(1) != ""

        truncated_notice = "\n...[conteúdo truncado para poupar memória RAM]..." if is_truncated else ""
        return f"=== Início do arquivo {path.name} ===\n{content}{truncated_notice}\n=== Fim ==="
    except Exception as e:
        return f"Erro ao ler arquivo: {str(e)}"


def write_file(param_str: str) -> str:
    """
    Salva anotações ou códigos gerados na pasta /knowledge_base.
    Aceita o formato 'nome_arquivo|conteudo' ou apenas o nome se passado de forma separada.
    """
    try:
        if "|" in param_str:
            filename, content = param_str.split("|", 1)
        else:
            return "Erro: Use o formato write_file[nome_arquivo|conteudo]."

        path = _sanitize_path(filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip())

        size = path.stat().st_size
        return f"Sucesso: Arquivo '{path.name}' salvo com sucesso ({size} bytes)."
    except Exception as e:
        return f"Erro ao escrever arquivo: {str(e)}"


def list_kb() -> str:
    """Lista todos os arquivos presentes na base de conhecimento."""
    try:
        files = [f.name for f in KB_DIR.iterdir() if f.is_file()]
        if not files:
            return "A pasta /knowledge_base está vazia."
        return "Arquivos disponíveis na base:\n- " + "\n- ".join(files)
    except Exception as e:
        return f"Erro ao listar arquivos: {str(e)}"


def execute_tool(action_name: str, action_arg: str) -> str:
    """Despacha a execução para a ferramenta correspondente."""
    action = action_name.strip().lower()
    arg = action_arg.strip()

    if action == "search_kb":
        return search_kb(arg)
    elif action == "read_file":
        return read_file(arg)
    elif action == "write_file":
        return write_file(arg)
    elif action in ("list_kb", "list_files"):
        return list_kb()
    else:
        return f"Erro: Ferramenta desconhecida '{action_name}'. Use search_kb, read_file ou write_file."
