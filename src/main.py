# src/main.py

import os
import sys
from dotenv import load_dotenv
from google import genai

from .analyzers.python_analyzer import PythonAnalyzer
from .analyzers.js_analyzer import JavaScriptAnalyzer
from .doc_generator import MarkdownGenerator

def find_project_files(directory):
    """
    Walks through a directory and returns a list of all .py and .js files,
    ignoring the node_modules directory.
    """
    file_list = []
    if not os.path.isdir(directory):
        print(f"Error: Directory not found at {directory}")
        return file_list

    print(f"Scanning directory: {directory}")
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d != 'node_modules']

        for file in files:
            if file.endswith('.py') or file.endswith('.js'):
                file_list.append(os.path.join(root, file))
    
    if not file_list:
        print(f"No Python or JavaScript files found in {directory} or its subdirectories.")
    
    return file_list

def write_documentation_to_file(filename, output_path, content):
    """
    Writes the generated documentation content to a file.
    """
    if not content:
        print("No content to write. Documentation was not generated.")
        return

    full_path = os.path.join(output_path, filename)
    
    try:
        os.makedirs(output_path, exist_ok=True)
        with open(full_path, 'w', encoding='utf8') as f:
            f.write(content)
        print(f"Documentation successfully generated and saved to `{full_path}`")
    except Exception as e:
        print(f"Error writing to file {full_path}: {e}")

def main_menu():
    """
    Displays the main menu and handles user input.
    """
    load_dotenv()
    
    if "GEMINI_API_KEY" not in os.environ:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please create a .env file in the root directory with the content:")
        print('  GEMINI_API_KEY="YOUR_API_KEY"')
        sys.exit(1)
    
    client = genai.Client()

    while True:
        print("\n===== Automated Documentation Generator =====")
        print("1. Scan a project directory and generate documentation")
        print("2. Exit")
        
        choice = input("Enter your choice (1 or 2): ")
        
        if choice == '1':
            project_directory = input("Enter the path to the project directory: ")
            
            all_files = find_project_files(project_directory)

            if not all_files:
                continue
            
            # Initialize analyzers and documentation generator
            python_analyzer = PythonAnalyzer(client)
            js_analyzer = JavaScriptAnalyzer(client)
            doc_generator = MarkdownGenerator()

            python_docs = []
            js_docs = []
            
            # Analyze each file and collect documentation data
            for file_path in all_files:
                if file_path.endswith('.py'):
                    doc_data = python_analyzer.analyze(file_path)
                    if doc_data:
                        python_docs.append(doc_data)
                elif file_path.endswith('.js'):
                    doc_data = js_analyzer.analyze(file_path)
                    if doc_data:
                        js_docs.append(doc_data)
            
            # Generate the final markdown content
            final_markdown_content = doc_generator.generate(python_docs, js_docs)
            
            # Determine output path and filename
            documentation_base_dir = "Documentation"
            project_name = os.path.basename(os.path.normpath(project_directory))
            output_path = os.path.join(documentation_base_dir, project_name)
            output_filename = "README.md"

            print("-" * 40)
            write_documentation_to_file(output_filename, output_path, final_markdown_content)
            print("-" * 40)
            
        elif choice == '2':
            print("Exiting the application. Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main_menu()