# src/readme_generator.py
"""
Comprehensive README generator that creates in-depth project documentation.

This generator produces a complete README.md file with:
- Project overview and description
- Architecture diagrams
- Directory structure explanation
- Setup and installation instructions
- Usage examples and API documentation
- Development guide
- Testing information
- Troubleshooting tips
"""

from __future__ import annotations
import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .providers.ollama_client import LLM
from .project_analyzer import ProjectAnalyzer
from .utils.diagram_generator import DiagramGenerator
from .utils.example_extractor import ExampleExtractor
from .utils.html_renderer import HTMLRenderer

logger = logging.getLogger(__name__)


class ReadmeGenerator:
    """
    Generates comprehensive README documentation using LLM with rich context.
    
    This generator goes beyond basic documentation to create README files
    that are informative, well-structured, and include visual diagrams.
    """

    def __init__(self, llm_client: LLM):
        """
        Initialize the README generator.
        
        Args:
            llm_client: LLM client for generating documentation
        """
        self.llm = llm_client

    def generate(
        self, 
        ladom_data: Dict[str, Any], 
        project_path: str,
        output_path: str
    ) -> None:
        """
        Generate comprehensive README documentation.
        
        Args:
            ladom_data: Aggregated LADOM data from project analysis
            project_path: Root path of the analyzed project
            output_path: Path where README.md should be saved
        """
        logger.info("Starting comprehensive README generation...")
        
        # Step 1: Perform comprehensive project analysis
        logger.info("Analyzing project structure and relationships...")
        project_analyzer = ProjectAnalyzer(ladom_data, project_path)
        project_context = project_analyzer.analyze()
        
        # Step 2: Generate diagrams
        logger.info("Generating architecture diagrams...")
        diagrams = DiagramGenerator.generate_all_diagrams(project_context, ladom_data)
        
        # Step 3: Extract examples
        logger.info("Extracting code examples...")
        example_extractor = ExampleExtractor(ladom_data, project_path)
        examples = example_extractor.extract_all_examples()
        
        # Step 4: Build comprehensive prompt
        logger.info("Building LLM prompt with rich context...")
        prompt = self._build_comprehensive_prompt(
            ladom_data, 
            project_context, 
            diagrams, 
            examples
        )
        
        # Step 5: Generate README content using LLM
        logger.info("Generating README content with LLM...")
        readme_content = self._generate_with_llm(prompt)
        
        # Step 6: Post-process and enhance
        logger.info("Post-processing README content...")
        final_content = self._post_process_content(
            readme_content, 
            project_context, 
            diagrams, 
            examples
        )
        
        # Step 7: Save to file
        self._save_readme(final_content, output_path)
        logger.info(f"✓ README generated: {output_path}")

    def _build_comprehensive_prompt(
        self,
        ladom_data: Dict[str, Any],
        project_context: Dict[str, Any],
        diagrams: Dict[str, str],
        examples: Dict[str, Any]
    ) -> str:
        """
        Build a comprehensive prompt for the LLM.
        
        Args:
            ladom_data: LADOM data
            project_context: Project analysis context
            diagrams: Generated diagrams
            examples: Extracted examples
            
        Returns:
            Comprehensive prompt string
        """
        project_name = project_context.get("project_name", "Unknown Project")
        architecture = project_context.get("architecture", {})
        dependencies = project_context.get("dependencies", {})
        key_features = project_context.get("key_features", [])
        tech_stack = project_context.get("technology_stack", {})
        statistics = project_context.get("file_statistics", {})
        entry_points = project_context.get("entry_points", [])
        testing = project_context.get("testing_structure", {})
        config_files = project_context.get("configuration_files", [])
        
        prompt = f"""You are a senior technical writer creating a comprehensive, production-quality README.md for a software project.

# PROJECT INFORMATION

**Project Name:** {project_name}

**Architecture:** {architecture.get('primary_pattern', 'Custom')} - {architecture.get('description', '')}

**Technology Stack:**
- Languages: {', '.join(tech_stack.get('languages', ['Unknown']))}
- Frameworks: {', '.join(tech_stack.get('frameworks', [])) or 'None detected'}

**Project Statistics:**
- Total Files: {statistics.get('total_files', 0)}
- Functions: {statistics.get('total_functions', 0)}
- Classes: {statistics.get('total_classes', 0)}
- Estimated Lines of Code: {statistics.get('estimated_lines', 0)}

**Key Features Detected:**
{self._format_list(key_features) or '- To be determined from code analysis'}

**Entry Points:**
{self._format_entry_points(entry_points)}

**External Dependencies:**
{self._format_list(dependencies.get('external_packages', [])[:10]) or '- No external dependencies detected'}

**Configuration Files:**
{self._format_config_files(config_files)}

**Testing:**
- Framework: {', '.join(testing.get('frameworks', ['None detected']))}
- Test Files: {testing.get('test_count', 0)}

# DETAILED CODE ANALYSIS

{self._format_code_analysis(ladom_data)}

# YOUR TASK

Generate a comprehensive, well-structured README.md that includes ALL of the following sections:

## 1. PROJECT HEADER
- Project title with badges (build status, version, license - use generic placeholders)
- One-line description (catchy and informative)
- Table of contents (linked)

## 2. OVERVIEW
- What is this project? (2-3 paragraphs)
- What problem does it solve?
- Who should use it?
- Key highlights and unique selling points

## 3. FEATURES
- Detailed list of features (based on code analysis)
- What makes this project special
- Capabilities and functionality

## 4. ARCHITECTURE
- High-level architecture explanation
- Design principles and patterns used
- Component relationships
- (Note: Diagrams will be inserted automatically)

## 5. DIRECTORY STRUCTURE
- Explain the project organization
- Purpose of each major directory
- Key files and their roles

## 6. GETTING STARTED

### Prerequisites
- System requirements
- Required software and versions
- Dependencies

### Installation
- Step-by-step installation instructions
- For different operating systems if relevant
- Virtual environment setup for Python projects

### Configuration
- How to configure the application
- Environment variables
- Configuration file examples

## 7. USAGE

### Basic Usage
- How to run the application
- Command-line arguments
- Common use cases with examples

### Advanced Usage
- Advanced features
- Configuration options
- Integration with other tools

### API Documentation (if applicable)
- Key endpoints/functions
- Parameters and return values
- Example requests/responses

## 8. DEVELOPMENT

### Setup Development Environment
- Setting up for development
- Installing dev dependencies
- Development tools

### Project Structure (Detailed)
- Detailed explanation of code organization
- Module purposes and responsibilities
- How components interact

### Adding New Features
- Guidelines for extending the project
- Where to add new code
- Best practices

### Code Style
- Coding conventions used
- Style guides followed

## 9. TESTING
- How to run tests
- Test structure
- Writing new tests
- Test coverage

## 10. DEPLOYMENT
- How to build for production
- Deployment strategies
- Environment considerations

## 11. TROUBLESHOOTING
- Common issues and solutions
- Debugging tips
- Where to get help

## 12. CONTRIBUTING
- How to contribute
- Submission guidelines
- Code review process

## 13. LICENSE
- License type (mention if found, otherwise suggest common ones)

## 14. ACKNOWLEDGMENTS
- Credits and references (if applicable)

## 15. CONTACT & SUPPORT
- How to get help
- Where to report issues

---

# GUIDELINES FOR GENERATION

1. **Be Specific**: Use actual details from the code analysis, not generic placeholders
2. **Be Professional**: Write clear, concise, professional documentation
3. **Be Complete**: Cover all sections thoroughly
4. **Be Practical**: Include real examples and actionable instructions
5. **Use Markdown**: Proper markdown formatting with headers, lists, code blocks
6. **Add Code Examples**: Include code snippets where relevant (use triple backticks with language)
7. **Be Accurate**: Base everything on the actual code analysis provided
8. **Be Helpful**: Think from a new user's perspective - what do they need to know?

# IMPORTANT NOTES

- DO NOT include the diagrams in your output - they will be inserted automatically
- DO include placeholders like `[Architecture Diagram]` where diagrams should go
- DO use proper markdown code blocks: ```python, ```bash, ```json, etc.
- DO include realistic examples based on the actual code
- DO make the README engaging and easy to follow
- DO NOT invent features that don't exist in the code
- DO explain technical concepts clearly

Now generate the comprehensive README.md content:
"""
        
        return prompt

    def _format_list(self, items: List[str]) -> str:
        """Format a list of items as markdown bullets."""
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items)

    def _format_entry_points(self, entry_points: List[Dict[str, str]]) -> str:
        """Format entry points information."""
        if not entry_points:
            return "- No specific entry points detected"
        
        formatted = []
        for ep in entry_points:
            formatted.append(f"- {ep.get('description', 'Entry point')}: `{ep.get('file', '')}`")
        return "\n".join(formatted)

    def _format_config_files(self, config_files: List[Dict[str, str]]) -> str:
        """Format configuration files information."""
        if not config_files:
            return "- No configuration files detected"
        
        formatted = []
        for cf in config_files:
            formatted.append(f"- `{cf.get('file', '')}`: {cf.get('description', '')}")
        return "\n".join(formatted)

    def _format_code_analysis(self, ladom_data: Dict[str, Any]) -> str:
        """Format detailed code analysis for the prompt."""
        files = ladom_data.get("files", [])
        
        # Limit to most important files to avoid token overflow
        important_files = self._get_important_files(files)
        
        output = []
        for file_data in important_files[:10]:  # Limit to 10 files
            file_path = file_data.get("path", "")
            file_name = Path(file_path).name
            
            output.append(f"\n## File: {file_name}")
            
            summary = file_data.get("summary", "")
            if summary:
                output.append(f"**Purpose:** {summary[:200]}")
            
            # Classes
            classes = file_data.get("classes", [])
            if classes:
                output.append(f"\n**Classes ({len(classes)}):**")
                for cls in classes[:3]:  # Limit to 3 classes per file
                    cls_name = cls.get("name", "")
                    cls_desc = cls.get("description", "")[:100]
                    methods = cls.get("methods", [])
                    output.append(f"- `{cls_name}`: {cls_desc} ({len(methods)} methods)")
            
            # Functions
            functions = file_data.get("functions", [])
            if functions:
                output.append(f"\n**Functions ({len(functions)}):**")
                for func in functions[:5]:  # Limit to 5 functions per file
                    func_name = func.get("name", "")
                    func_desc = func.get("description", "")[:100]
                    output.append(f"- `{func_name}`: {func_desc}")
            
            # Imports
            imports = file_data.get("imports", [])
            if imports:
                output.append(f"\n**Key Imports:** {', '.join(str(imp) for imp in imports[:5])}")
        
        return "\n".join(output)

    def _get_important_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify the most important files for documentation."""
        scored_files = []
        
        for file_data in files:
            score = 0
            file_path = file_data.get("path", "")
            
            # Skip test files
            if "test" in file_path.lower():
                score -= 100
            
            # Prioritize main files
            if "main" in file_path.lower():
                score += 50
            
            # Prioritize API/route files
            if any(keyword in file_path.lower() for keyword in ["api", "route", "endpoint"]):
                score += 30
            
            # Prioritize files with many classes
            score += len(file_data.get("classes", [])) * 10
            
            # Prioritize files with many functions
            score += len(file_data.get("functions", [])) * 5
            
            # Deprioritize utility files slightly
            if "util" in file_path.lower() or "helper" in file_path.lower():
                score -= 5
            
            scored_files.append((score, file_data))
        
        # Sort by score and return top files
        scored_files.sort(reverse=True, key=lambda x: x[0])
        return [f[1] for f in scored_files]

    def _generate_with_llm(self, prompt: str) -> str:
        """
        Generate README content using LLM.
        
        Args:
            prompt: The comprehensive prompt
            
        Returns:
            Generated README content
        """
        try:
            logger.info("Calling LLM to generate README content...")
            response = self.llm.generate(prompt)
            
            if not response:
                logger.error("LLM returned empty response")
                return self._generate_fallback_readme()
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating README with LLM: {e}")
            return self._generate_fallback_readme()

    def _generate_fallback_readme(self) -> str:
        """Generate a basic fallback README if LLM fails."""
        return """# Project README

