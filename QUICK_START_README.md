# Quick Start: README Generation

## Generate a Comprehensive README in 3 Steps

### Step 1: Run the Generator

```bash
python -m src.main
```

### Step 2: Enter Your Project Path

```
Enter the project path to scan: /path/to/your/project
```

Or use `.` for the current directory:

```
Enter the project path to scan: .
```

### Step 3: Select README Generation

```
Choose documentation type:
  1) Technical
  2) Business
  3) Both  [default]
  4) README (Comprehensive)    ← Choose this!
  5) All (Technical + Business + README)
Enter choice [1/2/3/4/5]: 4
```

That's it! Your comprehensive README will be generated.

## What You'll Get

After processing completes, you'll find:

```
Documentation/
  └── YourProjectName/
      ├── README.md      ← Comprehensive markdown README
      └── README.html    ← HTML version
```

## Example Output Preview

Your generated README will include:

```markdown
# Your Project Name

[![Build Status](badge)](#) [![License](badge)](#)

> One-line compelling description of your project

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
...

## Overview
[Detailed 2-3 paragraphs explaining what your project does]

## Features
- ✨ Feature 1 - [Detected from your code]
- 🚀 Feature 2 - [Detected from your code]
...

## Architecture
[Mermaid diagram of your system architecture]

Your project follows a [Pattern] architecture...

## Directory Structure
```
project/
  ├── src/          - Main application code
  ├── tests/        - Unit tests
  ├── config/       - Configuration files
  ...
```

## Getting Started

### Prerequisites
- Python 3.8+
- [Other detected dependencies]

### Installation
```bash
git clone [your-repo]
cd [your-project]
pip install -r requirements.txt
```

### Configuration
[Based on your config files]

## Usage

### Basic Usage
```python
# Real examples extracted from your code
from your_module import YourClass

instance = YourClass()
instance.main_method()
```

[... continues with more sections ...]
```

## Compare to Other Documentation Types

| Feature | Technical Doc | Business Doc | **README (Comprehensive)** |
|---------|--------------|--------------|---------------------------|
| Target Audience | Developers | Business stakeholders | Everyone |
| Code Details | ✅ Deep | ❌ None | ✅ Moderate |
| Business Context | ❌ None | ✅ Deep | ✅ Some |
| Architecture Diagrams | ❌ No | ❌ No | **✅ Yes** |
| Setup Instructions | ❌ No | ❌ No | **✅ Yes** |
| Usage Examples | ✅ Some | ❌ No | **✅ Many** |
| API Documentation | ✅ Yes | ❌ No | **✅ Yes** |
| Troubleshooting | ❌ No | ❌ No | **✅ Yes** |
| Contributing Guide | ❌ No | ❌ No | **✅ Yes** |

## Tips for Better Results

### 1. Add Good Docstrings

**Before:**
```python
def process(data):
    return data.upper()
```

**Better:**
```python
def process(data: str) -> str:
    """
    Process input data by converting to uppercase.
    
    Args:
        data: Input string to process
        
    Returns:
        Uppercase version of input string
    """
    return data.upper()
```

### 2. Include Configuration Files

Make sure you have:
- `requirements.txt` or `pyproject.toml`
- `config.yaml` or `config.json`
- `.env.example` if using environment variables

### 3. Add Main Entry Point

```python
# main.py
def main():
    """Main entry point for the application."""
    print("Running application...")
    
if __name__ == "__main__":
    main()
```

### 4. Organize Your Code

```
Good structure:
project/
  ├── src/
  │   ├── models/
  │   ├── services/
  │   └── utils/
  ├── tests/
  ├── config/
  └── docs/

This helps with architecture detection!
```

### 5. Include Tests

Test files help the generator understand:
- How to use your code
- What features exist
- Expected behavior

```python
# test_example.py
def test_process():
    """Example showing how to use the process function."""
    result = process("hello")
    assert result == "HELLO"
```

## Advanced: Generate All Documentation Types

Want everything? Choose option **5**:

```
Enter choice [1/2/3/4/5]: 5
```

This generates:
- `documentation.technical.md` - Detailed technical docs
- `documentation.business.md` - Business stakeholder docs
- `README.md` - Comprehensive README
- HTML versions of all three

Perfect for complete project documentation!

## Troubleshooting

### "No files found"
- Check your project path is correct
- Ensure you have `.py`, `.js`, `.ts`, or `.java` files
- Check `exclude_dirs` in `config.yaml`

### "README is too generic"
- Add more docstrings to your code
- Include a `main.py` with usage example
- Add configuration files

### "LLM timeout"
- Increase `timeout` in `config.yaml`:
  ```yaml
  llm:
    timeout: 600  # Increase to 10 minutes
  ```

### "Missing diagrams"
- Ensure `generate_diagrams: true` in config
- Check you have internal module imports
- Larger projects generate better diagrams

## Next Steps

1. ✅ Generate your first README with option 4
2. 📖 Read the full guide: [README_GENERATION_GUIDE.md](README_GENERATION_GUIDE.md)
3. ⚙️ Customize in `config.yaml` under the `readme:` section
4. 🎨 Edit and refine the generated README as needed
5. 📊 Try generating all docs (option 5) for comparison

## Questions?

- **Full documentation**: See [README_GENERATION_GUIDE.md](README_GENERATION_GUIDE.md)
- **Configuration**: Check `config.yaml` 
- **Issues**: Check project's main README

Happy documenting! 📝✨
