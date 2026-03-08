"""
pyproject.toml parser.

Extracts dependencies and project metadata from Python pyproject.toml files.
"""

from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def parse_pyproject_toml(pyproject_path: str) -> Dict[str, Any]:
    """
    Parse pyproject.toml file to extract dependencies.

    Args:
        pyproject_path: Path to pyproject.toml file

    Returns:
        Dictionary containing:
        - dependencies: List of runtime dependencies
        - dev_dependencies: List of dev/optional dependencies
        - project_name: Project name
        - version: Project version
        - description: Project description
    """
    try:
        import tomli
    except ImportError:
        # Try tomllib (Python 3.11+)
        try:
            import tomllib as tomli
        except ImportError:
            logger.warning("tomli/tomllib not available, cannot parse pyproject.toml")
            return {
                'dependencies': [],
                'dev_dependencies': [],
                'project_name': None,
                'version': None,
                'description': None
            }

    try:
        with open(pyproject_path, 'rb') as f:
            data = tomli.load(f)

        # Extract project metadata
        project = data.get('project', {})
        project_name = project.get('name')
        version = project.get('version')
        description = project.get('description')

        # Extract dependencies
        dependencies = []
        dev_dependencies = []

        # Runtime dependencies
        if 'dependencies' in project:
            deps = project['dependencies']
            if isinstance(deps, list):
                dependencies = [_parse_python_requirement(dep) for dep in deps]

        # Optional dependencies (dev, test, etc.)
        if 'optional-dependencies' in project:
            optional_deps = project['optional-dependencies']
            for category, deps in optional_deps.items():
                if isinstance(deps, list):
                    parsed_deps = [_parse_python_requirement(dep) for dep in deps]
                    dev_dependencies.extend(parsed_deps)

        # Poetry format (alternative)
        if 'tool' in data and 'poetry' in data['tool']:
            poetry = data['tool']['poetry']

            # Poetry project metadata
            if not project_name:
                project_name = poetry.get('name')
            if not version:
                version = poetry.get('version')
            if not description:
                description = poetry.get('description')

            # Poetry dependencies
            if 'dependencies' in poetry:
                for name, spec in poetry['dependencies'].items():
                    if name.lower() == 'python':
                        continue  # Skip Python version spec
                    dep_info = _parse_poetry_dependency(name, spec)
                    dependencies.append(dep_info)

            # Poetry dev dependencies
            if 'dev-dependencies' in poetry:
                for name, spec in poetry['dev-dependencies'].items():
                    dep_info = _parse_poetry_dependency(name, spec)
                    dev_dependencies.append(dep_info)

            # Poetry groups (Poetry 1.2+)
            if 'group' in poetry:
                for group_name, group_data in poetry['group'].items():
                    if 'dependencies' in group_data:
                        for name, spec in group_data['dependencies'].items():
                            dep_info = _parse_poetry_dependency(name, spec)
                            dev_dependencies.append(dep_info)

        return {
            'dependencies': dependencies,
            'dev_dependencies': dev_dependencies,
            'project_name': project_name,
            'version': version,
            'description': description
        }

    except FileNotFoundError:
        logger.warning(f"pyproject.toml not found at {pyproject_path}")
        return {
            'dependencies': [],
            'dev_dependencies': [],
            'project_name': None,
            'version': None,
            'description': None
        }
    except Exception as e:
        logger.warning(f"Error parsing pyproject.toml at {pyproject_path}: {e}")
        return {
            'dependencies': [],
            'dev_dependencies': [],
            'project_name': None,
            'version': None,
            'description': None
        }


def _parse_python_requirement(req_string: str) -> Dict[str, str]:
    """
    Parse a Python requirement string (e.g., 'requests>=2.0.0').

    Args:
        req_string: Requirement string

    Returns:
        Dictionary with name and version
    """
    # Simple parsing - split on common operators
    for op in ['>=', '<=', '==', '~=', '!=', '>', '<', '^']:
        if op in req_string:
            parts = req_string.split(op, 1)
            return {
                'name': parts[0].strip(),
                'version': parts[1].strip() if len(parts) > 1 else None
            }

    # No version specified
    return {
        'name': req_string.strip(),
        'version': None
    }


def _parse_poetry_dependency(name: str, spec: Any) -> Dict[str, str]:
    """
    Parse a Poetry dependency specification.

    Args:
        name: Dependency name
        spec: Version spec (string or dict)

    Returns:
        Dictionary with name and version
    """
    if isinstance(spec, str):
        return {
            'name': name,
            'version': spec
        }
    elif isinstance(spec, dict):
        version = spec.get('version')
        return {
            'name': name,
            'version': version
        }
    else:
        return {
            'name': name,
            'version': None
        }
