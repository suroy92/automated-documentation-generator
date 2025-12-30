# src/main.py

"""
Main orchestration module for the automated documentation generator.
Menu:
  1) Technical doc
  2) Business doc
  3) Both (default)
Outputs:
  - documentation.technical.md / .html
  - documentation.business.md / .html
"""

import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple
from dotenv import load_dotenv
from tqdm import tqdm

from .config_loader import ConfigLoader
from .cache_manager import DocstringCache
from .rate_limiter import RateLimiter
from .path_validator import PathValidator
from .analyzers.py_analyzer import PythonAnalyzer
from .analyzers.js_analyzer import JavaScriptAnalyzer
from .analyzers.java_analyzer import JavaAnalyzer
from .technical_doc_generator import MarkdownGenerator, HTMLGenerator
from .ladom_schema import LADOMValidator
from .providers.ollama_client import LLM, LLMConfig
from .business_doc_generator import BusinessDocGenerator

# Load environment variables (optional)
load_dotenv()

logger = logging.getLogger(__name__)


def setup_logging(config: ConfigLoader):
    log_level = getattr(logging, config.get_log_level().upper(), logging.INFO)
    log_format = config.get_log_format()
    log_file = config.get_log_file()
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    logger.info("Logging initialized")


def initialize_llm_client(config: ConfigLoader) -> LLM:
    try:
        llm_cfg = getattr(config, "config", {}).get("llm", {}) if hasattr(config, "config") else {}
    except Exception:
        llm_cfg = {}
    client = LLM(
        LLMConfig(
            base_url=llm_cfg.get("base_url", "http://localhost:11434"),
            model=llm_cfg.get("model", "qwen2.5-coder:7b"),
            temperature=float(llm_cfg.get("temperature", 0.2) or 0.2),
            embedding_model=llm_cfg.get("embedding_model", "all-minilm:l6-v2"),
            timeout_seconds=int(llm_cfg.get("timeout_seconds", 120) or 120),
        )
    )
    logger.info("Ollama LLM client initialized (local)")
    return client


def analyze_file(file_path: str, analyzer, file_type: str):
    try:
        logger.debug(f"Analyzing {file_type} file: {os.path.basename(file_path)}")
        ladom_data = analyzer.analyze(file_path)
        return (file_path, ladom_data)
    except Exception as e:
        logger.error(f"Error analyzing {file_path}: {e}")
        return (file_path, None)


def scan_and_analyze(project_path: str, config: ConfigLoader,
                     py_analyzer: PythonAnalyzer,
                     js_analyzer: JavaScriptAnalyzer,
                     java_analyzer: JavaAnalyzer):
    exclude_dirs = config.get_exclude_dirs()
    files_to_analyze = []

    logger.info("Scanning project directory...")
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".py"):
                files_to_analyze.append((file_path, py_analyzer, "Python"))
            elif file.endswith(".js"):
                files_to_analyze.append((file_path, js_analyzer, "JavaScript"))
            elif file.endswith(".java"):
                files_to_analyze.append((file_path, java_analyzer, "Java"))

    if not files_to_analyze:
        logger.warning("No supported files found in project")
        return None

    logger.info(f"Found {len(files_to_analyze)} files to analyze")

    aggregated_ladom = {"project_name": os.path.basename(os.path.abspath(project_path)), "files": []}

    if config.is_parallel_processing() and len(files_to_analyze) > 1:
        logger.info("Using parallel processing")
        max_workers = min(config.get_max_workers(), len(files_to_analyze))
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_file, fp, analyzer, ft): (fp, ft) for fp, analyzer, ft in files_to_analyze}
            with tqdm(total=len(files_to_analyze), desc="Analyzing files") as pbar:
                for future in as_completed(futures):
                    file_path, ladom_data = future.result()
                    if ladom_data and ladom_data.get("files"):
                        aggregated_ladom["files"].extend(ladom_data["files"])
                    pbar.update(1)
    else:
        logger.info("Using sequential processing")
        with tqdm(files_to_analyze, desc="Analyzing files") as pbar:
            for file_path, analyzer, file_type in pbar:
                pbar.set_description(f"Analyzing {os.path.basename(file_path)}")
                _, ladom_data = analyze_file(file_path, analyzer, file_type)
                if ladom_data and ladom_data.get("files"):
                    aggregated_ladom["files"].extend(ladom_data["files"])

    logger.info(f"Analysis complete: {len(aggregated_ladom['files'])} files processed")
    return aggregated_ladom


