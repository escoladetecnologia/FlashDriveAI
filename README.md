# 🧠 FlashDriveAI (Offline Portable AI Agent)

> **Agente de Inteligência Artificial 100% Offline, Portátil e Privado**  
> Projetado para caber em um pendrive de 8 GB e rodar em qualquer computador modesto (sem placa de vídeo dedicada, 2 a 4 GB de RAM), com **zero dependências pip** e **total privacidade**.

---

## ✨ Destaques

- **100% Offline & Privado:** Não faz nenhuma requisição externa. Seus documentos nunca saem da sua máquina.
- **Zero Dependências:** Construído unicamente sobre a biblioteca padrão do Python 3 (`urllib`, `json`, `subprocess`, `re`, `pathlib`). Sem `pip install`, sem frameworks pesados.
- **Portabilidade Total:** Execute no Windows com um clique (`start_agent.bat`) ou no Linux (`start_agent.sh`).
- **Arquitetura ReAct Local:** O modelo é capaz de raciocinar e executar ferramentas locais como busca semântica simples (`search_kb`), leitura de arquivos (`read_file`) e escrita (`write_file`).
- **Modelos Otimizados:** Compatível com Llama 3.2 1B e Qwen 2.5 1.5B (quantizados em GGUF Q4_K_M).

---

## 📁 Estrutura do Repositório

```text
├── agent/                  # Código-fonte do Agente ReAct
│   ├── agent.py            # Orquestrador do servidor e loop ReAct
│   ├── prompts.py          # Engenharia de prompts com injeção de contexto
│   └── tools.py            # Ferramentas nativas do agente (RAG local)
├── bin/                    # Binários do llama.cpp (gerados via setup)
├── boot_os/                # Imagem ISO live opcional (Alpine/antiX)
├── knowledge_base/         # Sua base de documentos privados (RAG)
├── models/                 # Modelos GGUF (baixados pelo setup)
├── setup_usb_ai.sh         # Script de provisionamento automático
├── start_agent.bat         # Inicializador portátil para Windows
├── start_agent.sh          # Inicializador portátil para Linux
└── .gitignore              # Protege arquivos sensíveis e modelos pesados
```

---

## 🚀 Como Começar

### 1. Clonar o Repositório
```bash
git clone https://github.com/escoladetecnologia/FlashDriveAI.git
cd FlashDriveAI
```

### 2. Baixar Modelos e Binários
Por serem arquivos pesados (>1 GB), os modelos GGUF não são versionados no Git. Para baixá-los automaticamente:

**No Linux / WSL:**
```bash
chmod +x setup_usb_ai.sh
./setup_usb_ai.sh
```

**Ou baixe manualmente os modelos GGUF e coloque na pasta `models/`:**
- [Llama-3.2-1B-Instruct-Q4_K_M.gguf](https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF)
- [qwen2.5-1.5b-instruct-q4_k_m.gguf](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)

### 3. Iniciar o Agente

- **No Windows:** Dê duplo clique em `start_agent.bat`.
- **No Linux:** Execute `./start_agent.sh`.

---

## 🔒 Privacidade e Segurança (.gitignore)
A pasta `knowledge_base/` é configurada por padrão no `.gitignore` para que nenhum documento pessoal ou sensível adicionado seja enviado acidentalmente ao GitHub.

---

## 📜 Licença
Distribuído sob a licença MIT. Consulte `LICENSE` para mais informações.
