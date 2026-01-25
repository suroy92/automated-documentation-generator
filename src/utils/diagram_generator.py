# src/utils/diagram_generator.py
"""
Generates Mermaid diagrams for documentation visualization.

Creates various types of diagrams including:
- Architecture diagrams
- Dependency graphs
- Class diagrams
- Sequence diagrams
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class DiagramGenerator:
    """Creates visual Mermaid diagrams from project analysis data."""

    @staticmethod
    def generate_architecture_diagram(project_context: Dict[str, Any]) -> str:
        """
        Generate a high-level architecture diagram.
        
        Args:
            project_context: Project analysis context
            
        Returns:
            Mermaid diagram as string
        """
        from pathlib import Path
        
        arch_info = project_context.get("architecture", {})
        entry_points = project_context.get("entry_points", [])
        dependencies = project_context.get("dependencies", {})
        tech_stack = project_context.get("technology_stack", {})
        
        diagram = ["```mermaid", "graph TD"]
        
        # Add entry points with relative paths
        if entry_points:
            for i, ep in enumerate(entry_points[:3]):  # Limit to 3 for clarity
                ep_type = ep.get("type", "main")
                ep_file_full = ep.get("file", "")
                # Convert to relative path (last 2-3 segments)
                ep_parts = Path(ep_file_full).parts
                ep_file = "/".join(ep_parts[-2:]) if len(ep_parts) > 1 else ep_parts[-1]
                diagram.append(f"    Entry{i}[\"{ep_file}<br/>({ep_type})\"]")
        
        # Add main components based on architecture
        arch_pattern = arch_info.get("primary_pattern", "Custom")
        
        # Check if project has views/templates (detect frontend)
        dir_structure = project_context.get("directory_structure", {})
        all_dirs = dir_structure.get("directories", [])
        has_views = any("view" in str(d).lower() or "template" in str(d).lower() or "static" in str(d).lower() for d in all_dirs)
        
        # Check if this is an API-only project
        is_api_only = any(ep.get("type") == "api" for ep in entry_points) and not has_views
        
        if arch_pattern == "MVC":
            if is_api_only:
                # API-only: Model-Controller pattern (no View)
                diagram.extend([
                    "    Model[\"📊 Model Layer\"]",
                    "    Controller[\"🎮 Controller Layer\"]",
                    "    Entry0 --> Controller",
                    "    Controller --> Model"
                ])
            else:
                # Full MVC with View
                diagram.extend([
                    "    Model[\"📊 Model Layer\"]",
                    "    View[\"👁️ View Layer\"]",
                    "    Controller[\"🎮 Controller Layer\"]",
                    "    Entry0 --> Controller",
                    "    Controller --> Model",
                    "    Controller --> View",
                    "    Model --> View"
                ])
        elif arch_pattern == "Layered":
            diagram.extend([
                "    Presentation[\"🖥️ Presentation Layer\"]",
                "    Business[\"💼 Business Logic\"]",
                "    Data[\"💾 Data Layer\"]",
                "    Entry0 --> Presentation",
                "    Presentation --> Business",
                "    Business --> Data"
            ])
        else:
            # Generic structure
            diagram.extend([
                "    Core[\"⚙️ Core Logic\"]",
                "    Utils[\"🔧 Utilities\"]",
                "    Data[\"💾 Data Layer\"]"
            ])
            if entry_points:
                diagram.append("    Entry0 --> Core")
            diagram.extend([
                "    Core --> Utils",
                "    Core --> Data"
            ])
        
        # Don't add External Libraries blob - it's noisy and not useful in architecture diagram
        
        diagram.append("```")
        return "\n".join(diagram)

    @staticmethod
    def generate_dependency_diagram(ladom_data: Dict[str, Any], max_nodes: int = 15) -> str:
        """
        Generate a dependency graph showing module relationships.
        
        Args:
            ladom_data: LADOM data with file information
            max_nodes: Maximum number of nodes to show
            
        Returns:
            Mermaid diagram as string
        """
        files = ladom_data.get("files", [])
        
        # Build dependency map
        dep_map: Dict[str, Set[str]] = defaultdict(set)
        file_names: Dict[str, str] = {}
        
        for file_data in files:
            file_path = file_data.get("path", "")
            file_name = file_path.split("/")[-1].replace(".py", "")
            file_names[file_path] = file_name
            
            imports = file_data.get("imports", [])
            for imp in imports:
                imp_str = str(imp)
                # Only track internal imports
                if imp_str.startswith(".") or "src." in imp_str:
                    imp_name = imp_str.split(".")[-1]
                    dep_map[file_name].add(imp_name)
        
        diagram = ["```mermaid", "graph LR"]
        
        # Add nodes and edges
        added_nodes = set()
        edge_count = 0
        
        for source, targets in list(dep_map.items())[:max_nodes]:
            source_id = source.replace("-", "_").replace(" ", "_")
            if source_id not in added_nodes:
                diagram.append(f"    {source_id}[\"{source}\"]")
                added_nodes.add(source_id)
            
            for target in list(targets)[:3]:  # Limit connections per node
                target_id = target.replace("-", "_").replace(" ", "_")
                if target_id not in added_nodes:
                    diagram.append(f"    {target_id}[\"{target}\"]")
                    added_nodes.add(target_id)
                diagram.append(f"    {source_id} --> {target_id}")
                edge_count += 1
                
                if edge_count >= max_nodes:
                    break
            
            if edge_count >= max_nodes:
                break
        
        if not added_nodes:
            diagram.append("    NoDepends[\"No internal dependencies detected\"]")
        
        diagram.append("```")
        return "\n".join(diagram)

    @staticmethod
    def generate_class_diagram(classes: List[Dict[str, Any]], max_classes: int = 8) -> str:
        """
        Generate a UML class diagram.
        
        Args:
            classes: List of class information from LADOM
            max_classes: Maximum number of classes to show
            
        Returns:
            Mermaid class diagram as string
        """
        if not classes:
            return "```mermaid\nclassDiagram\n    class NoClasses{\n        No classes detected\n    }\n```"
        
        diagram = ["```mermaid", "classDiagram"]
        
        for cls in classes[:max_classes]:
            cls_name = cls.get("name", "Unknown")
            methods = cls.get("methods", [])
            attributes = cls.get("attributes", [])
            extends = cls.get("extends", "")
            
            # Class definition
            diagram.append(f"    class {cls_name}{{")
            
            # Add attributes (limit to 5)
            for attr in attributes[:5]:
                attr_name = attr.get("name", "")
                attr_type = attr.get("type", "")
                if attr_name:
                    diagram.append(f"        +{attr_type} {attr_name}")
            
            # Add methods (limit to 5)
            for method in methods[:5]:
                method_name = method.get("name", "")
                returns = method.get("returns", {}).get("type", "")
                if method_name and not method_name.startswith("__"):
                    diagram.append(f"        +{method_name}() {returns}")
            
            diagram.append("    }")
            
            # Inheritance
            if extends:
                base_classes = extends.split(",")
                for base in base_classes[:1]:  # Show only first parent
                    base = base.strip()
                    if base and base != "object":
                        diagram.append(f"    {base} <|-- {cls_name}")
        
        diagram.append("```")
        return "\n".join(diagram)

    @staticmethod
    def generate_folder_structure_diagram(dir_structure: Dict[str, Any]) -> str:
        """
        Generate a folder structure diagram.
        
        Args:
            dir_structure: Directory structure from project analysis
            
        Returns:
            Mermaid diagram as string
        """
        directories = dir_structure.get("directories", [])
        purposes = dir_structure.get("directory_purposes", {})
        
        diagram = ["```mermaid", "graph TD"]
        diagram.append("    Root[\"📁 Project Root\"]")
        
        # Group by depth
        depth_map: Dict[int, List[str]] = defaultdict(list)
        for directory in directories:
            depth = directory.count("/")
            depth_map[depth].append(directory)
        
        # Add directories level by level (limit to depth 2)
        node_id = 1
        added_nodes = {"Root": "Root"}
        
        for depth in sorted(depth_map.keys())[:2]:
            for directory in depth_map[depth][:8]:  # Limit to 8 dirs per level
                parts = directory.split("/")
                dir_name = parts[-1]
                parent_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
                
                # Create node ID
                node_name = f"Dir{node_id}"
                node_id += 1
                
                # Get purpose
                purpose = purposes.get(directory, "")
                label = f"{dir_name}"
                if purpose and len(purpose) < 50:
                    label += f"<br/><small>{purpose}</small>"
                
                diagram.append(f"    {node_name}[\"{label}\"]")
                
                # Connect to parent
                if parent_path in added_nodes:
                    parent_node = added_nodes[parent_path]
                    diagram.append(f"    {parent_node} --> {node_name}")
                else:
                    diagram.append(f"    Root --> {node_name}")
                
                added_nodes[directory] = node_name
        
        diagram.append("```")
        return "\n".join(diagram)

    @staticmethod
    def generate_data_flow_diagram(entry_points: List[Dict], dependencies: Dict[str, Any]) -> str:
        """
        Generate a data flow diagram showing how data moves through the system.
        
        Args:
            entry_points: Entry point information
            dependencies: Dependency information
            
        Returns:
            Mermaid diagram as string
        """
        diagram = ["```mermaid", "flowchart LR"]
        
        # Input
        diagram.append("    Input[\"📥 Input<br/>(User/API/File)\"]")
        
        # Entry point
        if entry_points:
            ep = entry_points[0]
            ep_name = ep.get("file", "main").split("/")[-1]
            diagram.append(f"    Entry[\"🚪 {ep_name}\"]")
            diagram.append("    Input --> Entry")
        else:
            diagram.append("    Entry[\"🚪 Entry Point\"]")
            diagram.append("    Input --> Entry")
        
        # Processing layers
        diagram.extend([
            "    Process[\"⚙️ Processing<br/>(Business Logic)\"]",
            "    Entry --> Process"
        ])
        
        # Check for database/storage
        external_deps = dependencies.get("external_packages", [])
        has_db = any(db in str(external_deps).lower() for db in ["sql", "mongo", "redis", "database"])
        
        if has_db:
            diagram.extend([
                "    Storage[\"💾 Data Storage<br/>(Database)\"]",
                "    Process --> Storage",
                "    Storage --> Process"
            ])
        
        # Output
        diagram.extend([
            "    Output[\"📤 Output<br/>(Response/File/Report)\"]",
            "    Process --> Output"
        ])
        
        diagram.append("```")
        return "\n".join(diagram)

    @staticmethod
    def generate_all_diagrams(project_context: Dict[str, Any], ladom_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate all available diagrams.
        
        Args:
            project_context: Project analysis context
            ladom_data: LADOM data
            
        Returns:
            Dict mapping diagram names to diagram strings
        """
        diagrams = {}
        
        try:
            diagrams["architecture"] = DiagramGenerator.generate_architecture_diagram(project_context)
        except Exception as e:
            logger.warning(f"Failed to generate architecture diagram: {e}")
            diagrams["architecture"] = ""
        
        try:
            diagrams["dependencies"] = DiagramGenerator.generate_dependency_diagram(ladom_data)
        except Exception as e:
            logger.warning(f"Failed to generate dependency diagram: {e}")
            diagrams["dependencies"] = ""
        
        try:
            diagrams["folder_structure"] = DiagramGenerator.generate_folder_structure_diagram(
                project_context.get("directory_structure", {})
            )
        except Exception as e:
            logger.warning(f"Failed to generate folder structure diagram: {e}")
            diagrams["folder_structure"] = ""
        
        try:
            diagrams["data_flow"] = DiagramGenerator.generate_data_flow_diagram(
                project_context.get("entry_points", []),
                project_context.get("dependencies", {})
            )
        except Exception as e:
            logger.warning(f"Failed to generate data flow diagram: {e}")
            diagrams["data_flow"] = ""
        
        # Collect all classes for class diagram
        all_classes = []
        for file_data in ladom_data.get("files", []):
            all_classes.extend(file_data.get("classes", []))
        
        if all_classes:
            try:
                diagrams["class_diagram"] = DiagramGenerator.generate_class_diagram(all_classes)
            except Exception as e:
                logger.warning(f"Failed to generate class diagram: {e}")
                diagrams["class_diagram"] = ""
        
        return diagrams
