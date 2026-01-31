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
from .sanitizer import Sanitizer
from .validator import ReadmeValidator, ValidationResult

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
        output_path: str,
        validate: bool = True
    ) -> ValidationResult:
        """
        Generate comprehensive README documentation.

        Args:
            ladom_data: Aggregated LADOM data from project analysis
            project_path: Root path of the analyzed project
            output_path: Path where README.md should be saved
            validate: Whether to run validation (default: True)

        Returns:
            ValidationResult with validation status

        Raises:
            ValueError: If validation fails and validate=True
        """
        logger.info("Starting comprehensive README generation...")

        # Step 0: Sanitize input facts (prevent issues at source)
        logger.info("Sanitizing input data...")
        sanitizer = Sanitizer(project_root=project_path)
        sanitize_result = sanitizer.sanitize_facts(ladom_data)
        ladom_data = sanitize_result.sanitized_data

        if sanitize_result.issues_found:
            logger.warning(f"Found {len(sanitize_result.issues_found)} issues in input data")
            for issue in sanitize_result.issues_found[:5]:
                logger.warning(f"  - {issue}")

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

        # Step 6.5: Final sanitization of markdown output
        logger.info("Final sanitization of markdown...")
        markdown_sanitize_result = sanitizer.sanitize_markdown(final_content)
        final_content = markdown_sanitize_result.sanitized_data

        if markdown_sanitize_result.issues_found:
            logger.warning(f"Found {len(markdown_sanitize_result.issues_found)} issues in generated markdown")

        # Step 7: Validate README (if enabled)
        validation_result = ValidationResult(passed=True)
        if validate:
            logger.info("Validating generated README...")
            validator = ReadmeValidator(strict=False)
            validation_result = validator.validate(final_content, ladom_data)

            if not validation_result.passed:
                logger.error("README validation FAILED!")
                logger.error(validation_result.get_detailed_report())
                # Save the file even if validation fails (for debugging)
                self._save_readme(final_content, output_path)
                logger.info(f"README saved to {output_path} (with validation errors)")
                raise ValueError(f"README validation failed with {validation_result.error_count} errors")
            else:
                logger.info(f"✓ README validation PASSED ({validation_result.warning_count} warnings)")
                if validation_result.warnings:
                    for warning in validation_result.warnings[:10]:
                        logger.warning(f"  {warning}")

        # Step 8: Save to file
        self._save_readme(final_content, output_path)
        logger.info(f"✓ README generated: {output_path}")

        return validation_result

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
        
        # Determine project size for appropriate detail level
        total_files = statistics.get('total_files', 0)
        is_small_project = total_files < 20
        has_tests = testing.get('test_count', 0) > 0
        
        prompt = f"""You are a senior technical writer creating README documentation for DEVELOPERS who need to understand and work with this codebase.

# PROJECT ANALYSIS DATA

**Project Name:** {project_name}

**Architecture:** {architecture.get('primary_pattern', 'Custom')}
{architecture.get('description', '')}

**Technology Stack:**
- Languages: {', '.join(tech_stack.get('languages', ['Unknown']))}
- Frameworks: {', '.join(tech_stack.get('frameworks', [])) if tech_stack.get('frameworks') else 'None detected'}

**Project Statistics:**
- Total Files: {statistics.get('total_files', 0)}
- Functions: {statistics.get('total_functions', 0)}
- Classes: {statistics.get('total_classes', 0)}
- Lines of Code: ~{statistics.get('estimated_lines', 0)}

**Key Features:**
{self._format_list(key_features) if key_features else '- Features to be derived from code analysis'}

**Entry Points:**
{self._format_entry_points(entry_points)}

**Dependencies:**
{self._format_list(dependencies.get('external_packages', [])[:15]) if dependencies.get('external_packages') else '- No external dependencies'}

**Configuration:**
{self._format_config_files(config_files) if config_files else '- No configuration files detected'}

**Testing:**
{f"- Framework: {', '.join(testing.get('frameworks', []))}" if testing.get('frameworks') else "- No test framework detected"}
{f"- Test Files: {testing.get('test_count', 0)}" if has_tests else ""}

# DETAILED CODE ANALYSIS

{self._format_code_analysis(ladom_data)}

# YOUR TASK

Generate a developer-focused README.md that is:
1. **Accurate** - Based only on actual code analysis (no placeholders, no fake data)
2. **Specific** - Uses real file paths, function names, and examples from the code
3. **Concise** - {'Brief and focused for small projects' if is_small_project else 'Comprehensive for larger projects'}
4. **Actionable** - Helps developers get started and find their way around

# REQUIRED SECTIONS (adapt depth based on project size)

## 1. Project Header
- **Title**: Use actual project name: {project_name}
- **Description**: One clear sentence about what this project does (derived from analysis)
- **DO NOT** include GitHub badges, clone URLs, or usernames unless you can extract them from git config
- **DO NOT** use placeholder text like "yourusername/your-repo"

## 2. What Is This?
- Explain the purpose in 2-3 sentences
- List 3-5 key capabilities based on detected features
- Identify the target audience/use case

## 3. Architecture
- State the architecture pattern: {architecture.get('primary_pattern', 'Custom')}
- **IMPORTANT**: If this is an API-only backend, DO NOT claim it has a "View" layer or MVC
- Explain component organization (use relative paths like `src/auth/`, not absolute Windows paths)
- Include [Architecture Diagram] placeholder

## 4. Project Structure
- Show folder tree (use relative paths only)
- Explain what each major directory contains
- Highlight entry points: {', '.join([ep.get('file', ep.get('description', str(ep))) for ep in entry_points[:3]]) if entry_points else 'main files'}
- Include [Folder Structure] placeholder

## 5. Key Components
- Document 5-8 most important files/modules
- For each: purpose, main exports, when to modify
- Use actual filenames and function signatures from analysis
- Show dependency relationships

## 6. Getting Started

### Prerequisites
- **Extract from actual build files**: {'requirements.txt for Python' if 'python' in str(tech_stack.get('languages', [])).lower() else 'package.json for Node' if 'javascript' in str(tech_stack.get('languages', [])).lower() or 'typescript' in str(tech_stack.get('languages', [])).lower() else 'pom.xml or build.gradle for Java'}
- List runtime/language versions found in config files
- **DO NOT** hardcode version numbers (e.g., "JDK 11 or later")

### Installation
- **Use actual dependency files detected**: {', '.join([cf.get('file', '') for cf in config_files[:3]]) if config_files else 'no dependency file detected'}
- Provide correct install commands based on detected package managers
- **DO NOT** reference files that don't exist (no requirements.txt if Python project has none)

### Running
- Base commands on detected entry points
- Use actual script names from package.json or build files
- Show real examples, not generic placeholders

## 7. API / Usage Examples (if applicable)
- **ONLY include this section if project has API endpoints, CLI commands, or public functions**
- For REST APIs:
  - Format endpoints consistently: `GET /api/items` (with leading slash and proper base path)
  - For curl examples: `curl http://localhost:PORT/api/items` (ensure proper URL with slashes)
  - For path parameters: `/api/items/:id` (Node.js) or `/api/items/{id}` (Spring)
- For CLI tools: show actual commands from code
- For libraries: show import and usage examples
- **Validate URLs**: Ensure no malformed URLs like `localhost:3000items` (missing slash)
- **Match detected routes**: If routes are at `/api/...`, don't document as `/items`
- **Don't describe repos as "database operations"** if storage is in-memory (check implementation)

{'## 8. Testing' if has_tests else ''}
{'- Show how to run detected test framework: ' + ', '.join(testing.get('frameworks', [])) if has_tests else ''}
{'- List test commands from package.json or build files' if has_tests else ''}
{'- **DO NOT** mention coverage requirements if no coverage tools detected' if has_tests else ''}

## {'9' if has_tests else '8'}. Development
- Explain how to set up development environment
- **Base on actual project structure**, not generic advice
- **DO NOT** include generic performance tips ("avoid unnecessary DB queries") unless relevant
- **DO NOT** include SLA/response-time claims without metrics

## {'10' if has_tests else '9'}. Contributing
- Code organization principles
- Where to add new features (based on actual structure)
- **DO NOT** include instructional placeholders like "Include real code examples for..."

## {'11' if has_tests else '10'}. Architecture Decisions (if complex project)
- **ONLY include if project has notable design choices**
- Explain why certain patterns/libraries were chosen (if evident from code)

## {'12' if has_tests else '11'}. Dependencies
- List actual external packages from analysis
- **DO NOT** invent dependencies

## {'13' if has_tests else '12'}. License
- **ONLY include if LICENSE file was detected**

# CRITICAL RULES

**DO NOT:**
- Use placeholder text: "yourusername", "your-repo", "Project title with badges"
- Include fake GitHub metadata (badges, clone URLs with placeholders)
- Use absolute machine paths (D:\\Workspace\\...) - always use relative paths (src/auth/)
- Claim architecture patterns that don't apply (no MVC "View" for API-only backends)
- Insert "[Sequence Diagram]" or "[Placeholder]" sections you can't generate
- Duplicate sections (no "How to get help" twice)
- Include generic advice irrelevant to this project
- Reference build files that don't exist
- Hardcode prerequisites - derive from build config
- Include instructional text meant for you ("List specific problems...")
- Make up route examples - use actual detected routes with correct paths
- Include testing/coverage requirements when no tests exist
- Be overly verbose for small projects (<20 files)
- Create malformed URLs like `http://localhost:3000items` - always ensure proper slashes
- Use inconsistent path formatting like `srcindex.js` - use `src/index.js`

**DO:**
- Base everything on actual code analysis data provided
- Use consistent heading capitalization (Title Case, not ALL CAPS)
- Derive install commands from detected package managers
- Show actual code examples extracted from the project
- Use relative repository paths everywhere (e.g., `src/controllers/items.js`)
- Omit sections when data is unavailable (no Testing section if no tests)
- Keep it concise for small projects
- Ensure accuracy over completeness
- Validate all URLs have proper structure: `http://host:port/path` (with slashes)
- Use consistent path separators in file paths throughout

# CODE DETAILS FOR ACCURACY

{self._format_detailed_components(ladom_data, project_context)}

Generate the README following these rules strictly:
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

    def _format_detailed_components(self, ladom_data: Dict[str, Any], project_context: Dict[str, Any]) -> str:
        """Format detailed component information with APIs and interactions."""
        files = ladom_data.get("files", [])
        important_files = self._get_important_files(files)
        
        output = []
        output.append("\n## DETAILED COMPONENT BREAKDOWN\n")
        
        for file_data in important_files[:12]:  # Top 12 most important files
            file_path = file_data.get("path", "")
            file_name = Path(file_path).name
            relative_path = "/".join(Path(file_path).parts[-3:]) if len(Path(file_path).parts) > 3 else file_path
            
            output.append(f"\n### Component: {file_name} (`{relative_path}`)")
            
            # Summary
            summary = file_data.get("summary", "")
            if summary:
                output.append(f"\n**Purpose**: {summary[:300]}")
            
            # Classes with detailed info
            classes = file_data.get("classes", [])
            if classes:
                output.append(f"\n**Classes ({len(classes)}):**\n")
                for cls in classes[:3]:
                    cls_name = cls.get("name", "")
                    cls_desc = cls.get("description", "")
                    methods = cls.get("methods", [])
                    attributes = cls.get("attributes", [])
                    extends = cls.get("extends", "")
                    
                    output.append(f"- **`{cls_name}`**{f' extends {extends}' if extends else ''}: {cls_desc[:150]}")
                    if attributes:
                        output.append(f"  - Attributes: {', '.join(a.get('name', '') for a in attributes[:5])}")
                    if methods:
                        output.append(f"  - Key Methods:")
                        for method in methods[:4]:
                            m_name = method.get("name", "")
                            m_sig = method.get("signature", "")
                            m_desc = method.get("description", "")[:80]
                            if not m_name.startswith("_"):  # Skip private methods
                                output.append(f"    - `{m_name}{m_sig}`: {m_desc}")
            
            # Functions with signatures
            functions = file_data.get("functions", [])
            public_funcs = [f for f in functions if not f.get("name", "").startswith("_")]
            if public_funcs:
                output.append(f"\n**Public Functions ({len(public_funcs)}):**\n")
                for func in public_funcs[:6]:
                    func_name = func.get("name", "")
                    func_sig = func.get("signature", "")
                    func_desc = func.get("description", "")
                    returns = func.get("returns", {}).get("type", "")
                    params = func.get("parameters", [])
                    
                    output.append(f"- **`{func_name}{func_sig}`** → `{returns}`")
                    if func_desc:
                        output.append(f"  - {func_desc[:150]}")
                    if params and len(params) > 0:
                        output.append(f"  - Parameters: {', '.join(p.get('name', '') for p in params[:4])}")
            
            # Dependencies
            imports = file_data.get("imports", [])
            if imports:
                # Handle both dict and string imports
                external = []
                internal = []
                for imp in imports:
                    if isinstance(imp, dict):
                        from_module = imp.get("from", "") or imp.get("module", "")
                        if from_module and not from_module.startswith("."):
                            external.append(imp)
                        elif from_module and from_module.startswith("."):
                            internal.append(imp)
                    elif isinstance(imp, str):
                        if not imp.startswith("."):
                            external.append({"module": imp})
                        else:
                            internal.append({"module": imp})
                
                external = external[:4]
                internal = internal[:4]
                
                if external:
                    module_names = [imp.get('module', imp.get('name', str(imp))) for imp in external]
                    output.append(f"\n**External Dependencies**: {', '.join(module_names)}")
                if internal:
                    module_names = [imp.get('module', imp.get('name', str(imp))) for imp in internal]
                    output.append(f"**Internal Dependencies**: {', '.join(module_names)}")
        
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
            response = self.llm.generate(prompt=prompt)
            
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
        # Clean up placeholder text that shouldn't be in output
        placeholders_to_remove = [
            "yourusername/your-repo",
            "yourusername",
            "your-repo",
            "Project title with relevant badges",
            "One-line compelling description",
            "Include real code examples for",
            "List specific problems developers encounter",
            "[Sequence Diagram]",
            "[Placeholder]",
        ]
        
        for placeholder in placeholders_to_remove:
            if placeholder in content:
                # Remove lines containing these placeholders
                lines = content.split('\n')
                content = '\n'.join([line for line in lines if placeholder not in line])
        
        # Remove absolute Windows/Unix paths, keep only relative paths
        import re
        # More aggressive Windows absolute path removal including in diagrams
        content = re.sub(r'[A-Z]:[\\\/][^"\'\s\n\]]+', '', content)  # Windows absolute paths
        # Fix malformed URLs (missing slash between host:port and path)
        content = re.sub(r'(https?://[a-zA-Z0-9\.\-]+:\d+)([a-zA-Z])', r'\1/\2', content)
        content = re.sub(r'(https?://[a-zA-Z0-9\.\-]+)([a-zA-Z][a-zA-Z0-9\-]*)', r'\1/\2', content)
        
        # Fix path separator issues (srcindex.js -> src/index.js)
        content = re.sub(r'\b(src|app|lib|controllers|models|views|services|routes)([a-z])', r'\1/\2', content)
        
        # Validate and fix common URL patterns
        self._validate_and_fix_urls(content)
        
        # Insert diagrams at appropriate locations
        if "[Architecture Diagram]" in content and diagrams.get("architecture"):
            content = content.replace("[Architecture Diagram]", 
                                    f"\n{diagrams['architecture']}\n")
        elif "## Architecture" in content:
            arch_diagram = diagrams.get("architecture", "")
            if arch_diagram:
                content = content.replace(
                    "## Architecture",
                    f"## Architecture\n\n{arch_diagram}\n",
                    1  # Only first occurrence
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
        
        # Remove any remaining placeholder diagram markers
        content = re.sub(r'\[[\w\s]+Diagram\]', '', content)
        content = re.sub(r'\[[\w\s]+placeholder[^\]]*\]', '', content, flags=re.IGNORECASE)
        
        # Clean up duplicate sections (simple approach: remove exact duplicate headings)
        lines = content.split('\n')
        seen_headings = set()
        cleaned_lines = []
        skip_until_next_section = False
        
        for line in lines:
            if line.startswith('##'):
                if line in seen_headings:
                    skip_until_next_section = True
                    continue
                else:
                    seen_headings.add(line)
                    skip_until_next_section = False
            
            if not skip_until_next_section:
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        # Run validation gate before finalizing
        validation_issues = self._validate_output(content)
        if validation_issues:
            logger.warning(f"README validation found {len(validation_issues)} issues:")
            for issue in validation_issues[:10]:  # Log first 10
                logger.warning(f"  - {issue}")
        
        # Add metadata footer
        footer = f"\n\n---\n\n*This README was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        content += footer
        
        return content
    
    def _validate_and_fix_urls(self, content: str) -> str:
        """Validate URLs in content and log issues."""
        import re
        # Find potential malformed URLs
        malformed = re.findall(r'https?://[^/\s]+[a-zA-Z]', content)
        if malformed:
            logger.warning(f"Potential malformed URLs detected: {malformed[:5]}")
        return content
    
    def _validate_output(self, content: str) -> List[str]:
        """
        Validate generated README for common issues.
        
        Returns:
            List of validation issues found
        """
        import re
        issues = []
        
        # Check for absolute paths
        abs_windows = re.findall(r'[A-Z]:[\\\/][^\s\n]+', content)
        if abs_windows:
            issues.append(f"Contains {len(abs_windows)} absolute Windows paths")
        
        # Check for malformed URLs
        malformed_urls = re.findall(r'https?://[^/\s:]+:\d+[a-zA-Z]', content)
        if malformed_urls:
            issues.append(f"Contains {len(malformed_urls)} malformed URLs (missing slash)")
        
        # Check for placeholder text
        placeholders = ["yourusername", "your-repo", "your-project"]
        for placeholder in placeholders:
            if placeholder in content.lower():
                issues.append(f"Contains placeholder text: {placeholder}")
        
        # Check for missing path separators
        bad_paths = re.findall(r'\b(src|app|lib)(index|main|app|server|routes|models)', content)
        if bad_paths:
            issues.append(f"Contains {len(bad_paths)} paths with missing separators")
        
        # Check for inconsistent endpoint formats (if API docs present)
        if "curl" in content.lower() or "endpoint" in content.lower():
            # Look for endpoints without leading slash
            bad_endpoints = re.findall(r'`(GET|POST|PUT|DELETE|PATCH)\s+([a-z])', content)
            if bad_endpoints:
                issues.append(f"Contains {len(bad_endpoints)} endpoints without leading slash")
        
        return issues

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
