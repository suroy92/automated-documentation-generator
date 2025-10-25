# Automated Documentation Generator (Local — Ollama)

A robust, language-agnostic CLI that scans a project and generates documentation from source code using a Language-Agnostic Document Object Model (LADOM).  
**Runs entirely on your machine using [Ollama](https://ollama.com/). No API keys, no data leaving your device.**

---

## ✨ Features

- 🔍 **Multi-language support**: Python & JavaScript (extensible analyzers)
- 🧠 **Local LLM**: Uses an Ollama model (default: `qwen2.5-coder:7b`)
- 🧱 **LADOM**: A consistent, language-agnostic schema for docs
- ⚡ **Parallel processing**: Multi-threaded scanning
- 💾 **Smart caching**: Avoids regenerating docstrings
- 🧰 **Multiple outputs**: Markdown & HTML
- 🔐 **Security-first**: Path validation & forbidden paths
- ⚙️ **Configurable**: YAML config for model, temperature, rate limits, etc.

---

## 🚀 Quick Start

### 1) Prerequisites
- **Python** 3.8+
- **Ollama** installed and running locally  
  One-time model pull:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```

**Windows tip:** Keep large model files on a fast NVMe drive
Open PowerShell and set:
```powershell
$env:OLLAMA_MODELS = 'D:\ollama\models'
```
Restart the shell and (re)pull models if needed.

### 2) Install

```bash
git clone <your-repo-url>
cd automated-doc-generator
pip install -r requirements.txt
```

No `.env` or API keys required.

### 3) Run

```bash
python -m src.main
```

You’ll be prompted for the project path to scan. Output is written under `Documentation/` by default.

---

## ⚙️ Configuration

Edit **`config.yml`** at the repo root:

```yaml
# Directories to exclude from scanning
exclude_dirs:
  - node_modules
  - __pycache__
  - .git

# Output configuration
output:
  directory: Documentation
  format: markdown

# Local LLM configuration
llm:
  model: qwen2.5-coder:7b        # pull via: ollama pull qwen2.5-coder:7b
  base_url: http://localhost:11434
  temperature: 0.2
  rate_limit_calls_per_minute: 20
  embedding_model: all-minilm:l6-v2   # optional, for future embeddings use
  timeout_seconds: 120

# Caching
cache:
  enabled: true
  file: .docstring_cache.json

# Processing options
processing:
  parallel: true
  max_workers: 4

# Security hardening — keep secrets out of prompts (even locally)
security:
  forbidden_paths:
    - "**/.env"
    - "**/secrets/**"
    - "**/*.pem"
    - "**/*.key"
    - "**/.git/**"
    - "**/__pycache__/**"
    - "**/node_modules/**"
```

**Optional environment overrides**

* `OLLAMA_BASE_URL` (default `http://localhost:11434`)
* `DOCGEN_MODEL` (e.g., `qwen2.5-coder:7b`)
* `OLLAMA_TEMPERATURE`
* `DOCGEN_EMBED_MODEL`
* `DOCGEN_TIMEOUT`

---

## 🧭 Project Structure

```
automated-doc-generator/
├── src/
│   ├── main.py                  # Main entry point (now initializes local Ollama client)
│   ├── config_loader.py         # Configuration management
│   ├── ladom_schema.py          # LADOM schema & validation
│   ├── cache_manager.py         # Docstring caching
│   ├── rate_limiter.py          # Rate limiting
│   ├── path_validator.py        # Path security checks
│   ├── doc_generator.py         # Markdown/HTML generators
│   ├── providers/
│   │   └── ollama_client.py     # NEW: local client for Ollama (no external deps)
│   └── analyzers/
│       ├── base_analyzer.py     # calls client.generate(...)
│       ├── py_analyzer.py       # Python analyzer
│       ├── js_analyzer.py       # JavaScript analyzer
│       └── java_analyzer.py     # Java analyzer (optional)
├── tests/
│   ├── test_ladom_schema.py
│   ├── test_cache_manager.py
│   └── test_analyzers.py
├── config.yaml                   # Configuration (local-first)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🧪 Example Session

```text
$ python -m src.main
============================================================
  Automated Documentation Generator (Local – Ollama)
============================================================

Enter the project path to scan: /path/to/your/project

Scanning project: /path/to/your/project
Found 23 files to analyze
Analyzing files: 100%|███████████████████████████████| 23/23 [00:19<00:00]

Generating documentation...

============================================================
  ✓ Documentation generated successfully!
============================================================

Cache statistics:
  - Total entries: 18
  - Cache file: .docstring_cache.json

API calls made: 5
```

---

## 🧱 Architecture Overview

1. **File scanning** → respects `exclude_dirs`
2. **Language analyzers** → parse ASTs and extract symbols
3. **LADOM build** → normalized, language-agnostic representation
4. **LLM docstrings** → prompts a local model for concise descriptions
5. **Renderers** → Markdown and HTML outputs

**LADOM (example)**

```json
{
  "project_name": "My Project",
  "files": [
    {
      "path": "/path/to/file.py",
      "functions": [
        {
          "name": "function_name",
          "description": "Function description",
          "parameters": [{"name":"param1","type":"str","description":"..."}],
          "returns": {"type":"int","description":"..."}
        }
      ],
      "classes": []
    }
  ]
}
```

---

## 🛠️ Extending

### Add a new analyzer

Create `src/analyzers/my_lang_analyzer.py`:

```python
from .base_analyzer import BaseAnalyzer

class MyLanguageAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "mylanguage"

    def analyze(self, file_path: str):
        # Parse source; return LADOM-compliant dict
        ...
```

Register it in `src/main.py` to include files with your extension.

### Custom output formats

Add a generator in `src/doc_generator.py` and call it in `generate_documentation(...)`.

---

## 🧩 Troubleshooting

**“Connection refused” / timeouts**

* Ensure Ollama is running and reachable at `base_url`.
* Try: `curl http://localhost:11434/api/tags` (should list models).

**“model not found”**

* Pull it first: `ollama pull qwen2.5-coder:7b`.

**Slow generations**

* Reduce context in prompts; keep to essential code snippets.
* Ensure only 1–2 concurrent *LLM* calls while scanning remains parallel.
* On Windows/NVIDIA, set “Prefer maximum performance” for Python in the NVIDIA Control Panel.

**Nothing analyzed**

* Confirm your file types are included and not excluded by `exclude_dirs`.

---

## 🔒 Security

* All inference is local; nothing is sent to third-party services.
* `security.forbidden_paths` ensures secrets (e.g., `.env`, keys) are never read or sent.
* Cache file (`.docstring_cache.json`) is local and ignored by VCS (add to `.gitignore` if not already).

---

## 🧭 Migration Note (from Gemini)

* The project no longer uses Google’s Gemini or API keys.
* Any previous references to `GEMINI_API_KEY` or `google.generativeai` have been removed in favor of a **local client** (`src/providers/ollama_client.py`).
* If you still have an old `.env` file, it is no longer used.

---

## 🧪 Tests

```bash
pytest tests/ -v
# or with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a PR

---

## 📄 License

[LICENCE](./LICENSE)

---

## 🙏 Acknowledgments

* [Ollama](https://ollama.com/) for local model serving
* Python AST & Esprima for parsing
* Jinja2 for templating