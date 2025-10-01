# src/main.py

import os
from google import genai
from dotenv import load_dotenv
from .analyzers.py_analyzer import PythonAnalyzer
from .analyzers.js_analyzer import JavaScriptAnalyzer
from .doc_generator import MarkdownGenerator

# A list of directory names to exclude from the scan
EXCLUDE_DIRS = [
    'node_modules',
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'dist',
    'build',
    '.vscode',
    '.idea'
]

# The name of the main documentation directory
DOCS_DIR = 'Documentation'

def main():
    """
    Main orchestration function. Scans project, analyzes files, and generates documentation.
    """
    # Load environment variables from .env file
    load_dotenv()

    project_path = input("Enter the project path to scan: ")
    if not os.path.isdir(project_path):
        print("Invalid path. Please enter a valid directory.")
        return
    
    # Get the project name from the path
    project_name = os.path.basename(os.path.abspath(project_path))

    genai_client = genai.Client();
    # Initialize analyzers and generator
    py_analyzer = PythonAnalyzer(client=genai_client)
    js_analyzer = JavaScriptAnalyzer(client=genai_client)
    doc_generator = MarkdownGenerator()

    aggregated_ladom = {
        "project_name": project_name,
        "files": []
    }

    print("Scanning project and analyzing files...")

    for root, dirs, files in os.walk(project_path):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            file_path = os.path.join(root, file)
            
            # Use appropriate analyzer based on file extension
            if file.endswith('.py'):
                print(f"  - Analyzing Python file: {file}")
                ladom_data = py_analyzer.analyze(file_path)
                if ladom_data:
                    # Append file data from the analyzer's LADOM to the aggregated LADOM
                    aggregated_ladom['files'].extend(ladom_data['files'])
            elif file.endswith('.js'):
                print(f"  - Analyzing JavaScript file: {file}")
                ladom_data = js_analyzer.analyze(file_path)
                if ladom_data:
                    # Append file data from the analyzer's LADOM to the aggregated LADOM
                    aggregated_ladom['files'].extend(ladom_data['files'])

    if not aggregated_ladom['files']:
        print("No supported files found to document.")
        return

    # Create the output directory path
    output_dir = os.path.join(DOCS_DIR, project_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Define the final output file path
    output_path = os.path.join(output_dir, "documentation.md")
    
    print(f"\nGenerating final documentation to {output_path}...")
    
    # Pass the single, aggregated LADOM to the generator
    doc_generator.generate(aggregated_ladom, output_path)

if __name__ == "__main__":
    main()