# src/doc_generator.py

class MarkdownGenerator:
    def generate(self, python_data, js_data):
        """
        Combines structured documentation data into a single markdown string.
        """
        markdown_output = ""
        
        # --- Python Documentation ---
        for file_data in python_data:
            markdown_output += f"\n---\n\n# `{file_data['file_name']}`\n\n"
            if file_data['module_docstring']:
                markdown_output += f"**Module Description:**\n```\n{file_data['module_docstring'].strip()}\n```\n\n"

            for func in file_data['functions']:
                params_str = ", ".join(func['params'])
                markdown_output += f"### Function: `{func['name']}({params_str})`\n"
                if func['docstring']:
                    brief_desc = func['docstring'].strip().split('\n')[0]
                    markdown_output += f"**Description:** {brief_desc}\n\n"
                
                if func['parsed_args']:
                    markdown_output += "**Parameters:**\n"
                    for arg_name, details in func['parsed_args'].items():
                        doc_type = f"({details['type']})" if details['type'] else ""
                        markdown_output += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                    markdown_output += "\n"

                if func['parsed_returns']:
                    returns_type = f"({func['parsed_returns']['type']})" if func['parsed_returns']['type'] else ""
                    markdown_output += f"**Returns** {returns_type}:\n"
                    markdown_output += f"  {func['parsed_returns']['desc']}\n\n"
            
            for class_data in file_data['classes']:
                markdown_output += f"### Class: `{class_data['name']}`\n"
                if class_data['docstring']:
                    markdown_output += f"**Description:**\n```\n{class_data['docstring'].strip()}\n```\n\n"

                for method in class_data['methods']:
                    method_params_str = ", ".join(method['params'])
                    markdown_output += f"#### Method: `{method['name']}({method_params_str})`\n"
                    if method['docstring']:
                        brief_desc = method['docstring'].strip().split('\n')[0]
                        markdown_output += f"**Description:** {brief_desc}\n\n"

                    if method['parsed_args']:
                        markdown_output += "**Parameters:**\n"
                        for arg_name, details in method['parsed_args'].items():
                            doc_type = f"({details['type']})" if details['type'] else ""
                            markdown_output += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                        markdown_output += "\n"
                    
                    if method['parsed_returns']:
                        returns_type = f"({method['parsed_returns']['type']})" if method['parsed_returns']['type'] else ""
                        markdown_output += f"**Returns** {returns_type}:\n"
                        markdown_output += f"  {method['parsed_returns']['desc']}\n\n"

        # --- JavaScript Documentation ---
        for file_data in js_data:
            markdown_output += f"\n---\n\n# `{file_data['file_name']}`\n\n"

            for func in file_data['functions']:
                params_str = ", ".join(func['params'])
                markdown_output += f"### Function: `{func['name']}({params_str})`\n"
                if func['description']:
                    markdown_output += f"**Description:** {func['description']}\n\n"
                
                if func['parsed_args']:
                    markdown_output += "**Parameters:**\n"
                    for arg_name, details in func['parsed_args'].items():
                        doc_type = f"({details['type']})" if details['type'] else ""
                        markdown_output += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                    markdown_output += "\n"

                if func['parsed_returns']:
                    returns_type = f"({func['parsed_returns']['type']})" if func['parsed_returns']['type'] else ""
                    markdown_output += f"**Returns** {returns_type}:\n"
                    markdown_output += f"  {func['parsed_returns']['desc']}\n\n"
            
            for class_data in file_data['classes']:
                markdown_output += f"### Class: `{class_data['name']}`\n"
                if class_data['description']:
                    markdown_output += f"**Description:** {class_data['description']}\n\n"

                for method in class_data['methods']:
                    method_params_str = ", ".join(method['params'])
                    markdown_output += f"#### Method: `{method['name']}({method_params_str})`\n"
                    if method['description']:
                        markdown_output += f"**Description:** {method['description']}\n\n"

                    if method['parsed_args']:
                        markdown_output += "**Parameters:**\n"
                        for arg_name, details in method['parsed_args'].items():
                            doc_type = f"({details['type']})" if details['type'] else ""
                            markdown_output += f"  - `{arg_name}` {doc_type}: {details['desc']}\n"
                        markdown_output += "\n"
                    
                    if method['parsed_returns']:
                        returns_type = f"({method['parsed_returns']['type']})" if method['parsed_returns']['type'] else ""
                        markdown_output += f"**Returns** {returns_type}:\n"
                        markdown_output += f"  {method['parsed_returns']['desc']}\n\n"

        return markdown_output