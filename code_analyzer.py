import ast
import os
import sys
import re
from google import genai
from dotenv import load_dotenv
import esprima

# Global variable to store the documentation content
documentation_content = ""

def generate_ai_docstring(code_snippet, client, lang="python"):
    """
    Generates a docstring for a code snippet by calling the Gemini API.
    """
    if lang == "python":
        prompt = (
            f"You are a helpful AI assistant tasked with generating docstrings for Python code. "
            f"Analyze the following function or class and generate a comprehensive docstring for it in the Google style. "
            f"Include a brief description, an Args section for each parameter, and a Returns section for the return value.\n\n"
            f"Code:\n```python\n{code_snippet}\n```\n\n"
            f"Provide ONLY the docstring text as your output. Do NOT enclose it in triple quotes or a code block."
        )
    elif lang == "javascript":
        prompt = (
            f"You are a helpful AI assistant tasked with generating JSDoc comments for JavaScript code. "
            f"Analyze the following function or class and generate a comprehensive JSDoc comment for it. "
            f"Include a brief description, an @param section for each parameter, and a @returns section for the return value.\n\n"
            f"Code:\n```javascript\n{code_snippet}\n```\n\n"
            f"Provide ONLY the JSDoc comment text as your output, starting with `/**` and ending with `*/`."
        )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        # Sanitize the AI's response
        text_output = response.text.strip()
        if text_output.startswith('"""') and text_output.endswith('"""'):
            text_output = text_output.strip('"""').strip()
        if text_output.startswith('```') and text_output.endswith('```'):
            text_output = text_output.split('\n', 1)[-1]
            if text_output.endswith('```'):
                text_output = text_output[:-3].strip()
        
        return text_output

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return f"AI documentation failed to generate due to an API error: {e}"

def parse_py_docstring(docstring):
    """
    Parses a Python docstring to extract Args and Returns sections.
    """
    if not docstring:
        return {}, {} 

    args = {}
    returns = {}
    
    args_section_match = re.search(r'Args:\s*?\n(.*?)(?:\n\s*Returns:|\n\s*Raises:|$)', docstring, re.DOTALL)
    if args_section_match:
        args_text = args_section_match.group(1).strip()
        lines = re.split(r'\n\s*[\*-]\s*', args_text)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'(\w+)\s*(?:\((.*?)\))?:\s*(.*)', line)
            if match:
                param_name, param_type, param_desc = match.groups()
                args[param_name] = {'type': param_type.strip() if param_type else None, 'desc': param_desc.strip()}
            else:
                simple_match = re.match(r'(\w+)\s*:\s*(.*)', line)
                if simple_match:
                    param_name, param_desc = simple_match.groups()
                    args[param_name] = {'type': None, 'desc': param_desc.strip()}

    returns_section_match = re.search(r'Returns:\s*?\n(.*?)(?:\n\s*Raises:|$)', docstring, re.DOTALL)
    if returns_section_match:
        return_line = returns_section_match.group(1).strip()
        match = re.match(r'(.*?):\s*(.*)', return_line)
        if match:
            return_type, return_desc = match.groups()
            returns = {'type': return_type.strip(), 'desc': return_desc.strip()}
        else:
            returns = {'type': None, 'desc': return_line.strip()}

    return args, returns

def parse_js_docstring(docstring):
    """
    Parses a JSDoc comment to extract @param and @returns sections.
    """
    if not docstring:
        return {}, {}, ""
    
    args = {}
    returns = {}
    description = ""
    
    # Clean up common AI-generated formatting issues
    docstring = docstring.replace('`', '')
    docstring = docstring.replace('* @returns', '@returns')
    docstring = docstring.replace('* @param', '@param')
    
    # Extract the main description
    desc_match = re.search(r'/\*\*\s*([\s\S]*?)(?=@|\*/)', docstring)
    if desc_match:
        description = desc_match.group(1).replace('\n * ', ' ').strip()
        
    # Extract @param tags
    param_tags = re.findall(r'@param\s+({[^}]+})?\s*([^-\s]+)(?:\s*-\s*([\s\S]*?)(?=\n\s*@|$))', docstring)
    for tag in param_tags:
        param_type, param_name, param_desc = tag
        param_type = param_type.strip('{}')
        param_name = param_name.strip()
        param_desc = param_desc.strip().replace('\n * ', ' ')
        args[param_name] = {'type': param_type, 'desc': param_desc}

    # Extract @returns tag
    returns_tag = re.search(r'@returns\s+({[^}]+})?\s*([\s\S]*)', docstring)
    if returns_tag:
        return_type, return_desc = returns_tag.groups()
        return_type = return_type.strip('{}') if return_type else 'any'
        return_desc = return_desc.strip().replace('\n * ', ' ')
        returns = {'type': return_type, 'desc': return_desc}
    
    return args, returns, description

