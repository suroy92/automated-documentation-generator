# src/main.py

"""
Main orchestration module for the automated documentation generator.
"""

import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from dotenv import load_dotenv
from tqdm import tqdm

from .config_loader import ConfigLoader
from .cache_manager import DocstringCache
from .rate_limiter import RateLimiter
from .path_validator import PathValidator
from .analyzers.py_analyzer import PythonAnalyzer
from .analyzers.js_analyzer import JavaScriptAnalyzer
from .doc_generator import MarkdownGenerator, HTMLGenerator
from .ladom_schema import LADOMValidator

# Load environment variables
load_dotenv()

# Initialize logger
logger = logging.getLogger(__name__)


def setup_logging(config: ConfigLoader):
    """
    Setup logging configuration.
    
    Args:
        config: Configuration loader instance
    """
    log_level = getattr(logging, config.get_log_level().upper(), logging.INFO)
    log_format = config.get_log_format()
    log_file = config.get_log_file()
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger.info("Logging initialized")


def initialize_genai_client():
    """
    Initialize the Gemini AI client.
    
    Returns:
        Initialized client or None if API key not found
    """
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        logger.error("Please set GEMINI_API_KEY in your .env file")
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        logger.info("Gemini AI client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None


def analyze_file(file_path: str, analyzer, file_type: str) -> tuple:
    """
    Analyze a single file.
    
    Args:
        file_path: Path to the file
        analyzer: Analyzer instance
        file_type: Type of file (for logging)
        
    Returns:
        Tuple of (file_path, ladom_data)
    """
    try:
        logger.debug(f"Analyzing {file_type} file: {os.path.basename(file_path)}")
        ladom_data = analyzer.analyze(file_path)
        return (file_path, ladom_data)
    except Exception as e:
        logger.error(f"Error analyzing {file_path}: {e}")
        return (file_path, None)


def scan_and_analyze(project_path: str, config: ConfigLoader, 
                     py_analyzer: PythonAnalyzer, 
                     js_analyzer: JavaScriptAnalyzer) -> dict:
    """
    Scan project directory and analyze all supported files.
    
    Args:
        project_path: Root project path
        config: Configuration loader
        py_analyzer: Python analyzer instance
        js_analyzer: JavaScript analyzer instance
        
    Returns:
        Aggregated LADOM structure
    """
    exclude_dirs = config.get_exclude_dirs()
    
    # Collect all files first
    files_to_analyze = []
    
    logger.info("Scanning project directory...")
    for root, dirs, files in os.walk(project_path):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            
            if file.endswith('.py'):
                files_to_analyze.append((file_path, py_analyzer, 'Python'))
            elif file.endswith('.js'):
                files_to_analyze.append((file_path, js_analyzer, 'JavaScript'))
    
    if not files_to_analyze:
        logger.warning("No supported files found in project")
        return None
    
    logger.info(f"Found {len(files_to_analyze)} files to analyze")
    
    # Analyze files (parallel or sequential based on config)
    aggregated_ladom = {
        "project_name": os.path.basename(os.path.abspath(project_path)),
        "files": []
    }
    
    if config.is_parallel_processing() and len(files_to_analyze) > 1:
        logger.info("Using parallel processing")
        max_workers = min(config.get_max_workers(), len(files_to_analyze))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_file, fp, analyzer, ft): (fp, ft)
                for fp, analyzer, ft in files_to_analyze
            }
            
            with tqdm(total=len(files_to_analyze), desc="Analyzing files") as pbar:
                for future in as_completed(futures):
                    file_path, ladom_data = future.result()
                    
                    if ladom_data and ladom_data.get('files'):
                        aggregated_ladom['files'].extend(ladom_data['files'])
                    
                    pbar.update(1)
    else:
        logger.info("Using sequential processing")
        with tqdm(files_to_analyze, desc="Analyzing files") as pbar:
            for file_path, analyzer, file_type in pbar:
                pbar.set_description(f"Analyzing {os.path.basename(file_path)}")
                _, ladom_data = analyze_file(file_path, analyzer, file_type)
                
                if ladom_data and ladom_data.get('files'):
                    aggregated_ladom['files'].extend(ladom_data['files'])
    
    logger.info(f"Analysis complete: {len(aggregated_ladom['files'])} files processed")
    return aggregated_ladom


