#!/usr/bin/env python3
"""
agent.py - Agente ReAct Ultraleve e Autônomo para Modelos 1B / 1.5B
===================================================================
100% dependente apenas da biblioteca padrão do Python 3 (urllib, json, subprocess, os).
Zero dependências externas (sem LangChain, sem pip install, 0 MB overhead).
Suporta execução em Linux e Windows (Live USB ou Host).
"""

import atexit
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Importa as ferramentas e prompts locais
from prompts import get_system_prompt, REACT_SYSTEM_PROMPT
from tools import execute_tool, get_kb_files, list_kb

# Definições de caminhos
AGENT_DIR = Path(__file__).resolve().parent
USB_ROOT = AGENT_DIR.parent
BIN_DIR = USB_ROOT / "bin"
MODELS_DIR = USB_ROOT / "models"
KB_DIR = USB_ROOT / "knowledge_base"


def find_free_port(start_port=8088):
    """Encontra uma porta TCP livre dinamicamente para evitar conflitos no host."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


# Configurações do servidor local com porta dinâmica
SERVER_HOST = "127.0.0.1"
SERVER_PORT = find_free_port()
API_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/v1/chat/completions"
HEALTH_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/health"

# Variável global para controle do processo do servidor
SERVER_PROCESS = None
SERVER_LOG_FILE = None


def cleanup_server():
    """Finaliza o processo do llama-server de forma limpa na saída."""
    global SERVER_PROCESS, SERVER_LOG_FILE
    if SERVER_PROCESS and SERVER_PROCESS.poll() is None:
        print("\n[Sistema] Encerrando servidor llama.cpp...")
        try:
            if sys.platform == "win32":
                SERVER_PROCESS.terminate()
            else:
                SERVER_PROCESS.send_signal(signal.SIGTERM)
            SERVER_PROCESS.wait(timeout=3)
        except Exception:
            SERVER_PROCESS.kill()
        print("[Sistema] Servidor finalizado com sucesso.")
    if SERVER_LOG_FILE and not SERVER_LOG_FILE.closed:
        try:
            SERVER_LOG_FILE.close()
        except Exception:
            pass


atexit.register(cleanup_server)


def find_llama_binary() -> Path:
    """Detecta o binário do llama-server conforme o sistema operacional."""
    is_windows = sys.platform == "win32"
    server_name = "llama-server.exe" if is_windows else "llama-server"

    candidate = BIN_DIR / server_name
    if candidate.exists():
        return candidate

    # Procura no PATH do sistema caso não esteja em /bin
    import shutil
    system_bin = shutil.which(server_name)
    if system_bin:
        return Path(system_bin)

    print(f"[ERRO] Binário '{server_name}' não encontrado em {BIN_DIR} nem no PATH.")
    print("Execute o script setup_usb_ai.sh primeiro para baixar os binários.")
    sys.exit(1)


def select_model() -> Path:
    """Menu interativo para escolha do modelo com orçamento estrito de RAM."""
    models = {
        "1": {
            "name": "Llama-3.2-1B-Instruct (Q4_K_M)",
            "file": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "desc": "Rápido / Conversação / Síntese direta (~800 MB)"
        },
        "2": {
            "name": "Qwen2.5-1.5B-Instruct (Q4_K_M)",
            "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "desc": "Código / Lógica / Tarefas ReAct estruturadas (~1.1 GB)"
        }
    }

    print("\n" + "=" * 62)
    print("     SELEÇÃO DE MODELO LOCAL (EXECUÇÃO 100% OFFLINE)       ")
    print("=" * 62)
    for key, info in models.items():
        path = MODELS_DIR / info["file"]
        status = "[PRESENTE]" if path.exists() else "[NÃO ENCONTRADO]"
        print(f" [{key}] {info['name']} {status}")
        print(f"     Foco: {info['desc']}")
    print("=" * 62)

    choice = ""
    while choice not in models:
        choice = input("\nEscolha o modelo desejado [1 ou 2] (padrão: 2): ").strip()
        if choice == "":
            choice = "2"

    selected_file = MODELS_DIR / models[choice]["file"]
    if not selected_file.exists():
        print(f"\n[AVISO] Arquivo {selected_file.name} não existe na pasta /models.")
        print("Modelos disponíveis na pasta:")
        found = list(MODELS_DIR.glob("*.gguf"))
        if not found:
            print("   Nenhum arquivo .gguf encontrado em /models!")
            print("   Execute setup_usb_ai.sh para baixá-los.")
            sys.exit(1)
        for idx, m in enumerate(found, 1):
            print(f"   [{idx}] {m.name}")
        sub_choice = input("Selecione o número do arquivo que deseja carregar: ").strip()
        try:
            return found[int(sub_choice) - 1]
        except Exception:
            return found[0]

    return selected_file


def start_llama_server(model_path: Path):
    """Inicia o llama-server em background otimizado para computadores modestos."""
    global SERVER_PROCESS, SERVER_PORT, API_URL, HEALTH_URL, SERVER_LOG_FILE

    SERVER_PORT = find_free_port()
    API_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/v1/chat/completions"
    HEALTH_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/health"

    # Verifica se o servidor já está ativo (ex: reexecução)
    try:
        req = urllib.request.Request(HEALTH_URL)
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                print(f"[Sistema] Servidor llama.cpp já está em execução na porta {SERVER_PORT}.")
                return
    except Exception:
        pass

    binary = find_llama_binary()

    # Detecção de recursos da máquina
    threads = int(os.environ.get("THREADS", max(1, (os.cpu_count() or 2) - 1)))
    ctx_size = int(os.environ.get("CTX_SIZE", 2048))

    cmd = [
        str(binary),
        "-m", str(model_path),
        "--host", SERVER_HOST,
        "--port", str(SERVER_PORT),
        "-c", str(ctx_size),
        "-t", str(threads),
        "-b", "512",          # Lote maior acelera avaliação de prompt em CPU
        "-ub", "512",         # Physical batch size
        "-n", "160",          # Limite de tokens para agilizar respostas
        "--log-disable"       # Mantém o terminal limpo
    ]

    print(f"\n[Sistema] Iniciando {binary.name} na porta {SERVER_PORT}...")
    print(f"   Modelo: {model_path.name}")
    print(f"   Contexto: {ctx_size} tokens | Threads CPU: {threads} | Batch: 512")

    log_file_path = USB_ROOT / "llama_server.log"
    SERVER_LOG_FILE = open(log_file_path, "w", encoding="utf-8", errors="replace")

    # Inicia o processo redirecionando a saída para o log
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        SERVER_PROCESS = subprocess.Popen(cmd, stdout=SERVER_LOG_FILE, stderr=subprocess.STDOUT, creationflags=creationflags)
    else:
        SERVER_PROCESS = subprocess.Popen(cmd, stdout=SERVER_LOG_FILE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)

    # Aguarda o servidor estar pronto (health check)
    print("   Aguardando inicialização do modelo na memória...", end="", flush=True)
    max_wait = 45
    start_time = time.time()
    ready = False

    while time.time() - start_time < max_wait:
        if SERVER_PROCESS.poll() is not None:
            SERVER_LOG_FILE.flush()
            print(f"\n[ERRO] O servidor encerrou precocemente com código {SERVER_PROCESS.returncode}.")
            try:
                with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    err_lines = [l.strip() for l in f.readlines() if l.strip()]
                    if err_lines:
                        print("Detalhes do erro:")
                        for line in err_lines[-5:]:
                            print(f"   {line}")
            except Exception:
                pass
            cleanup_server()
            sys.exit(1)

        try:
            req = urllib.request.Request(HEALTH_URL)
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    if not ready:
        print("\n[ERRO] O servidor não respondeu dentro do tempo limite.")
        cleanup_server()
        sys.exit(1)

    print(" [PRONTO!]")


def call_llm(messages: list) -> str:
    """Chama a API OpenAI-compatible do llama-server via urllib com proteção de timeout."""
    payload = {
        "messages": messages,
        "temperature": 0.1,       # Menor temperatura para maior obediência ao ReAct
        "top_p": 0.9,
        "max_tokens": 160,        # Rápido em CPU
        "stop": ["Observation:", "Observation", "Usuário:"]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        # Timeout estendido (240s) para garantir execução em CPUs modestas
        with urllib.request.urlopen(req, timeout=240) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        return f"Erro de comunicação com o servidor local: {e}"
    except TimeoutError:
        return "Erro: Tempo limite de processamento atingido na CPU."


def parse_action(text: str):
    """
    Extrai a intenção de ferramenta usando regex tolerante a modelos pequenos.
    Reconhece:
      Action: tool_name[param]
      Action: tool_name(param)
      Action: {"tool": "...", "query": "..."}
      Action: tool_name param
    """
    # Formato 1: Action: nome_ferramenta[argumento]
    match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\[(.*?)\]", text, re.DOTALL)
    if match:
        tool_name = match.group(1).strip()
        arg = match.group(2).strip().strip("'\"` ")
        return tool_name, arg

    # Formato 2: Action: nome_ferramenta(argumento)
    match_paren = re.search(r"Action:\s*([a-zA-Z0-9_]+)\((.*?)\)", text, re.DOTALL)
    if match_paren:
        tool_name = match_paren.group(1).strip()
        arg = match_paren.group(2).strip().strip("'\"` ")
        return tool_name, arg

    # Formato 3: Action: {"tool": "search_kb", "arg": "termo"}
    json_match = re.search(r"Action:\s*(\{.*?\})", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            tool_name = data.get("tool") or data.get("name") or data.get("action")
            arg = data.get("arg") or data.get("query") or data.get("content") or data.get("filename") or ""
            if tool_name:
                return str(tool_name).strip(), str(arg).strip().strip("'\"` ")
        except Exception:
            pass

    # Formato 4: Action: tool_name: argumento ou Action: tool_name argumento
    match_colon = re.search(r"Action:\s*([a-zA-Z0-9_]+)(?:[:\s]+)([^\n\r]+)", text)
    if match_colon:
        t_name = match_colon.group(1).strip()
        if t_name.lower() in ("read_file", "search_kb", "write_file", "list_files", "list_kb"):
            return t_name, match_colon.group(2).strip().strip("'\"` ")

    return None, None


def extract_final_answer(text: str) -> str:
    """Extrai a resposta final do modelo ou retorna o texto limpo."""
    if "Final Answer:" in text:
        return text.split("Final Answer:", 1)[1].strip()
    return text.strip()


def react_loop(user_query: str, chat_history: list = None):
    """
    Loop ReAct (Reason + Act) com memória conversacional e assistência automática a arquivos.
    """
    print(f"\n[Usuário] {user_query}")
    if chat_history is None:
        chat_history = []

    # Atalho para comando de leitura direta: ex: "ler arquivo sobre_sistema.txt" ou "leia sobre_sistema.txt"
    direct_match = re.search(r"^(?:ler|leia|abrir|ver|cat)\s+(?:o\s+arquivo\s+|arquivo\s+)?([^\s]+)$", user_query.strip(), re.IGNORECASE)
    if direct_match:
        target_name = direct_match.group(1).strip()
        print(f"  ⚡ [Leitura direta solicitada]: {target_name}")
        content = execute_tool("read_file", target_name)
        print(f"\n{content}\n")
        chat_history.append({"role": "user", "content": user_query})
        chat_history.append({"role": "assistant", "content": f"Conteúdo de {target_name}:\n{content}"})
        return

    system_prompt = get_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]

    # Inclui os últimos 2 turnos da conversa para contexto de pronomes ("dele", "nele", "desse arquivo")
    for turn in chat_history[-4:]:
        messages.append(turn)

    messages.append({"role": "user", "content": user_query})

    max_steps = 5
    step = 0
    refusal_keywords = [
        "não tenho acesso", "arquivo privado", "não posso acessar",
        "não possuo autorização", "não tenho autorização", "sem acesso",
        "não consigo acessar", "privacidade", "não me é permitido"
    ]

    while step < max_steps:
        step += 1
        print("  ⏳ [Processando raciocínio na CPU... aguarde alguns segundos]", flush=True)
        llm_output = call_llm(messages)

        # Imprime o raciocínio interno do modelo
        for line in llm_output.splitlines():
            line_str = line.strip()
            if line_str.startswith("Thought:"):
                print(f"  🧠 {line_str}")
            elif line_str.startswith("Action:"):
                print(f"  ⚡ {line_str}")

        # Verifica se o modelo já concluiu com Final Answer
        if "Final Answer:" in llm_output:
            final = extract_final_answer(llm_output)
            print(f"\n[Resposta Final]\n{final}\n")
            chat_history.append({"role": "user", "content": user_query})
            chat_history.append({"role": "assistant", "content": final})
            return

        # Verifica se há ação a executar
        tool_name, tool_arg = parse_action(llm_output)

        if tool_name:
            print(f"  ⚙️ Executando: {tool_name} com argumento '{tool_arg}'...")
            observation = execute_tool(tool_name, tool_arg)
            print(f"  📥 [Observation]: {observation[:200]}..." if len(observation) > 200 else f"  📥 [Observation]: {observation}")

            # Alimenta a conversa com o pensamento do modelo e a observação real
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
        else:
            # Caso o modelo pequeno recuse ("não tenho acesso") ou não tenha disparado a Action ao ser perguntado sobre arquivos:
            is_refusal = any(kw in llm_output.lower() for kw in refusal_keywords)
            asked_about_files = any(w in user_query.lower() for w in ["arquivo", "ler", "leia", "dentro", "conteudo", "conteúdo", "o que tem", "sobre"])
            kb_files = get_kb_files()

            if (is_refusal or asked_about_files) and kb_files and step == 1:
                # Localiza o arquivo pretendido ou usa o primeiro da base
                chosen_file = kb_files[0]
                for f_name in kb_files:
                    if f_name.lower() in user_query.lower():
                        chosen_file = f_name
                        break
                print(f"  ⚙️ [Auto-Assist]: Consultando '{chosen_file}' na base de conhecimento...")
                observation = execute_tool("read_file", chosen_file)
                messages.append({"role": "assistant", "content": f"Thought: consultando o arquivo {chosen_file}\nAction: read_file[{chosen_file}]"})
                messages.append({"role": "user", "content": f"Observation: {observation}\n\nCom base no arquivo lido acima, responda a pergunta do usuário com Final Answer:"})
                continue

            # Se não chamou ferramenta nem usou Final Answer, apresenta a resposta direta
            clean_ans = llm_output.replace("Thought:", "").strip()
            print(f"\n[Resposta]\n{clean_ans}\n")
            chat_history.append({"role": "user", "content": user_query})
            chat_history.append({"role": "assistant", "content": clean_ans})
            return

    print("\n[Aviso] Limite de passos ReAct atingido. Resposta baseada nas observações obtidas:")
    messages.append({"role": "user", "content": "Forneça agora a Final Answer resumindo o que você descobriu."})
    final_output = call_llm(messages)
    final_ans = extract_final_answer(final_output)
    print(f"\n[Resposta Final]\n{final_ans}\n")
    chat_history.append({"role": "user", "content": user_query})
    chat_history.append({"role": "assistant", "content": final_ans})


def main():
    print("""
