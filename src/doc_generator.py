# src/doc_generator.py

"""
Documentation generator using template-based rendering.
Converts LADOM structures into formatted documentation.
"""

import os
import logging
from jinja2 import Template, Environment, BaseLoader
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown documentation from LADOM structures."""
    
    # Default Markdown template
    DEFAULT_TEMPLATE = """# {{ project_name }}

Generated documentation for the project.

---
{% for file in files %}
## File: `{{ file.path | basename }}`

**Path:** `{{ file.path }}`

{% if file.functions %}
### Functions

{% for func in file.functions %}
#### `{{ func.name }}({% for param in func.parameters %}{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})`

{{ func.description }}

{% if func.parameters %}
**Parameters:**

{% for param in func.parameters %}
- `{{ param.name }}` *({%  if param.type %}{{ param.type }}{% else %}any{% endif %})* - {{ param.description }}
{% endfor %}
{% endif %}

**Returns:** *{% if func.returns.type %}{{ func.returns.type }}{% else %}void{% endif %}*
{% if func.returns.description %}
{{ func.returns.description }}
{% endif %}

---
{% endfor %}
{% endif %}

{% if file.classes %}
### Classes

{% for cls in file.classes %}
#### Class: `{{ cls.name }}`

{{ cls.description }}

{% if cls.methods %}
**Methods:**

{% for method in cls.methods %}
##### `{{ method.name }}({% for param in method.parameters %}{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})`

{{ method.description }}

{% if method.parameters %}
**Parameters:**

{% for param in method.parameters %}
- `{{ param.name }}` *({% if param.type %}{{ param.type }}{% else %}any{% endif %})* - {{ param.description }}
{% endfor %}
{% endif %}

**Returns:** *{% if method.returns.type %}{{ method.returns.type }}{% else %}void{% endif %}*
{% if method.returns.description %}
{{ method.returns.description }}
{% endif %}

---
{% endfor %}
{% endif %}
{% endfor %}
{% endif %}

{% endfor %}
"""
    
    def __init__(self, template: str = None):
        """
        Initialize the markdown generator.
        
        Args:
            template: Optional custom Jinja2 template string
        """
        self.template_str = template or self.DEFAULT_TEMPLATE
        self.env = Environment(loader=BaseLoader())
        
        # Add custom filters
        self.env.filters['basename'] = os.path.basename
        
        try:
            self.template = self.env.from_string(self.template_str)
            logger.debug("Markdown template loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            raise
    
    def generate(self, aggregated_ladom: Dict[str, Any], output_path: str) -> str:
        """
        Generate markdown documentation from LADOM structure.
        
        Args:
            aggregated_ladom: Complete LADOM structure
            output_path: Path where markdown file should be saved
            
        Returns:
            Generated markdown content
        """
        try:
            # Render the template
            markdown_output = self.template.render(
                project_name=aggregated_ladom.get('project_name', 'Project Documentation'),
                files=aggregated_ladom.get('files', [])
            )
            
            # Write to file
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_output)
            
            logger.info(f"Documentation generated successfully: {output_path}")
            return markdown_output
            
        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            raise


class HTMLGenerator:
    """Generates HTML documentation from LADOM structures."""
    
    DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project_name }} - Documentation</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }
        .file-section {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .function, .class {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            border-radius: 3px;
        }
        .method {
            margin: 15px 0 15px 20px;
            padding: 10px;
            background: #e9ecef;
            border-left: 3px solid #95a5a6;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .params, .returns {
            margin: 10px 0;
        }
        .param-item {
            margin: 5px 0;
            padding-left: 20px;
        }
        h1, h2, h3, h4 {
            color: #2c3e50;
        }
        .type {
            color: #e74c3c;
            font-style: italic;
        }
    </style>
</head>
<body>
    <header>
        <h1>{{ project_name }}</h1>
        <p>Auto-generated documentation</p>
    </header>
    
    {% for file in files %}
    <div class="file-section">
        <h2>📄 {{ file.path | basename }}</h2>
        <p><strong>Path:</strong> <code>{{ file.path }}</code></p>
        
        {% if file.functions %}
        <h3>Functions</h3>
        {% for func in file.functions %}
        <div class="function">
            <h4><code>{{ func.name }}({% for param in func.parameters %}{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})</code></h4>
            <p>{{ func.description }}</p>
            
            {% if func.parameters %}
            <div class="params">
                <strong>Parameters:</strong>
                {% for param in func.parameters %}
                <div class="param-item">
                    <code>{{ param.name }}</code> 
                    <span class="type">({{ param.type or 'any' }})</span> - 
                    {{ param.description }}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="returns">
                <strong>Returns:</strong> 
                <span class="type">({{ func.returns.type or 'void' }})</span>
                {% if func.returns.description %}
                - {{ func.returns.description }}
                {% endif %}
            </div>
        </div>
        {% endfor %}
        {% endif %}
        
        {% if file.classes %}
        <h3>Classes</h3>
        {% for cls in file.classes %}
        <div class="class">
            <h4>Class: <code>{{ cls.name }}</code></h4>
            <p>{{ cls.description }}</p>
            
            {% if cls.methods %}
            <strong>Methods:</strong>
            {% for method in cls.methods %}
            <div class="method">
                <h5><code>{{ method.name }}({% for param in method.parameters %}{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})</code></h5>
                <p>{{ method.description }}</p>
                
                {% if method.parameters %}
                <div class="params">
                    <strong>Parameters:</strong>
                    {% for param in method.parameters %}
                    <div class="param-item">
                        <code>{{ param.name }}</code> 
                        <span class="type">({{ param.type or 'any' }})</span> - 
                        {{ param.description }}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <div class="returns">
                    <strong>Returns:</strong> 
                    <span class="type">({{ method.returns.type or 'void' }})</span>
                    {% if method.returns.description %}
                    - {{ method.returns.description }}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
"""
    
    def __init__(self, template: str = None):
        """
        Initialize the HTML generator.
        
        Args:
            template: Optional custom Jinja2 template string
        """
        self.template_str = template or self.DEFAULT_TEMPLATE
        self.env = Environment(loader=BaseLoader())
        self.env.filters['basename'] = os.path.basename
        
        try:
            self.template = self.env.from_string(self.template_str)
            logger.debug("HTML template loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load HTML template: {e}")
            raise
    
    def generate(self, aggregated_ladom: Dict[str, Any], output_path: str) -> str:
        """
        Generate HTML documentation from LADOM structure.
        
        Args:
            aggregated_ladom: Complete LADOM structure
            output_path: Path where HTML file should be saved
            
        Returns:
            Generated HTML content
        """
        try:
            html_output = self.template.render(
                project_name=aggregated_ladom.get('project_name', 'Project Documentation'),
                files=aggregated_ladom.get('files', [])
            )
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_output)
            
            logger.info(f"HTML documentation generated: {output_path}")
            return html_output
            
        except Exception as e:
            logger.error(f"Failed to generate HTML documentation: {e}")
            raise