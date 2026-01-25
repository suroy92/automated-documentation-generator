"""
AST Utilities Module for Cross-Language Analysis

Provides common functionality for analyzing Abstract Syntax Trees (AST) across
different programming languages (Python, JavaScript, TypeScript, Java).

Features:
- Dependency graph building
- Call graph analysis
- Data flow tracking
- Control flow analysis
- Symbol resolution
- Cross-reference mapping
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Symbol:
    """Represents a code symbol (function, class, variable, etc.)."""

    name: str
    type: str  # 'function', 'class', 'variable', 'constant', 'method'
    file_path: str
    line: int
    end_line: Optional[int] = None
    signature: Optional[str] = None
    parent: Optional[str] = None  # Parent class/module name
    access_modifier: Optional[str] = None  # 'public', 'private', 'protected'
    is_exported: bool = False
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)  # Functions this symbol calls
    references: Set[str] = field(default_factory=set)  # Other symbols it references


@dataclass
class ImportStatement:
    """Represents an import/require statement."""

    source: str  # Module/file being imported
    names: List[str]  # Specific names imported (or ['*'] for wildcard)
    alias: Optional[str] = None
    file_path: str = ""
    line: int = 0
    import_type: str = "import"  # 'import', 'require', 'from_import'


@dataclass
class DependencyNode:
    """Node in the dependency graph."""

    identifier: str  # Unique identifier (file_path or module_name)
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[ImportStatement] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)  # Files/modules this depends on
    dependents: Set[str] = field(default_factory=set)  # Files/modules that depend on this


class DependencyGraph:
    """Build and analyze project-wide dependency graphs."""

    def __init__(self):
        self.nodes: Dict[str, DependencyNode] = {}
        self.symbol_table: Dict[str, Symbol] = {}  # name -> Symbol
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # caller -> callees

    def add_node(self, identifier: str, node: DependencyNode) -> None:
        """Add a node to the dependency graph."""
        self.nodes[identifier] = node

        # Index symbols
        for symbol in node.symbols:
            self.symbol_table[f"{identifier}:{symbol.name}"] = symbol

    def add_dependency(self, from_node: str, to_node: str) -> None:
        """Add a dependency relationship."""
        if from_node in self.nodes and to_node in self.nodes:
            self.nodes[from_node].dependencies.add(to_node)
            self.nodes[to_node].dependents.add(from_node)

    def add_call(self, caller: str, callee: str) -> None:
        """Add a function call relationship."""
        self.call_graph[caller].add(callee)

    def get_dependencies(self, identifier: str) -> Set[str]:
        """Get all dependencies of a node."""
        if identifier in self.nodes:
            return self.nodes[identifier].dependencies
        return set()

    def get_dependents(self, identifier: str) -> Set[str]:
        """Get all nodes that depend on this node."""
        if identifier in self.nodes:
            return self.nodes[identifier].dependents
        return set()

    def get_transitive_dependencies(self, identifier: str) -> Set[str]:
        """Get all transitive dependencies (recursive)."""
        visited = set()
        to_visit = [identifier]

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue

            visited.add(current)
            deps = self.get_dependencies(current)
            to_visit.extend(deps - visited)

        visited.discard(identifier)
        return visited

    def get_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies in the graph."""
        cycles = []
        visited = set()

        def dfs(node: str, path: List[str], rec_stack: Set[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self.get_dependencies(node):
                if dep not in visited:
                    dfs(dep, path, rec_stack)
                elif dep in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    if cycle not in cycles:
                        cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node, [], set())

        return cycles

    def topological_sort(self) -> List[str]:
        """Perform topological sort on the dependency graph."""
        in_degree = {node: 0 for node in self.nodes}

        for node in self.nodes:
            for dep in self.get_dependencies(node):
                if dep in in_degree:
                    in_degree[dep] += 1

        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for dep in self.get_dependents(node):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        return result

    def get_entry_points(self) -> List[str]:
        """Find entry points (nodes with no dependencies)."""
        return [node for node in self.nodes if not self.get_dependencies(node)]

    def get_leaf_nodes(self) -> List[str]:
        """Find leaf nodes (nodes with no dependents)."""
        return [node for node in self.nodes if not self.get_dependents(node)]

    def get_call_chain(self, start_function: str, max_depth: int = 10) -> List[List[str]]:
        """Get call chains starting from a function."""
        chains = []

        def dfs_calls(func: str, path: List[str], depth: int) -> None:
            if depth >= max_depth or func in path:
                return

            path.append(func)

            callees = self.call_graph.get(func, set())
            if not callees:
                chains.append(path.copy())
            else:
                for callee in callees:
                    dfs_calls(callee, path, depth + 1)

            path.pop()

        dfs_calls(start_function, [], 0)
        return chains

    def export_to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary for serialization."""
        return {
            "nodes": {
                identifier: {
                    "symbols": [
                        {
                            "name": s.name,
                            "type": s.type,
                            "line": s.line,
                            "signature": s.signature,
                        }
                        for s in node.symbols
                    ],
                    "dependencies": list(node.dependencies),
                    "dependents": list(node.dependents),
                    "imports": [
                        {"source": imp.source, "names": imp.names, "line": imp.line} for imp in node.imports
                    ],
                    "exports": node.exports,
                }
                for identifier, node in self.nodes.items()
            },
            "call_graph": {caller: list(callees) for caller, callees in self.call_graph.items()},
        }


class DataFlowAnalyzer:
    """Analyze data flow within functions and across modules."""

    @staticmethod
    def track_variable_flow(symbols: List[Symbol]) -> Dict[str, List[str]]:
        """Track how variables flow through the code."""
        variable_flow = defaultdict(list)

        for symbol in symbols:
            if symbol.type == "variable":
                # Track where this variable is used
                for ref in symbol.references:
                    variable_flow[symbol.name].append(ref)

        return dict(variable_flow)

    @staticmethod
    def identify_data_sources(symbols: List[Symbol]) -> List[Symbol]:
        """Identify data sources (inputs, API calls, file reads, etc.)."""
        data_sources = []

        source_indicators = [
            "input",
            "read",
            "fetch",
            "request",
            "get",
            "load",
            "parse",
            "receive",
            "query",
            "select",
        ]

        for symbol in symbols:
            if symbol.type == "function":
                for call in symbol.calls:
                    call_lower = call.lower()
                    if any(indicator in call_lower for indicator in source_indicators):
                        data_sources.append(symbol)
                        break

        return data_sources

    @staticmethod
    def identify_data_sinks(symbols: List[Symbol]) -> List[Symbol]:
        """Identify data sinks (outputs, API calls, file writes, etc.)."""
        data_sinks = []

        sink_indicators = [
            "output",
            "write",
            "send",
            "post",
            "put",
            "save",
            "store",
            "insert",
            "update",
            "delete",
            "print",
            "log",
        ]

        for symbol in symbols:
            if symbol.type == "function":
                for call in symbol.calls:
                    call_lower = call.lower()
                    if any(indicator in call_lower for indicator in sink_indicators):
                        data_sinks.append(symbol)
                        break

        return data_sinks


class ControlFlowAnalyzer:
    """Analyze control flow patterns."""

    @staticmethod
    def identify_error_handling_patterns(symbols: List[Symbol]) -> Dict[str, List[str]]:
        """Identify error handling patterns across functions."""
        error_patterns = defaultdict(list)

        error_keywords = ["try", "catch", "except", "finally", "error", "throw", "raise"]

        for symbol in symbols:
            if symbol.type in ("function", "method"):
                for call in symbol.calls:
                    call_lower = call.lower()
                    for keyword in error_keywords:
                        if keyword in call_lower:
                            error_patterns[symbol.name].append(call)
                            break

        return dict(error_patterns)

    @staticmethod
    def identify_async_patterns(symbols: List[Symbol]) -> Dict[str, List[str]]:
        """Identify asynchronous execution patterns."""
        async_patterns = defaultdict(list)

        async_keywords = ["async", "await", "promise", "future", "callback", "then"]

        for symbol in symbols:
            if symbol.is_async or any(keyword in symbol.name.lower() for keyword in async_keywords):
                async_patterns[symbol.name].append("async_function")

            for call in symbol.calls:
                call_lower = call.lower()
                for keyword in async_keywords:
                    if keyword in call_lower:
                        async_patterns[symbol.name].append(call)
                        break

        return dict(async_patterns)


class CodeMetricsCalculator:
    """Calculate various code metrics from AST analysis."""

    @staticmethod
    def calculate_coupling(graph: DependencyGraph) -> Dict[str, float]:
        """Calculate coupling metrics for each module."""
        coupling = {}

        for identifier, node in graph.nodes.items():
            # Efferent coupling (outgoing dependencies)
            efferent = len(node.dependencies)

            # Afferent coupling (incoming dependencies)
            afferent = len(node.dependents)

            # Instability metric (0 = stable, 1 = unstable)
            total = efferent + afferent
            instability = efferent / total if total > 0 else 0

            coupling[identifier] = {
                "efferent": efferent,
                "afferent": afferent,
                "instability": instability,
            }

        return coupling

    @staticmethod
    def calculate_module_cohesion(node: DependencyNode) -> float:
        """Calculate module cohesion based on symbol relationships."""
        if not node.symbols:
            return 0.0

        # Count internal references vs external references
        internal_refs = 0
        total_refs = 0

        symbol_names = {s.name for s in node.symbols}

        for symbol in node.symbols:
            for ref in symbol.references:
                total_refs += 1
                if ref in symbol_names:
                    internal_refs += 1

        return internal_refs / total_refs if total_refs > 0 else 1.0

    @staticmethod
    def calculate_function_complexity_distribution(symbols: List[Symbol]) -> Dict[str, int]:
        """Calculate distribution of function complexities."""
        distribution = {"simple": 0, "moderate": 0, "complex": 0, "very_complex": 0}

        for symbol in symbols:
            if symbol.type in ("function", "method"):
                # Estimate complexity based on calls and nesting
                num_calls = len(symbol.calls)

                if num_calls <= 3:
                    distribution["simple"] += 1
                elif num_calls <= 7:
                    distribution["moderate"] += 1
                elif num_calls <= 15:
                    distribution["complex"] += 1
                else:
                    distribution["very_complex"] += 1

        return distribution


def build_cross_reference_map(symbols: List[Symbol]) -> Dict[str, List[str]]:
    """Build a cross-reference map showing where each symbol is used."""
    xref_map = defaultdict(list)

    for symbol in symbols:
        for ref in symbol.references:
            xref_map[ref].append(f"{symbol.file_path}:{symbol.name}")

    return dict(xref_map)


def identify_api_boundaries(symbols: List[Symbol]) -> List[Symbol]:
    """Identify public API boundaries (exported symbols)."""
    return [s for s in symbols if s.is_exported]


def detect_design_patterns(symbols: List[Symbol], graph: DependencyGraph) -> Dict[str, List[str]]:
    """Detect common design patterns in the code."""
    patterns = defaultdict(list)

    # Singleton pattern (class with getInstance or similar)
    for symbol in symbols:
        if symbol.type == "class":
            for method_symbol in symbols:
                if (
                    method_symbol.parent == symbol.name
                    and method_symbol.type == "method"
                    and "instance" in method_symbol.name.lower()
                ):
                    patterns["singleton"].append(symbol.name)
                    break

    # Factory pattern (create* methods)
    for symbol in symbols:
        if symbol.type in ("function", "method") and symbol.name.lower().startswith(("create", "make", "build")):
            patterns["factory"].append(symbol.name)

    # Observer pattern (subscribe/notify methods)
    observer_keywords = ["subscribe", "notify", "observer", "listen", "emit", "event"]
    for symbol in symbols:
        if symbol.type in ("function", "method"):
            if any(keyword in symbol.name.lower() for keyword in observer_keywords):
                patterns["observer"].append(symbol.name)

    # Decorator pattern (decorators in Python, wrapper functions)
    for symbol in symbols:
        if symbol.decorators or "decorator" in symbol.name.lower() or "wrapper" in symbol.name.lower():
            patterns["decorator"].append(symbol.name)

    return dict(patterns)