==================================================================
        AGENTE IA OFFLINE PORTÁTIL - AMBIENTE EMBARCADO          
==================================================================
- 100% Local e Privado (Sem conexão externa necessária)
- Janela de contexto: 2048 tokens | Zero dependências pip
- Ferramentas ativas: search_kb, read_file, write_file, list_files
- Comandos rápidos: 'listar' (ver arquivos) | 'ler <arquivo>'
==================================================================
""")
    # 1. Seleciona o modelo
    selected_model = select_model()

    # 2. Inicia o servidor local
    start_llama_server(selected_model)

    print("\n" + "-" * 62)
    print("Agente pronto! Digite sua pergunta ou comando.")
    print("Dica: Digite 'listar' para ver arquivos ou 'ler <arquivo>'.")
    print("Digite 'sair' ou 'exit' para encerrar.")
    print("-" * 62)

    chat_history = []

    while True:
        try:
            user_input = input("\nVocê > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("sair", "exit", "quit", ":q"):
                print("Até logo!")
                break

            # Atalhos rápidos locais
            if user_input.lower() in ("listar", "arquivos", "list", "ls", "arquivos na base"):
                print(f"\n{list_kb()}\n")
                continue

            react_loop(user_input, chat_history)
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando sessão...")
            break


if __name__ == "__main__":
    main()

