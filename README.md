Here’s an updated **README.md** based on your current file, adding the interactive **menu** and generating **both Technical and Business docs by default**, plus notes about the new `BusinessDocGenerator`. 

````markdown
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

**New (Business-Friendly Docs + Menu):**
- 🗺️ **Business documentation**: Executive Summary, Capabilities, User Journeys, Inputs/Outputs, Operations, Security & Privacy, Risks, Glossary, Roadmap — synthesized from LADOM via the local LLM.
- 🧭 **Interactive menu**: choose *Technical*, *Business*, or **Both (default)** every run.

---

## 🚀 Quick Start

### 1) Prerequisites
- **Python** 3.8+
- **Ollama** installed and running locally  
  One-time model pull:
  ```bash
  ollama pull qwen2.5-coder:7b
````

**Windows tip:** Keep large model files on a fast NVMe drive.
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

You’ll be prompted for the project path to scan and then see a **menu**:

```
Choose documentation type:
  1) Technical
  2) Business
  3) Both  [default]
Enter choice [1/2/3]:
```

Press **Enter** to generate **both** docs (default).
Outputs are written under the project-specific folder inside `Documentation/` (configurable).

---

## 📄 Outputs

By default, you’ll get **two** documentation sets:

* **Technical**

  * `documentation.technical.md`
  * `documentation.technical.html`

* **Business**

  * `documentation.business.md`
  * `documentation.business.html`

The Business doc is stakeholder-friendly (non-technical) and complements the API-style Technical doc.

---

## ⚙️ Configuration

Edit **`config.yml`** (or **`config.yaml`**) at the repo root:

```yaml
# Directories to exclude from scanning
exclude_dirs:
  - node_modules
  - __pycache__
  - .git

# Output configuration
output:
  directory: Documentation

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
│   ├── main.py                      # Entry point (interactive menu; generates Technical & Business docs)
│   ├── config_loader.py             # Configuration management
│   ├── ladom_schema.py              # LADOM schema & validation
│   ├── cache_manager.py             # Docstring caching
│   ├── rate_limiter.py              # Rate limiting
│   ├── path_validator.py            # Path security checks & safe output paths
│   ├── doc_generator.py             # Technical Markdown/HTML generators
│   ├── business_doc_generator.py    # NEW: Business doc synthesis (local LLM, single project-level prompt)
│   ├── providers/
│   │   └── ollama_client.py         # Local client for Ollama (no external deps)
│   └── analyzers/
│       ├── base_analyzer.py         # LLM prompt + normalization; caching
│       ├── py_analyzer.py           # Python analyzer (AST + LLM synthesis)
│       ├── js_analyzer.py           # JavaScript analyzer (covers constructor/field/prototype patterns)
│       └── java_analyzer.py         # Java analyzer (optional; uses javalang if installed)
├── tests/
│   ├── test_ladom_schema.py
│   ├── test_cache_manager.py
│   └── test_analyzers.py
├── config.yml                        # Configuration (or config.yaml)
├── requirements.txt                  # Python dependencies
└── README.md
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

Choose documentation type:
  1) Technical
  2) Business
  3) Both  [default]

Generating documentation...

============================================================
  ✓ Documentation generated successfully!
============================================================

Cache statistics:
  - Total entries: 18
  - Cache file: .docstring_cache.json

Local LLM calls made: 5
```

---

## 🧱 Architecture Overview

1. **File scanning** → respects `exclude_dirs`
2. **Language analyzers** → parse AST/heuristics and extract symbols
3. **LADOM build** → normalized, language-agnostic representation
4. **LLM docstrings** → prompts a local model for concise descriptions
5. **Renderers** → Technical & Business outputs (Markdown and HTML)

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

## 🗺️ Business Documentation (What it includes)

* **Executive Summary** — 2–4 sentence elevator pitch
* **Audience, Goals, KPIs** — who it’s for and how success is measured
* **Capabilities** — grouped features in plain language
* **User Journeys** — stepwise flows for users/stakeholders
* **Inputs & Outputs** — what the app consumes/produces
* **Operations** — how to run, config keys, logs, troubleshooting
* **Security & Privacy** — data flow, PII stance, storage, LLM usage
* **Risks & Assumptions** — constraints and known gaps
* **Glossary & Roadmap** — shared vocabulary and what’s next

All of this is produced locally via the Ollama model, using only the aggregated LADOM as context.

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

Add a generator in `src/doc_generator.py` or a parallel renderer, and call it in `src/main.py`.

---

## 🧩 Troubleshooting

**“Connection refused” / timeouts**

* Ensure Ollama is running and reachable at `base_url`.
* Try: `curl http://localhost:11434/api/tags` (should list models).

**“model not found”**

* Pull it first: `ollama pull qwen2.5-coder:7b`.

**Slow generations**

* Reduce prompt context; keep essential code snippets only.
* Keep LLM calls modest while enabling parallel file scanning.
* On Windows/NVIDIA, set “Prefer maximum performance” for Python in the NVIDIA Control Panel.

**Nothing analyzed**

* Confirm your file types are included and not excluded by `exclude_dirs`.

---

## 🔒 Security

* All inference is local; nothing is sent to third-party services.
* `security.forbidden_paths` ensures secrets (e.g., `.env`, keys) are never read or sent.
* Cache file (`.docstring_cache.json`) is local and can be ignored by VCS (add to `.gitignore`).

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