def find_py_docstring(node, client):
    """
    A helper function to find an existing Python docstring or generate one with AI.
    """
    docstring = ast.get_docstring(node)
    if not docstring:
        print(f"  - Generating docstring for `{node.name}`...")
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
            source_code = ast.unparse(node)
            if not source_code:
                return ""
            docstring = generate_ai_docstring(source_code, client, lang="python")
    return docstring

def find_js_docstring(node, source_code, client):
    """
    A helper function to find an existing JSDoc comment or generate one with AI.
    """
    # First, try to find an existing JSDoc comment
    if hasattr(node, 'leadingComments') and node.leadingComments:
        # Check for the last JSDoc block comment before the node
        for comment in reversed(node.leadingComments):
            if comment.type == 'Block' and comment.value.strip().startswith('*'):
                return f"/**{comment.value}*/"
    
    # If no valid JSDoc comment is found, generate one with AI.
    node_name = node.id.name if hasattr(node, 'id') and hasattr(node.id, 'name') else 'anonymous'
    print(f"  - Generating JSDoc for `{node_name}`...")
    if hasattr(node, 'range'):
        code_snippet = source_code[node.range[0]:node.range[1]]
    else:
        return "" # Cannot extract code without range info
        
    return generate_ai_docstring(code_snippet, client, lang="javascript")

