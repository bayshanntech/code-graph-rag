"""Call processor for finding and resolving function/method calls."""

import re
from pathlib import Path
from typing import Any

from loguru import logger
from tree_sitter import Node, QueryCursor

from ..language_config import LanguageConfig
from ..services.graph_service import MemgraphIngestor
from .import_processor import ImportProcessor
from .type_inference import TypeInferenceEngine
from .utils import resolve_class_name


class CallProcessor:
    """Handles processing of function and method calls."""

    def __init__(
        self,
        ingestor: MemgraphIngestor,
        repo_path: Path,
        project_name: str,
        function_registry: Any,
        import_processor: ImportProcessor,
        type_inference: TypeInferenceEngine,
        class_inheritance: dict[str, list[str]],
    ):
        self.ingestor = ingestor
        self.repo_path = repo_path
        self.project_name = project_name
        self.function_registry = function_registry
        self.import_processor = import_processor
        self.type_inference = type_inference
        self.class_inheritance = class_inheritance

    def process_calls_in_file(
        self, file_path: Path, root_node: Node, language: str, queries: dict[str, Any]
    ) -> None:
        """Process function calls in a specific file using its cached AST."""
        relative_path = file_path.relative_to(self.repo_path)
        logger.debug(f"Processing calls in cached AST for: {relative_path}")

        try:
            module_qn = ".".join(
                [self.project_name] + list(relative_path.with_suffix("").parts)
            )
            if file_path.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )

            self._process_calls_in_functions(root_node, module_qn, language, queries)
            self._process_calls_in_classes(root_node, module_qn, language, queries)

        except Exception as e:
            logger.error(f"Failed to process calls in {file_path}: {e}")

    def _process_calls_in_functions(
        self, root_node: Node, module_qn: str, language: str, queries: dict[str, Any]
    ) -> None:
        """Process calls within top-level functions."""
        lang_queries = queries[language]
        lang_config: LanguageConfig = lang_queries["config"]

        query = lang_queries["functions"]
        cursor = QueryCursor(query)
        captures = cursor.captures(root_node)
        func_nodes = captures.get("function", [])
        for func_node in func_nodes:
            if not isinstance(func_node, Node):
                continue
            if self._is_method(func_node, lang_config):
                continue

            name_node = func_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            func_name = text.decode("utf8")
            func_qn = self._build_nested_qualified_name(
                func_node, module_qn, func_name, lang_config
            )

            if func_qn:
                self._ingest_function_calls(
                    func_node, func_qn, "Function", module_qn, language, queries
                )

    def _process_calls_in_classes(
        self, root_node: Node, module_qn: str, language: str, queries: dict[str, Any]
    ) -> None:
        """Process calls within class methods."""
        lang_queries = queries[language]

        query = lang_queries["classes"]
        cursor = QueryCursor(query)
        captures = cursor.captures(root_node)
        class_nodes = captures.get("class", [])

        for class_node in class_nodes:
            if not isinstance(class_node, Node):
                continue
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            class_name = text.decode("utf8")
            class_qn = f"{module_qn}.{class_name}"

            body_node = class_node.child_by_field_name("body")
            if not body_node:
                continue

            method_query = lang_queries["functions"]
            method_cursor = QueryCursor(method_query)
            method_captures = method_cursor.captures(body_node)
            method_nodes = method_captures.get("function", [])
            for method_node in method_nodes:
                if not isinstance(method_node, Node):
                    continue
                method_name_node = method_node.child_by_field_name("name")
                if not method_name_node:
                    continue
                text = method_name_node.text
                if text is None:
                    continue
                method_name = text.decode("utf8")
                method_qn = f"{class_qn}.{method_name}"

                self._ingest_function_calls(
                    method_node,
                    method_qn,
                    "Method",
                    module_qn,
                    language,
                    queries,
                    class_qn,
                )

    def _get_call_target_name(self, call_node: Node) -> str | None:
        """Extracts the name of the function or method being called."""
        # For 'call' in Python and 'call_expression' in JS/TS
        if func_child := call_node.child_by_field_name("function"):
            if func_child.type == "identifier":
                text = func_child.text
                if text is not None:
                    return str(text.decode("utf8"))
            # Python: obj.method() -> attribute
            elif func_child.type == "attribute":
                # Return the full attribute path
                text = func_child.text
                if text is not None:
                    return str(text.decode("utf8"))
            # JS/TS: obj.method() -> member_expression
            elif func_child.type == "member_expression":
                # Return the full member expression (e.g., "obj.method")
                text = func_child.text
                if text is not None:
                    return str(text.decode("utf8"))

        # For 'method_invocation' in Java
        if name_node := call_node.child_by_field_name("name"):
            text = name_node.text
            if text is not None:
                return str(text.decode("utf8"))

        return None

    def _ingest_function_calls(
        self,
        caller_node: Node,
        caller_qn: str,
        caller_type: str,
        module_qn: str,
        language: str,
        queries: dict[str, Any],
        class_context: str | None = None,
    ) -> None:
        """Find and ingest function calls within a caller node."""
        calls_query = queries[language].get("calls")
        if not calls_query:
            return

        local_var_types = self.type_inference.build_local_variable_type_map(
            caller_node, module_qn, language
        )

        cursor = QueryCursor(calls_query)
        captures = cursor.captures(caller_node)
        call_nodes = captures.get("call", [])

        for call_node in call_nodes:
            if not isinstance(call_node, Node):
                continue

            # Process nested calls first (inner to outer)
            self._process_nested_calls_in_node(
                call_node,
                caller_qn,
                caller_type,
                module_qn,
                local_var_types,
                class_context,
            )

            call_name = self._get_call_target_name(call_node)
            if not call_name:
                continue

            callee_info = self._resolve_function_call(
                call_name, module_qn, local_var_types, class_context
            )
            if not callee_info:
                continue

            callee_type, callee_qn = callee_info
            logger.debug(
                f"      Found call from {caller_qn} to {call_name} "
                f"(resolved as {callee_type}:{callee_qn})"
            )

            self.ingestor.ensure_relationship_batch(
                (caller_type, "qualified_name", caller_qn),
                "CALLS",
                (callee_type, "qualified_name", callee_qn),
            )

    def _process_nested_calls_in_node(
        self,
        call_node: Node,
        caller_qn: str,
        caller_type: str,
        module_qn: str,
        local_var_types: dict[str, str] | None,
        class_context: str | None,
    ) -> None:
        """Process nested call expressions within a call node's function expression."""
        # Get the function expression of this call
        func_child = call_node.child_by_field_name("function")
        if not func_child:
            return

        # If the function is an attribute (e.g., obj.method), check if obj contains calls
        if func_child.type == "attribute":
            # Recursively search for nested calls in the object part
            self._find_and_process_nested_calls(
                func_child,
                caller_qn,
                caller_type,
                module_qn,
                local_var_types,
                class_context,
            )

    def _find_and_process_nested_calls(
        self,
        node: Node,
        caller_qn: str,
        caller_type: str,
        module_qn: str,
        local_var_types: dict[str, str] | None,
        class_context: str | None,
    ) -> None:
        """Recursively find and process call expressions in a node tree."""
        # If this node is a call expression, process it
        if node.type == "call":
            # First process any nested calls within this call
            self._process_nested_calls_in_node(
                node, caller_qn, caller_type, module_qn, local_var_types, class_context
            )

            # Then process this call itself
            call_name = self._get_call_target_name(node)
            if call_name:
                callee_info = self._resolve_function_call(
                    call_name, module_qn, local_var_types, class_context
                )
                if callee_info:
                    callee_type, callee_qn = callee_info
                    logger.debug(
                        f"      Found nested call from {caller_qn} to {call_name} "
                        f"(resolved as {callee_type}:{callee_qn})"
                    )
                    self.ingestor.ensure_relationship_batch(
                        (caller_type, "qualified_name", caller_qn),
                        "CALLS",
                        (callee_type, "qualified_name", callee_qn),
                    )

        # Recursively search in all child nodes
        for child in node.children:
            self._find_and_process_nested_calls(
                child, caller_qn, caller_type, module_qn, local_var_types, class_context
            )

    def _resolve_function_call(
        self,
        call_name: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
        class_context: str | None = None,
    ) -> tuple[str, str] | None:
        """Resolve a function call to its qualified name and type."""
        # Phase 0: Handle super() calls specially
        if call_name.startswith("super()"):
            return self._resolve_super_call(call_name, module_qn, class_context)

        # Phase 0.5: Handle method chaining - check if this is a chained call
        if "." in call_name and self._is_method_chain(call_name):
            return self._resolve_chained_call(call_name, module_qn, local_var_types)

        # Phase 1: Check import mapping for 100% accurate resolution
        if module_qn in self.import_processor.import_mapping:
            import_map = self.import_processor.import_mapping[module_qn]

            # 1a.1. Direct import resolution
            if call_name in import_map:
                imported_qn = import_map[call_name]
                if imported_qn in self.function_registry:
                    logger.debug(
                        f"Direct import resolved: {call_name} -> {imported_qn}"
                    )
                    return self.function_registry[imported_qn], imported_qn

            # 1a.2. Handle qualified calls like "Class.method" and "self.attr.method"
            if "." in call_name:
                parts = call_name.split(".")

                # Special handling for self.attribute.method patterns
                if len(parts) >= 3 and parts[0] == "self":
                    attribute_ref = ".".join(parts[:-1])  # "self.repo"
                    method_name = parts[-1]  # "find_by_id"

                    # Check if we have type info for this attribute reference
                    if local_var_types and attribute_ref in local_var_types:
                        var_type = local_var_types[attribute_ref]

                        # Resolve var_type to full qualified name
                        if var_type in import_map:
                            class_qn = import_map[var_type]
                        else:
                            class_qn_or_none = self._resolve_class_name(
                                var_type, module_qn
                            )
                            class_qn = class_qn_or_none if class_qn_or_none else ""

                        if class_qn:
                            method_qn = f"{class_qn}.{method_name}"
                            if method_qn in self.function_registry:
                                logger.debug(
                                    f"Instance-resolved self-attribute call: "
                                    f"{call_name} -> {method_qn} "
                                    f"(via {attribute_ref}:{var_type})"
                                )
                                return self.function_registry[method_qn], method_qn

                            # Check inheritance for this method
                            inherited_method = self._resolve_inherited_method(
                                class_qn, method_name
                            )
                            if inherited_method:
                                logger.debug(
                                    f"Instance-resolved inherited self-attribute call: "
                                    f"{call_name} -> {inherited_method[1]} "
                                    f"(via {attribute_ref}:{var_type})"
                                )
                                return inherited_method
                else:
                    # Regular Class.method pattern
                    class_name = parts[0]
                    method_name = ".".join(parts[1:])

                    # Check if the class is imported
                    if class_name in import_map:
                        class_qn = import_map[class_name]
                        method_qn = f"{class_qn}.{method_name}"
                        if method_qn in self.function_registry:
                            logger.debug(
                                f"Import-resolved qualified call: "
                                f"{call_name} -> {method_qn}"
                            )
                            return self.function_registry[method_qn], method_qn

                    # Then, check if the base is a local variable with known type
                    if local_var_types and class_name in local_var_types:
                        var_type = local_var_types[class_name]

                        # The var_type might be a simple class name, resolve to full qn
                        if var_type in import_map:
                            class_qn = import_map[var_type]
                        else:
                            # Try to find the class in the same module or resolve it
                            class_qn_or_none = self._resolve_class_name(
                                var_type, module_qn
                            )
                            class_qn = class_qn_or_none if class_qn_or_none else ""

                        if class_qn:
                            method_qn = f"{class_qn}.{method_name}"
                            if method_qn in self.function_registry:
                                logger.debug(
                                    f"Instance-resolved qualified call: "
                                    f"{call_name} -> {method_qn} "
                                    f"(via {class_name}:{var_type})"
                                )
                                return self.function_registry[method_qn], method_qn

                            # If method not found in the class, check inheritance chain
                            inherited_method = self._resolve_inherited_method(
                                class_qn, method_name
                            )
                            if inherited_method:
                                inherited_method_qn = inherited_method[1]
                                logger.debug(
                                    f"Instance-resolved inherited call: "
                                    f"{call_name} -> {inherited_method_qn} "
                                    f"(via {class_name}:{var_type})"
                                )
                                return inherited_method

            # 1b. Check wildcard imports
            for local_name, imported_qn in import_map.items():
                if local_name.startswith("*"):
                    # Construct potential qualified name from wildcard import
                    potential_qns = []

                    # If the imported_qn contains '::', use '::' separator
                    if "::" in imported_qn:
                        potential_qns.append(f"{imported_qn}::{call_name}")
                    else:
                        # For languages like Java/Python/Scala that use '.'
                        potential_qns.append(f"{imported_qn}.{call_name}")
                        # Also try '::' in case the imported name is C++ style
                        potential_qns.append(f"{imported_qn}::{call_name}")

                    for wildcard_qn in potential_qns:
                        if wildcard_qn in self.function_registry:
                            logger.debug(
                                f"Wildcard-resolved call: {call_name} -> {wildcard_qn}"
                            )
                            return self.function_registry[wildcard_qn], wildcard_qn

        # Phase 2: Heuristic-based resolution (less accurate but often effective)
        # 2a. Check for a function in the same module
        same_module_func_qn = f"{module_qn}.{call_name}"
        if same_module_func_qn in self.function_registry:
            logger.debug(
                f"Same-module resolution: {call_name} -> {same_module_func_qn}"
            )
            return (
                self.function_registry[same_module_func_qn],
                same_module_func_qn,
            )

        # 2b. Use the Trie to find any matching symbol
        # This is a fallback and can be imprecise, but better than nothing.
        possible_matches = self.function_registry.find_ending_with(call_name)
        if possible_matches:
            # Sort candidates by likelihood (prioritize closer modules)
            possible_matches.sort(
                key=lambda qn: self._calculate_import_distance(qn, module_qn)
            )
            # Take the most likely candidate.
            best_candidate_qn = possible_matches[0]
            logger.debug(
                f"Trie-based fallback resolution: {call_name} -> {best_candidate_qn}"
            )
            return (
                self.function_registry[best_candidate_qn],
                best_candidate_qn,
            )

        logger.debug(f"Could not resolve call: {call_name}")
        return None

    def _is_method_chain(self, call_name: str) -> bool:
        """Check if this appears to be a method chain with parentheses (not just obj.method)."""
        # Look for patterns like: obj.method().other_method or obj.method("arg").other_method
        # But not simple patterns like: obj.method or self.attr
        if "(" in call_name and ")" in call_name:
            # Count method calls - if more than one, it's likely chaining
            parts = call_name.split(".")
            method_calls = sum(1 for part in parts if "(" in part and ")" in part)
            return method_calls >= 1 and len(parts) >= 2
        return False

    def _resolve_chained_call(
        self,
        call_name: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
    ) -> tuple[str, str] | None:
        """Resolve chained method calls like obj.method().other_method()."""
        # For chained calls like "processed_user.update_name('Updated').clone"
        # We need to resolve the return type of the inner call first

        # Handle the case where we have method(args).method format
        # Find the rightmost method that's not in parentheses

        # Pattern to find the final method call: anything.method
        # where method is at the end and not in parentheses
        match = re.search(r"\.([^.()]+)$", call_name)
        if not match:
            return None

        final_method = match.group(1)

        # Get the object expression (everything before the final method)
        object_expr = call_name[: match.start()]

        # Try to get the return type of the object expression
        object_type = self.type_inference._infer_expression_return_type(
            object_expr, module_qn, local_var_types
        )

        if object_type:
            # Convert object_type to full qualified name if it's a short name
            full_object_type = object_type
            if "." not in object_type:
                # This is a short class name, resolve to full qualified name
                resolved_class = self._resolve_class_name(object_type, module_qn)
                if resolved_class:
                    full_object_type = resolved_class

            # Now resolve the final method call on that type
            method_qn = f"{full_object_type}.{final_method}"

            if method_qn in self.function_registry:
                logger.debug(
                    f"Resolved chained call: {call_name} -> {method_qn} "
                    f"(via {object_expr}:{object_type})"
                )
                return self.function_registry[method_qn], method_qn

            # Also check inheritance for the final method
            inherited_method = self._resolve_inherited_method(
                full_object_type, final_method
            )
            if inherited_method:
                logger.debug(
                    f"Resolved chained inherited call: {call_name} -> {inherited_method[1]} "
                    f"(via {object_expr}:{object_type})"
                )
                return inherited_method

        return None

    def _resolve_super_call(
        self, call_name: str, module_qn: str, class_context: str | None = None
    ) -> tuple[str, str] | None:
        """Resolve super() calls to parent class methods."""
        # Extract method name from super() call
        # Examples: "super().__init__" -> "__init__", "super().start_engine" -> "start_engine"
        if "." in call_name:
            method_name = call_name.split(".", 1)[1]  # Get part after "super()."
        else:
            # Just "super()" - this shouldn't happen in normal calls but handle gracefully
            return None

        # Use the provided class context
        current_class_qn = class_context
        if not current_class_qn:
            logger.debug(f"No class context provided for super() call: {call_name}")
            return None

        # Look up parent classes for the current class
        if current_class_qn not in self.class_inheritance:
            logger.debug(f"No inheritance info for class {current_class_qn}")
            return None

        parent_classes = self.class_inheritance[current_class_qn]
        if not parent_classes:
            logger.debug(f"No parent classes found for {current_class_qn}")
            return None

        # Use inheritance chain traversal to find the method
        result = self._resolve_inherited_method(current_class_qn, method_name)
        if result:
            callee_type, parent_method_qn = result
            logger.debug(f"Resolved super() call: {call_name} -> {parent_method_qn}")
            return callee_type, parent_method_qn

        logger.debug(
            f"Could not resolve super() call: {call_name} in parents of {current_class_qn}"
        )
        return None

    def _resolve_inherited_method(
        self, class_qn: str, method_name: str
    ) -> tuple[str, str] | None:
        """Resolve a method by looking up the inheritance chain."""
        # Check if we have inheritance information for this class
        if class_qn not in self.class_inheritance:
            return None

        # Use a queue for breadth-first search through the inheritance hierarchy
        queue = list(self.class_inheritance.get(class_qn, []))
        visited = set(queue)

        while queue:
            parent_class_qn = queue.pop(0)
            parent_method_qn = f"{parent_class_qn}.{method_name}"

            # Check if the method exists in the current parent class
            if parent_method_qn in self.function_registry:
                return (
                    self.function_registry[parent_method_qn],
                    parent_method_qn,
                )

            # Add the parent's parents to the queue for further searching
            if parent_class_qn in self.class_inheritance:
                for grandparent_qn in self.class_inheritance[parent_class_qn]:
                    if grandparent_qn not in visited:
                        visited.add(grandparent_qn)
                        queue.append(grandparent_qn)

        return None

    def _calculate_import_distance(
        self, candidate_qn: str, caller_module_qn: str
    ) -> int:
        """
        Calculate the 'distance' between a candidate function and the calling module.
        Lower values indicate more likely imports (closer modules, common prefixes).
        """
        caller_parts = caller_module_qn.split(".")
        candidate_parts = candidate_qn.split(".")

        # Find common prefix length (how many package levels they share)
        common_prefix = 0
        for i in range(min(len(caller_parts), len(candidate_parts))):
            if caller_parts[i] == candidate_parts[i]:
                common_prefix += 1
            else:
                break

        # Calculate base distance (inverse of common prefix)
        base_distance = max(len(caller_parts), len(candidate_parts)) - common_prefix

        # Bonus for candidates that are "close" in the module hierarchy
        if candidate_qn.startswith(".".join(caller_parts[:-1]) + "."):
            base_distance -= 1

        return base_distance

    def _resolve_class_name(self, class_name: str, module_qn: str) -> str | None:
        """Convert a simple class name to its fully qualified name."""
        return resolve_class_name(
            class_name, module_qn, self.import_processor, self.function_registry
        )

    def _build_nested_qualified_name(
        self,
        func_node: Node,
        module_qn: str,
        func_name: str,
        lang_config: LanguageConfig,
    ) -> str | None:
        """Build qualified name for nested functions."""
        path_parts = []
        current = func_node.parent

        if not isinstance(current, Node):
            logger.warning(
                f"Unexpected parent type for node {func_node}: {type(current)}. "
                f"Skipping."
            )
            return None

        while current and current.type not in lang_config.module_node_types:
            if current.type in lang_config.function_node_types:
                if name_node := current.child_by_field_name("name"):
                    text = name_node.text
                    if text is not None:
                        path_parts.append(text.decode("utf8"))
            elif current.type in lang_config.class_node_types:
                return None  # This is a method

            current = current.parent

        path_parts.reverse()
        if path_parts:
            return f"{module_qn}.{'.'.join(path_parts)}.{func_name}"
        else:
            return f"{module_qn}.{func_name}"

    def _is_method(self, func_node: Node, lang_config: LanguageConfig) -> bool:
        """Check if a function is actually a method inside a class."""
        current = func_node.parent
        if not isinstance(current, Node):
            return False

        while current and current.type not in lang_config.module_node_types:
            if current.type in lang_config.class_node_types:
                return True
            current = current.parent
        return False
