# Automated Documentation Generator

A robust, language-agnostic command-line tool that automatically generates comprehensive project documentation from your source code using AI-powered analysis.

## Features

- 🔍 **Multi-Language Support**: Currently supports Python and JavaScript with extensible architecture
- 🤖 **AI-Powered**: Uses Google's Gemini AI to generate high-quality docstrings
- 📦 **LADOM Architecture**: Language-Agnostic Document Object Model ensures consistency
- ⚡ **Parallel Processing**: Fast analysis with multi-threaded file processing
- 💾 **Smart Caching**: Reduces API calls by caching generated documentation
- 🎨 **Multiple Output Formats**: Generates both Markdown and HTML documentation
- 🔒 **Security First**: Path validation and safe file handling
- ⚙️ **Configurable**: YAML-based configuration for easy customization

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd automated-doc-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

To get a Gemini API key:
- Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- Sign in with your Google account
- Create a new API key

## Usage

### Basic Usage

Run the generator:
```bash
python -m src.main
```

You'll be prompted to enter the project path to scan.

### Configuration

Edit `config.yaml` to customize behavior:

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

# LLM Configuration
llm:
  model: gemini-2.5-flash
  temperature: 0.3
  rate_limit_calls_per_minute: 20

# Enable/disable caching
cache:
  enabled: true
  file: .docstring_cache.json

# Processing options
processing:
  parallel: true
  max_workers: 4
```

### Example

```bash
$ python -m src.main
============================================================
  Automated Documentation Generator
============================================================

Enter the project path to scan: /path/to/your/project

Scanning project: /path/to/your/project
Found 15 files to analyze
Analyzing files: 100%|██████████████████| 15/15 [00:23<00:00]

Generating documentation...

============================================================
  ✓ Documentation generated successfully!
============================================================

Cache statistics:
  - Total entries: 12
  - Cache file: .docstring_cache.json

API calls made: 3
```

## Project Structure

```
automated-doc-generator/
├── src/
│   ├── main.py                 # Main entry point
│   ├── config_loader.py        # Configuration management
│   ├── ladom_schema.py         # LADOM schema and validation
│   ├── cache_manager.py        # Docstring caching
│   ├── rate_limiter.py         # API rate limiting
│   ├── path_validator.py       # Path security validation
│   ├── doc_generator.py        # Documentation generators
│   └── analyzers/
│       ├── base_analyzer.py    # Base analyzer class
│       ├── py_analyzer.py      # Python analyzer
│       └── js_analyzer.py      # JavaScript analyzer
├── tests/
│   ├── test_ladom_schema.py    # LADOM tests
│   ├── test_cache_manager.py   # Cache tests
│   └── test_analyzers.py       # Analyzer tests
├── config.yaml                 # Configuration file
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (create this)
└── README.md                   # This file
```

## Architecture

The system follows a pipeline architecture:

1. **File Scanning**: Walks through project directory, excluding configured directories
2. **Language-Specific Parsing**: Uses appropriate analyzer (Python/JavaScript) to parse files
3. **LADOM Generation**: Converts parsed data into Language-Agnostic Document Object Model
4. **Documentation Generation**: Renders LADOM into Markdown/HTML using templates

### LADOM Structure

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
          "parameters": [
            {
              "name": "param1",
              "type": "str",
              "description": "Parameter description"
            }
          ],
          "returns": {
            "type": "int",
            "description": "Return description"
          }
        }
      ],
      "classes": [...]
    }
  ]
}
```

## Running Tests

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=src --cov-report=html
```

## Extending the Tool

### Adding a New Language

1. Create a new analyzer in `src/analyzers/`:

```python
from .base_analyzer import BaseAnalyzer

class MyLanguageAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "mylanguage"
    
    def analyze(self, file_path: str):
        # Implement parsing logic
        # Return LADOM-compliant structure
        pass
```

2. Register the analyzer in `src/main.py`:

```python
from .analyzers.mylang_analyzer import MyLanguageAnalyzer

# In scan_and_analyze function:
if file.endswith('.mylang'):
    files_to_analyze.append((file_path, mylang_analyzer, 'MyLanguage'))
```

### Custom Output Formats

Create a new generator class in `src/doc_generator.py`:

```python
class CustomGenerator:
    def __init__(self, template: str = None):
        # Initialize with custom template
        pass
    
    def generate(self, aggregated_ladom: dict, output_path: str):
        # Implement custom generation logic
        pass
```

## Troubleshooting

### Common Issues

**Issue**: "GEMINI_API_KEY not found"
- **Solution**: Ensure `.env` file exists with valid API key

**Issue**: "Access denied to forbidden path"
- **Solution**: Check `security.forbidden_paths` in config.yaml

**Issue**: Rate limit errors
- **Solution**: Reduce `rate_limit_calls_per_minute` in config.yaml

**Issue**: Analysis fails for certain files
- **Solution**: Check logs in `docgen.log` for detailed error messages

## Performance Tips

1. **Enable Caching**: Keep `cache.enabled: true` to avoid regenerating docstrings
2. **Adjust Workers**: Increase `max_workers` for faster processing on multi-core systems
3. **Rate Limiting**: Balance between speed and API quota with `rate_limit_calls_per_minute`
4. **Exclude Irrelevant Directories**: Add to `exclude_dirs` to skip unnecessary files

## Security

- Path validation prevents access to sensitive system directories
- Configurable forbidden paths in `security.forbidden_paths`
- No external code execution - only static analysis
- API keys stored securely in `.env` (not committed to version control)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs in `docgen.log`
- Open an issue on GitHub

## Acknowledgments

- Google Gemini AI for docstring generation
- Esprima for JavaScript parsing
- Python AST for Python parsing
- Jinja2 for templating

## Roadmap

- [ ] Support for more languages (TypeScript, Java, C++)
- [ ] Visual diagram generation (class diagrams, call graphs)
- [ ] Web interface for documentation viewing
- [ ] Plugin system for custom analyzers
- [ ] Git integration for change tracking
- [ ] Automated documentation updates on commits