def generate_documentation(aggregated_ladom: dict, config: ConfigLoader, 
                          project_name: str) -> bool:
    """
    Generate documentation from aggregated LADOM.
    
    Args:
        aggregated_ladom: Complete LADOM structure
        config: Configuration loader
        project_name: Project name
        
    Returns:
        True if successful, False otherwise
    """
    # Validate LADOM
    if not LADOMValidator.validate_ladom(aggregated_ladom):
        logger.error("LADOM validation failed, cannot generate documentation")
        return False
    
    # Get output configuration
    output_dir = config.get_output_dir()
    path_validator = PathValidator()
    output_path = path_validator.get_safe_output_path(output_dir, project_name)
    
    os.makedirs(output_path, exist_ok=True)
    logger.info(f"Output directory: {output_path}")
    
    # Generate Markdown documentation
    try:
        md_generator = MarkdownGenerator()
        md_file = os.path.join(output_path, "documentation.md")
        md_generator.generate(aggregated_ladom, md_file)
        logger.info(f"✓ Markdown documentation: {md_file}")
    except Exception as e:
        logger.error(f"Failed to generate Markdown documentation: {e}")
        return False
    
    # Optionally generate HTML documentation
    try:
        html_generator = HTMLGenerator()
        html_file = os.path.join(output_path, "documentation.html")
        html_generator.generate(aggregated_ladom, html_file)
        logger.info(f"✓ HTML documentation: {html_file}")
    except Exception as e:
        logger.warning(f"Failed to generate HTML documentation: {e}")
    
    return True


def main():
    """Main entry point for the documentation generator."""
    print("=" * 60)
    print("  Automated Documentation Generator")
    print("=" * 60)
    print()
    
    # Load configuration
    config = ConfigLoader()
    setup_logging(config)
    
    logger.info("Starting documentation generator")
    
    # Get project path from user
    project_path = input("Enter the project path to scan: ").strip()
    
    if not project_path:
        logger.error("No project path provided")
        print("Error: Project path is required")
        return
    
    # Validate project path
    path_validator = PathValidator(config.get_forbidden_paths())
    
    if not path_validator.validate_project_path(project_path):
        logger.error(f"Invalid or forbidden project path: {project_path}")
        print(f"Error: Invalid project path or access denied")
        return
    
    # Initialize Gemini client
    genai_client = initialize_genai_client()
    if not genai_client:
        print("\nWarning: LLM client not initialized. Docstring generation will be limited.")
        response = input("Continue without LLM support? (y/n): ").strip().lower()
        if response != 'y':
            logger.info("User cancelled operation")
            return
    
    # Initialize cache and rate limiter
    cache = DocstringCache(
        cache_file=config.get_cache_file(),
        enabled=config.is_cache_enabled()
    )
    
    rate_limiter = RateLimiter(
        calls_per_minute=config.get_rate_limit()
    )
    
    # Initialize analyzers
    py_analyzer = PythonAnalyzer(
        client=genai_client,
        cache=cache,
        rate_limiter=rate_limiter
    )
    
    js_analyzer = JavaScriptAnalyzer(
        client=genai_client,
        cache=cache,
        rate_limiter=rate_limiter
    )
    
    # Scan and analyze project
    print(f"\nScanning project: {project_path}")
    aggregated_ladom = scan_and_analyze(
        project_path, config, py_analyzer, js_analyzer
    )
    
    if not aggregated_ladom or not aggregated_ladom.get('files'):
        logger.error("No files were successfully analyzed")
        print("\nError: No supported files found or analysis failed")
        return
    
    # Generate documentation
    print("\nGenerating documentation...")
    project_name = os.path.basename(os.path.abspath(project_path))
    success = generate_documentation(aggregated_ladom, config, project_name)
    
    if success:
        print("\n" + "=" * 60)
        print("  ✓ Documentation generated successfully!")
        print("=" * 60)
        
        # Print cache statistics
        cache_stats = cache.get_stats()
        if cache_stats['enabled']:
            print(f"\nCache statistics:")
            print(f"  - Total entries: {cache_stats['total_entries']}")
            print(f"  - Cache file: {cache_stats['cache_file']}")
        
        # Print rate limiter statistics
        rate_stats = rate_limiter.get_stats()
        print(f"\nAPI calls made: {rate_stats['total_calls']}")
    else:
        print("\n✗ Documentation generation failed. Check logs for details.")
        logger.error("Documentation generation failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        logger.info("Operation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.exception("Unexpected error in main")