def analyze_python_file(file_path, client):
    """
    Parses a Python file and generates rich documentation content.
    """
    global documentation_content
    print(f"Analyzing Python file: {os.path.basename(file_path)}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return

    tree = ast.parse(source_code)
    file_name = os.path.basename(file_path)
    documentation_content += f"\n---\n\n# `{file_name}`\n\n"
    
    module_docstring = ast.get_docstring(tree)
    if not module_docstring:
      print(f"  - Generating module docstring...")
      module_docstring = generate_ai_docstring(source_code[:1000], client, lang="python") 
    
    if module_docstring:
        documentation_content += f"**Module Description:**\n```\n{module_docstring.strip()}\n```\n\n"
    else:
        documentation_content += "*No documentation found.*\n\n"

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            docstring = find_py_docstring(node, client)
            parsed_args, parsed_returns = parse_py_docstring(docstring)

            params = [f"{arg.arg}: {ast.unparse(arg.annotation) if arg.annotation else 'any'}" for arg in node.args.args]
            params_str = ", ".join(params)
            
            documentation_content += f"### Function: `{node.name}({params_str})`\n"
            
            if docstring:
                brief_desc = docstring.strip().split('\n')[0]
                documentation_content += f"**Description:** {brief_desc}\n\n"
            
            if parsed_args:
                documentation_content += "**Parameters:**\n"
                for arg_name, details in parsed_args.items():
                    doc_type = f"({details['type']})" if details['type'] else ""
                    documentation_content += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                documentation_content += "\n"

            if parsed_returns:
                returns_type = f"({parsed_returns['type']})" if parsed_returns['type'] else ""
                documentation_content += f"**Returns** {returns_type}:\n"
                documentation_content += f"  {parsed_returns['desc']}\n\n"

            if not docstring and not parsed_args and not parsed_returns:
                documentation_content += "*No documentation found.*\n\n"

        elif isinstance(node, ast.ClassDef):
            docstring = find_py_docstring(node, client)
            documentation_content += f"### Class: `{node.name}`\n"
            if docstring:
                documentation_content += f"**Description:**\n```\n{docstring.strip()}\n```\n\n"
            else:
                documentation_content += "*No documentation found.*\n\n"
            
            class_variables = [f"  - `{target.id}` = `{ast.unparse(node.value)}`" for sub_node in node.body if isinstance(sub_node, ast.Assign) for target in sub_node.targets if isinstance(target, ast.Name)]
            if class_variables:
                documentation_content += "**Class Variables:**\n" + "\n".join(class_variables) + "\n\n"

            for sub_node in node.body:
                if isinstance(sub_node, ast.FunctionDef):
                    method_name = sub_node.name
                    method_docstring = find_py_docstring(sub_node, client)
                    parsed_args, parsed_returns = parse_py_docstring(method_docstring)
                    
                    method_params = [f"{arg.arg}: {ast.unparse(arg.annotation) if arg.annotation else 'any'}" for arg in sub_node.args.args if arg.arg != 'self']
                    method_params_str = ", ".join(method_params)
                    
                    documentation_content += f"#### Method: `{method_name}({method_params_str})`\n"

                    if method_docstring:
                        brief_desc = method_docstring.strip().split('\n')[0]
                        documentation_content += f"**Description:** {brief_desc}\n\n"

                    if parsed_args:
                        documentation_content += "**Parameters:**\n"
                        for arg_name, details in parsed_args.items():
                            doc_type = f"({details['type']})" if details['type'] else ""
                            documentation_content += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                        documentation_content += "\n"
                    
                    if parsed_returns:
                        returns_type = f"({parsed_returns['type']})" if parsed_returns['type'] else ""
                        documentation_content += f"**Returns** {returns_type}:\n"
                        documentation_content += f"  {parsed_returns['desc']}\n\n"

                    if not method_docstring and not parsed_args and not parsed_returns:
                        documentation_content += "*No documentation found.*\n\n"

def analyze_javascript_file(file_path, client):
    """
    Parses a JavaScript file and generates rich documentation content.
    """
    global documentation_content
    print(f"Analyzing JavaScript file: {os.path.basename(file_path)}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return

    try:
        tree = esprima.parse(source_code, {'loc': True, 'range': True, 'attachComment': True})
    except esprima.Error as e:
        print(f"Error parsing JavaScript file {file_path}: {e}")
        return
        
    file_name = os.path.basename(file_path)
    documentation_content += f"\n---\n\n# `{file_name}`\n\n"

    # Process all top-level declarations
    for node in tree.body:
        # Document classes
        if node.type == 'ClassDeclaration':
            docstring = find_js_docstring(node, source_code, client)
            parsed_args, parsed_returns, brief_desc = parse_js_docstring(docstring)
            
            documentation_content += f"### Class: `{node.id.name}`\n"
            if brief_desc:
                documentation_content += f"**Description:** {brief_desc}\n\n"
            else:
                documentation_content += "*No documentation found.*\n\n"
                
            for method in node.body.body:
                if method.type == 'MethodDefinition':
                    method_docstring = find_js_docstring(method, source_code, client)
                    parsed_args, parsed_returns, brief_desc = parse_js_docstring(method_docstring)
                    
                    method_name = method.key.name
                    method_params = []
                    if method.value and method.value.params:
                        for param in method.value.params:
                            if param.type == 'Identifier':
                                method_params.append(param.name)
                            elif hasattr(param, 'range'):
                                method_params.append(source_code[param.range[0]:param.range[1]])
                    params_str = ", ".join(method_params)
                    
                    documentation_content += f"#### Method: `{method_name}({params_str})`\n"

                    if brief_desc:
                        documentation_content += f"**Description:** {brief_desc}\n\n"
                    
                    if parsed_args:
                        documentation_content += "**Parameters:**\n"
                        for arg_name, details in parsed_args.items():
                            doc_type = f"({details['type']})" if details['type'] else ""
                            documentation_content += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                        documentation_content += "\n"

                    if parsed_returns:
                        returns_type = f"({parsed_returns['type']})" if parsed_returns['type'] else ""
                        documentation_content += f"**Returns** {returns_type}:\n"
                        documentation_content += f"  {parsed_returns['desc']}\n\n"

                    if not method_docstring:
                        documentation_content += "*No documentation found.*\n\n"

        # Document functions
        elif node.type == 'FunctionDeclaration':
            func_node = node
            func_name = node.id.name
            
            docstring = find_js_docstring(func_node, source_code, client)
            parsed_args, parsed_returns, brief_desc = parse_js_docstring(docstring)

            func_params = []
            if func_node.params:
                for param in func_node.params:
                    if param.type == 'Identifier':
                        func_params.append(param.name)
                    elif hasattr(param, 'range'):
                        func_params.append(source_code[param.range[0]:param.range[1]])
            params_str = ", ".join(func_params)
            
            documentation_content += f"### Function: `{func_name}({params_str})`\n"
            
            if brief_desc:
                documentation_content += f"**Description:** {brief_desc}\n\n"

            if parsed_args:
                documentation_content += "**Parameters:**\n"
                for arg_name, details in parsed_args.items():
                    doc_type = f"({details['type']})" if details['type'] else ""
                    documentation_content += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                documentation_content += "\n"

            if parsed_returns:
                returns_type = f"({parsed_returns['type']})" if parsed_returns['type'] else ""
                documentation_content += f"**Returns** {returns_type}:\n"
                documentation_content += f"  {parsed_returns['desc']}\n\n"

            if not docstring:
                documentation_content += "*No documentation found.*\n\n"

        # Document functions defined as variable assignments (e.g., const myFunction = () => {})
        elif node.type == 'VariableDeclaration':
            for declaration in node.declarations:
                if declaration.init and (declaration.init.type == 'FunctionExpression' or declaration.init.type == 'ArrowFunctionExpression'):
                    func_node = declaration.init
                    func_name = declaration.id.name

                    docstring = find_js_docstring(func_node, source_code, client)
                    parsed_args, parsed_returns, brief_desc = parse_js_docstring(docstring)

                    func_params = []
                    if func_node.params:
                        for param in func_node.params:
                            if param.type == 'Identifier':
                                func_params.append(param.name)
                            elif hasattr(param, 'range'):
                                func_params.append(source_code[param.range[0]:param.range[1]])
                    params_str = ", ".join(func_params)
                    
                    documentation_content += f"### Function: `{func_name}({params_str})`\n"
                    
                    if brief_desc:
                        documentation_content += f"**Description:** {brief_desc}\n\n"

                    if parsed_args:
                        documentation_content += "**Parameters:**\n"
                        for arg_name, details in parsed_args.items():
                            doc_type = f"({details['type']})" if details['type'] else ""
                            documentation_content += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                        documentation_content += "\n"

                    if parsed_returns:
                        returns_type = f"({parsed_returns['type']})" if parsed_returns['type'] else ""
                        documentation_content += f"**Returns** {returns_type}:\n"
                        documentation_content += f"  {parsed_returns['desc']}\n\n"
                    
                    if not docstring:
                        documentation_content += "*No documentation found.*\n\n"


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
        # Exclude node_modules from the list of directories to visit
        dirs[:] = [d for d in dirs if d != 'node_modules']

        for file in files:
            if file.endswith('.py') or file.endswith('.js'):
                file_list.append(os.path.join(root, file))
    
    if not file_list:
        print(f"No Python or JavaScript files found in {directory} or its subdirectories.")
    
    return file_list

def write_documentation_to_file(filename, output_path):
    """
    Writes the generated documentation content to a file in the specified format.
    """
    global documentation_content
    
    if not documentation_content:
        print("No content to write. Documentation was not generated.")
        return

    full_path = os.path.join(output_path, filename)
    
    try:
        os.makedirs(output_path, exist_ok=True)
        with open(full_path, 'w', encoding='utf8') as f:
            f.write(documentation_content)
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
        print("Please create a .env file in this directory with the content:")
        print('  GEMINI_API_KEY="YOUR_API_KEY"')
        print("and try again.")
        sys.exit(1)
    
    client = genai.Client()

    while True:
        print("\n===== Automated Documentation Generator =====")
        print("1. Scan a project directory and generate documentation")
        print("2. Exit")
        
        choice = input("Enter your choice (1 or 2): ")
        
        if choice == '1':
            global documentation_content
            documentation_content = ""
            
            project_directory = input("Enter the path to the project directory: ")
            
            all_files = find_project_files(project_directory)

            if not all_files:
                print(f"No Python or JavaScript files found in {project_directory} or its subdirectories.")
                continue

            for file_path in all_files:
                if file_path.endswith('.py'):
                    analyze_python_file(file_path, client)
                elif file_path.endswith('.js'):
                    analyze_javascript_file(file_path, client)
            
            # New logic for output path and file name
            documentation_base_dir = "Documentation"
            project_name = os.path.basename(os.path.normpath(project_directory))
            output_path = os.path.join(documentation_base_dir, project_name)
            output_filename = "README.md"

            print("-" * 40)
            write_documentation_to_file(output_filename, output_path)
            print("-" * 40)
            
        elif choice == '2':
            print("Exiting the application. Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main_menu()