"""
Maven pom.xml parser.

Extracts dependencies and project metadata from Maven pom.xml files.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def parse_pom_xml(pom_path: str) -> Dict[str, Any]:
    """
    Parse Maven pom.xml file to extract dependencies.

    Args:
        pom_path: Path to pom.xml file

    Returns:
        Dictionary containing:
        - dependencies: List of dependency dicts with name, version, scope
        - project_name: Project artifactId
        - version: Project version
        - group_id: Project groupId
    """
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()

        # Maven uses namespaces
        # Try to detect namespace
        namespace = ''
        if root.tag.startswith('{'):
            namespace = root.tag[root.tag.find('{'):root.tag.find('}') + 1]

        def find_with_ns(element, tag):
            """Find element with or without namespace."""
            # Try with namespace first
            result = element.find(f'{namespace}{tag}')
            if result is None:
                # Try without namespace
                result = element.find(tag)
            return result

        def findall_with_ns(element, tag):
            """Find all elements with or without namespace."""
            # Try with namespace first
            results = element.findall(f'{namespace}{tag}')
            if not results:
                # Try without namespace
                results = element.findall(tag)
            return results

        # Extract project metadata
        project_name = None
        version = None
        group_id = None

        artifact_id_elem = find_with_ns(root, 'artifactId')
        if artifact_id_elem is not None:
            project_name = artifact_id_elem.text

        version_elem = find_with_ns(root, 'version')
        if version_elem is not None:
            version = version_elem.text

        group_id_elem = find_with_ns(root, 'groupId')
        if group_id_elem is not None:
            group_id = group_id_elem.text

        # Extract dependencies
        dependencies = []

        # Find <dependencies> section
        deps_elem = find_with_ns(root, 'dependencies')
        if deps_elem is not None:
            for dep in findall_with_ns(deps_elem, 'dependency'):
                dep_info = _parse_dependency(dep, namespace, find_with_ns)
                if dep_info:
                    dependencies.append(dep_info)

        # Also check <dependencyManagement><dependencies>
        dep_mgmt = find_with_ns(root, 'dependencyManagement')
        if dep_mgmt is not None:
            deps_elem = find_with_ns(dep_mgmt, 'dependencies')
            if deps_elem is not None:
                for dep in findall_with_ns(deps_elem, 'dependency'):
                    dep_info = _parse_dependency(dep, namespace, find_with_ns)
                    if dep_info:
                        # Mark as managed dependency
                        dep_info['managed'] = True
                        dependencies.append(dep_info)

        return {
            'dependencies': dependencies,
            'project_name': project_name,
            'version': version,
            'group_id': group_id
        }

    except ET.ParseError as e:
        logger.warning(f"Failed to parse pom.xml at {pom_path}: {e}")
        return {'dependencies': [], 'project_name': None, 'version': None, 'group_id': None}
    except Exception as e:
        logger.warning(f"Error parsing pom.xml at {pom_path}: {e}")
        return {'dependencies': [], 'project_name': None, 'version': None, 'group_id': None}


def _parse_dependency(dep_elem, namespace: str, find_with_ns) -> Optional[Dict[str, str]]:
    """
    Parse a single <dependency> element.

    Args:
        dep_elem: Dependency XML element
        namespace: XML namespace
        find_with_ns: Function to find elements with namespace handling

    Returns:
        Dictionary with groupId, artifactId, version, scope, type
    """
    group_id = find_with_ns(dep_elem, 'groupId')
    artifact_id = find_with_ns(dep_elem, 'artifactId')
    version_elem = find_with_ns(dep_elem, 'version')
    scope_elem = find_with_ns(dep_elem, 'scope')
    type_elem = find_with_ns(dep_elem, 'type')

    if group_id is None or artifact_id is None:
        return None

    # Construct dependency name (groupId:artifactId)
    name = f"{group_id.text}:{artifact_id.text}"

    # Get version (may be None for managed dependencies)
    version = version_elem.text if version_elem is not None else None

    # Get scope (compile, test, runtime, provided, system)
    # Default is 'compile' if not specified
    scope = scope_elem.text if scope_elem is not None else 'compile'

    # Get type (jar, war, pom, etc.)
    dep_type = type_elem.text if type_elem is not None else 'jar'

    return {
        'name': name,
        'group_id': group_id.text,
        'artifact_id': artifact_id.text,
        'version': version,
        'scope': scope,
        'type': dep_type
    }


def categorize_maven_dependency(scope: str) -> str:
    """
    Categorize Maven dependency scope to our dependency type.

    Args:
        scope: Maven scope (compile, test, runtime, provided, system)

    Returns:
        Dependency type: runtime, dev, or optional
    """
    scope_map = {
        'compile': 'runtime',
        'runtime': 'runtime',
        'test': 'dev',
        'provided': 'runtime',  # Provided at runtime by container
        'system': 'runtime',
    }
    return scope_map.get(scope.lower(), 'runtime')