## Overview
This project documentation was generated automatically.

## Installation
```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage
```bash
# Run the application
python main.py
```

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
See LICENSE file for details.
"""

    def _post_process_content(
        self,
        content: str,
        project_context: Dict[str, Any],
        diagrams: Dict[str, str],
        examples: Dict[str, Any]
    ) -> str:
        """
        Post-process and enhance the generated README.
        
        Args:
            content: LLM-generated content
            project_context: Project context
            diagrams: Generated diagrams
            examples: Extracted examples
            
        Returns:
            Enhanced README content
        """
        # Insert diagrams at appropriate locations
        if "[Architecture Diagram]" in content and diagrams.get("architecture"):
            content = content.replace("[Architecture Diagram]", 
                                    f"\n{diagrams['architecture']}\n")
        elif "## 4. ARCHITECTURE" in content or "## Architecture" in content:
            # Insert after architecture header
            arch_diagram = diagrams.get("architecture", "")
            if arch_diagram:
                content = content.replace(
                    "## 4. ARCHITECTURE",
                    f"## 4. ARCHITECTURE\n\n{arch_diagram}\n"
                ).replace(
                    "## Architecture",
                    f"## Architecture\n\n{arch_diagram}\n"
                )
        
        # Insert folder structure diagram
        if "[Folder Structure]" in content and diagrams.get("folder_structure"):
            content = content.replace("[Folder Structure]", 
                                    f"\n{diagrams['folder_structure']}\n")
        
        # Insert dependency diagram
        if "[Dependency Diagram]" in content and diagrams.get("dependencies"):
            content = content.replace("[Dependency Diagram]", 
                                    f"\n{diagrams['dependencies']}\n")
        
        # Insert data flow diagram
        if "[Data Flow]" in content and diagrams.get("data_flow"):
            content = content.replace("[Data Flow]", 
                                    f"\n{diagrams['data_flow']}\n")
        
        # Add metadata footer
        footer = f"\n\n---\n\n*This README was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        content += footer
        
        return content

    def _save_readme(self, content: str, output_path: str) -> None:
        """
        Save README to file.
        
        Args:
            content: README content
            output_path: Output file path
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"README saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving README: {e}")
            raise

    def generate_html(self, markdown_path: str, html_path: str) -> None:
        """
        Generate HTML version of README.
        
        Args:
            markdown_path: Path to markdown file
            html_path: Path for HTML output
        """
        try:
            with open(markdown_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # Use HTMLRenderer to convert
            renderer = HTMLRenderer()
            html_content = renderer.render_markdown_to_html(
                markdown_content,
                title="Project README"
            )
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML README saved to: {html_path}")
            
        except Exception as e:
            logger.error(f"Error generating HTML README: {e}")
