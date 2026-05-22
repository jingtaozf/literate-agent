import ast
import sys
import time
import weakref
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class ImportData:
    """Represents an import statement in a module."""

    module: str  # Source module (e.g., "module_a")
    definition: str  # Name in importing module (e.g., "func" or "alias_func")
    imported_symbol: Optional[str] = None  # Original symbol (e.g., "module_a.func")
    is_alias: bool = False  # Whether it's imported with an alias
    is_wildcard: bool = False  # Whether it's from module import *


@dataclass
class ModuleInfo:
    """Information about a module and its dependencies."""

    name: str
    imports: List[ImportData] = field(default_factory=list)
    imported_by: Set[str] = field(default_factory=set)  # Modules that import from this
    last_modified: float = field(default_factory=time.time)
    top_level_names: Set[str] = field(default_factory=set)


def extract_imports_from_code(code: str, module_name: str) -> List[ImportData]:
    """Extract import statements from Python code."""
    imports = []
    # # Walk the AST; bail to an empty list on parse failure.
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # # Plain `import X` / `import X as Y` — one entry per name in the import list.
            if isinstance(node, ast.Import):
                # Handle: import module_a, module_b as b
                for alias in node.names:
                    imports.append(
                        ImportData(
                            module=alias.name,
                            definition=alias.asname or alias.name,
                            imported_symbol=None,
                            is_alias=alias.asname is not None,
                            is_wildcard=False,
                        )
                    )
            # # `from X import ...` — split the wildcard case from the named-symbol case.
            elif isinstance(node, ast.ImportFrom):
                if node.module:  # from module import ...
                    for alias in node.names:
                        if alias.name == "*":
                            # from module import *
                            imports.append(
                                ImportData(
                                    module=node.module,
                                    definition="*",
                                    imported_symbol=None,
                                    is_alias=False,
                                    is_wildcard=True,
                                )
                            )
                        else:
                            # from module import name [as alias]
                            imports.append(
                                ImportData(
                                    module=node.module,
                                    definition=alias.asname or alias.name,
                                    imported_symbol=f"{node.module}.{alias.name}",
                                    is_alias=alias.asname is not None,
                                    is_wildcard=False,
                                )
                            )
    # # Syntax-broken code is logged and treated as "no imports".
    except SyntaxError:
        logger.warning(f"Failed to parse imports from code in module {module_name}")
    return imports


class ModuleReloader:
    """Manages module dependencies and hot reloading."""

    def __init__(self):
        # Track module information
        self.modules: Dict[str, ModuleInfo] = {}
        # Track stale modules that need reloading
        self.stale_modules: Set[str] = set()
        # Object references for patching
        self.old_objects: Dict[Tuple[str, str], List[weakref.ref]] = {}

    def register_module(self, module_name: str) -> ModuleInfo:
        """Register a module if not already registered."""
        if module_name not in self.modules:
            self.modules[module_name] = ModuleInfo(name=module_name)
        return self.modules[module_name]

    def track_module_execution(
        self, module_name: str, code: str, top_level_names: Set[str]
    ) -> Set[str]:
        """Track when a module is executed and return affected modules."""
        # Register this module
        module_info = self.register_module(module_name)

        # Extract imports from the code
        imports = extract_imports_from_code(code, module_name)
        module_info.imports = imports
        module_info.top_level_names = top_level_names
        module_info.last_modified = time.time()

        # Update imported_by relationships
        for import_data in imports:
            if import_data.module in self.modules:
                self.modules[import_data.module].imported_by.add(module_name)

        # Find modules that import from this module
        affected_modules = self.find_dependent_modules(module_name)

        # Mark them as stale
        self.stale_modules.update(affected_modules)

        return affected_modules

    def find_dependent_modules(self, module_name: str) -> Set[str]:
        """Find all modules that depend on the given module."""
        if module_name not in self.modules:
            return set()

        dependent = set()
        module_info = self.modules[module_name]

        # Direct dependencies
        dependent.update(module_info.imported_by)

        # Transitive dependencies (modules that import the dependent modules)
        to_check = list(dependent)
        checked = {module_name}

        while to_check:
            checking = to_check.pop()
            if checking in checked:
                continue
            checked.add(checking)

            if checking in self.modules:
                new_deps = self.modules[checking].imported_by
                for dep in new_deps:
                    if dep not in checked:
                        dependent.add(dep)
                        to_check.append(dep)

        return dependent

    def update_dependent_modules(self, source_module: str) -> Dict[str, List[str]]:
        """Update symbols in modules that import from source_module."""
        updates = {}

        # # Bail unless the source module is loaded *and* tracked by the reloader.
        if source_module not in sys.modules:
            return updates

        source_mod = sys.modules[source_module]
        module_info = self.modules.get(source_module)

        if not module_info:
            return updates

        # # For every module that imports from `source_module`, find its tracked metadata or skip.
        for dependent_module_name in module_info.imported_by:
            if dependent_module_name not in sys.modules:
                continue

            dependent_mod = sys.modules[dependent_module_name]
            dependent_info = self.modules.get(dependent_module_name)

            if not dependent_info:
                continue

            updated_names = []

            # # Walk that module's imports and dispatch on the import shape: wildcard / named / module-only.
            for import_data in dependent_info.imports:
                if import_data.module != source_module:
                    continue

                if import_data.is_wildcard:
                    # Handle from module import *
                    for name in module_info.top_level_names:
                        if hasattr(source_mod, name):
                            setattr(dependent_mod, name, getattr(source_mod, name))
                            updated_names.append(name)
                elif import_data.imported_symbol:
                    # Handle from module import name [as alias]
                    # Extract the actual name from imported_symbol
                    parts = import_data.imported_symbol.split(".")
                    if len(parts) > 1:
                        actual_name = parts[-1]
                        if hasattr(source_mod, actual_name):
                            # Update with the correct name (definition is the alias or original)
                            setattr(
                                dependent_mod,
                                import_data.definition,
                                getattr(source_mod, actual_name),
                            )
                            updated_names.append(import_data.definition)
                else:
                    # Handle import module [as alias]
                    # Update the module reference itself
                    setattr(dependent_mod, import_data.definition, source_mod)
                    updated_names.append(import_data.definition)

            # # Record the rebound names per dependent module and return the full map.
            if updated_names:
                updates[dependent_module_name] = updated_names

        return updates

    def clear_stale_modules(self):
        """Clear the set of stale modules."""
        self.stale_modules.clear()

    def get_import_info(self, module_name: str) -> List[ImportData]:
        """Get import information for a module."""
        if module_name in self.modules:
            return self.modules[module_name].imports
        return []