def _menu_choice() -> str:
    print("\nChoose documentation type:")
    print("  1) Technical")
    print("  2) Business")
    print("  3) Both  [default]")
    choice = input("Enter choice [1/2/3]: ").strip()
    if choice == "1":
        return "technical"
    if choice == "2":
        return "business"
    return "both"  # default


def _generate_technical_docs(aggregated_ladom, output_dir: str) -> Tuple[str, str]:
    md_path = os.path.join(output_dir, "documentation.technical.md")
    html_path = os.path.join(output_dir, "documentation.technical.html")
    md = MarkdownGenerator()
    md.generate(aggregated_ladom, md_path)
    HTMLGenerator().generate(aggregated_ladom, html_path)
    logger.info(f"✓ Technical Markdown: {md_path}")
    logger.info(f"✓ Technical HTML:     {html_path}")
    return md_path, html_path


def _generate_business_docs(aggregated_ladom, output_dir: str, llm_client: LLM) -> Tuple[str, str]:
    md_path = os.path.join(output_dir, "documentation.business.md")
    html_path = os.path.join(output_dir, "documentation.business.html")
    biz = BusinessDocGenerator(llm_client)
    biz.generate(aggregated_ladom, md_path)
    HTMLGenerator().generate(aggregated_ladom, html_path)
    logger.info(f"✓ Business Markdown:  {md_path}")
    logger.info(f"✓ Business HTML:      {html_path}")
    return md_path, html_path


def main():
    print("=" * 60)
    print("  Automated Documentation Generator (Local – Ollama / Week 1)")
    print("=" * 60)
    print()

    config = ConfigLoader()
    setup_logging(config)
    logger.info("Starting documentation generator")

    project_path = input("Enter the project path to scan: ").strip()
    if not project_path:
        logger.error("No project path provided")
        print("Error: Project path is required")
        return

    path_validator = PathValidator(config.get_forbidden_paths())
    if not path_validator.validate_project_path(project_path):
        logger.error(f"Invalid or forbidden project path: {project_path}")
        print("\nError: Invalid project path or access denied")
        print("Please ensure:")
        print("  - The path exists and is a valid directory")
        print("  - You have read permissions for this directory")
        print("  - The path doesn't contain system directories (e.g., /etc, /sys)")
        print("  - The path doesn't contain path traversal sequences (..)")
        return

    llm_client = initialize_llm_client(config)
    cache = DocstringCache(cache_file=config.get_cache_file(), enabled=config.is_cache_enabled())
    rate_limiter = RateLimiter(calls_per_minute=config.get_rate_limit())

    py_analyzer = PythonAnalyzer(client=llm_client, cache=cache, rate_limiter=rate_limiter)
    js_analyzer = JavaScriptAnalyzer(client=llm_client, cache=cache, rate_limiter=rate_limiter)
    java_analyzer = JavaAnalyzer(client=llm_client, cache=cache, rate_limiter=rate_limiter)

    print("\nScanning project:", project_path)
    aggregated_ladom = scan_and_analyze(project_path, config, py_analyzer, js_analyzer, java_analyzer)
    if not aggregated_ladom or not aggregated_ladom.get("files"):
        logger.error("No files were successfully analyzed")
        print("\nError: No supported files found or analysis failed")
        return

    # Output dir
    output_dir = config.get_output_dir()
    from .path_validator import PathValidator as PV
    pval = PV()
    project_name = os.path.basename(os.path.abspath(project_path))
    out = pval.get_safe_output_path(output_dir, project_name)
    os.makedirs(out, exist_ok=True)
    logger.info(f"Output directory: {out}")

    # Menu
    doc_choice = _menu_choice()

    print("\nGenerating documentation...")
    if doc_choice in ("technical", "both"):
        _generate_technical_docs(aggregated_ladom, out)

    if doc_choice in ("business", "both"):
        _generate_business_docs(aggregated_ladom, out, llm_client)

    print("\n" + "=" * 60)
    print("  ✓ Documentation generated successfully!")
    print("=" * 60)

    # Cache / rate stats
    stats = cache.get_stats()
    if stats["enabled"]:
        print(f"\nCache statistics:")
        print(f"  - Total entries: {stats['total_entries']}")
        print(f"  - Cache file: {stats['cache_file']}")

    rate_stats = rate_limiter.get_stats()
    print(f"\nLocal LLM calls made: {rate_stats['total_calls']}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        logger.info("Operation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.exception("Unexpected error in main")
