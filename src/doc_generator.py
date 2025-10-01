# src/doc_generator.py

import os

class MarkdownGenerator:
    """
    Generates a single markdown file from the aggregated Language-Agnostic Document Object Model (LADOM).
    """
    def generate(self, aggregated_ladom, output_path):
        """
        Combines structured documentation data into a single markdown string and writes it to a file.
        
        Args:
            aggregated_ladom (dict): The complete LADOM structure containing all files.
            output_path (str): The file path where the markdown should be saved.
        
        Returns:
            str: The final markdown content string.
        """
        project_name = aggregated_ladom.get('project_name', 'Project Documentation')
        markdown_output = f"# {project_name}\n\n"

        # Iterate over all files in the aggregated LADOM
        for file_data in aggregated_ladom.get('files', []):
            # Use 'path' key as defined in js_analyzer.py
            file_name = os.path.basename(file_data.get('path', 'unknown_file'))
            markdown_output += f"\n---\n\n## File: `{file_name}`\n\n"

            # --- Process Functions (if any) ---
            for func in file_data.get('functions', []):
                params_str = ", ".join(func.get('params', []))
                markdown_output += f"### Function: `{func['name']}({params_str})`\n"
                
                # Function Description
                if func.get('description'):
                    markdown_output += f"**Description:** {func['description']}\n\n"
                
                # Function Parameters
                if func.get('parsed_args'):
                    markdown_output += "**Parameters:**\n"
                    for arg_name, details in func['parsed_args'].items():
                        doc_type = f"({details.get('type', 'any')})" if details.get('type') else ""
                        markdown_output += f"  - `{arg_name}` {doc_type}: {details.get('desc', 'No description available.')}\n"
                    markdown_output += "\n"

                # Function Returns
                if func.get('parsed_returns'):
                    returns_type = f"({func['parsed_returns'].get('type', 'void')})" if func['parsed_returns'].get('type') else ""
                    markdown_output += f"**Returns** {returns_type}:\n"
                    markdown_output += f"  {func['parsed_returns'].get('desc', 'No return description available.')}\n\n"

            # --- Process Classes and Methods (JavaScript/Class Logic) ---
            for class_data in file_data.get('classes', []):
                markdown_output += f"### Class: `{class_data['name']}`\n"
                
                # Class Description
                if class_data.get('description'):
                    markdown_output += f"**Description:** {class_data['description']}\n\n"

                for method in class_data.get('methods', []):
                    # Method Header (Name and Parameters from the method signature)
                    method_params_str = ", ".join(method.get('params', []))
                    markdown_output += f"#### Method: `{method['name']}({method_params_str})`\n"
                    
                    # Method Description
                    if method.get('description'):
                        markdown_output += f"**Description:** {method['description']}\n\n"

                    # Method Parameters (Parsed JSDoc details)
                    if method.get('parsed_args'):
                        markdown_output += "**Parameters:**\n"
                        for arg_name, details in method['parsed_args'].items():
                            # Check for complex types like object destructuring if the name is not in the parsed args
                            param_name_display = arg_name.strip('[]') 
                            doc_type = f"({details.get('type', 'any')})" if details.get('type') else ""
                            markdown_output += f"  - `{param_name_display}` {doc_type}: {details.get('desc', 'No description available.')}\n"
                        markdown_output += "\n"
                    
                    # Method Returns (Parsed JSDoc details)
                    if method.get('parsed_returns'):
                        returns_type = f"({method['parsed_returns'].get('type', 'void')})" if method['parsed_returns'].get('type') else ""
                        
                        # Only print 'Returns' section if there is a type or a description
                        if returns_type != '(void)' or method['parsed_returns'].get('desc'):
                            markdown_output += f"**Returns** {returns_type}:\n"
                            markdown_output += f"  {method['parsed_returns'].get('desc', 'No return description available.')}\n\n"

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)
            
        return markdown_output
