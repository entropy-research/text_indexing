# ast_extractor.py

import ast
from codebase_graph import add_node, add_edge
import networkx as nx
import os
from constants import built_in_functions
from ast_parser import parse_python_file
from graph_visualization import print_node_edge_attributes
import importlib.util

def get_module_path(module_name, current_file_path, python_files):
    """ Try to find the path of the module relative to the current file. """
    # Check if the module is a relative import
    if module_name.startswith('.'):
        # Get the directory of the current file
        current_dir = os.path.dirname(current_file_path)
        
        # Resolve the relative import path
        relative_path = os.path.normpath(os.path.join(current_dir, module_name.replace('.', os.path.sep)))
        
        # Find the file path of the module
        module_file_path = find_file_in_directory(relative_path)
        
        if module_file_path:
            return module_file_path
    
    # If not a relative import, search for the module in the codebase
    for file_path in python_files:
        if file_path.endswith(module_name.replace('.', os.path.sep) + '.py'):
            return file_path
    
    # If the module is not found in the codebase, try to find it using importlib.util
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None and spec.origin is not None:
            return spec.origin
    except ImportError:
        pass
    
    # If the module is not found, return None
    return None

def find_file_in_directory(path):
    """ Find the file in the given directory or its subdirectories. """
    if os.path.isfile(path + '.py'):
        return path + '.py'
    
    if os.path.isdir(path):
        init_file = os.path.join(path, '__init__.py')
        if os.path.isfile(init_file):
            return init_file
        
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    return os.path.join(root, file)
    
    return None

imported_functions = {}


def extract_info_from_ast(graph, ast_tree, file_path, python_files):
    # Add file node to the graph

    with open(file_path, 'r') as file:
        file_content = file.read()

    file_attrs = {
        "type": "file",
        "file_path": file_path,
        "code": file_content  # Add the file content as an attribute
    }
    add_node(graph, file_path, file_attrs)

    # Add directory node to the graph
    directory_path = os.path.dirname(file_path)
    directory_attrs = {
        "type": "directory",
        "directory_path": directory_path,
    }
    add_node(graph, directory_path, directory_attrs)

    # Add edge from directory to file
    add_edge(graph, directory_path, file_path, "contains", {})

    # Define a visitor class to traverse the AST
        # Define a visitor class to traverse the AST

    imported_functions = {}
    
    class ASTVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_scope = []
            self.imported_modules = {}

        def visit_ClassDef(self, node):
            class_name = node.name
            class_lineno = node.lineno
            class_attrs = {
                "type": "class",
                "code": ast.unparse(node),
                "doc": ast.get_docstring(node),
                "location": {
                    "file_path": file_path,
                    "start_line": class_lineno,
                    "end_line": class_lineno + len(node.body) - 1,
                },
                "dependencies": {
                    "imports": [],
                    "exported": [],
                },
            }

            # Add the class node to the graph
            add_node(graph, class_name, class_attrs)

            # Add edge from file to class
            add_edge(graph, file_path, class_name, "defines", {})

            # Update the current scope
            self.current_scope.append(class_name)

            # Visit the body of the class
            self.generic_visit(node)

            # Remove the class from the current scope
            self.current_scope.pop()

        def visit_FunctionDef(self, node):
            function_name = node.name
            function_lineno = node.lineno
            function_end_lineno = node.end_lineno
            function_attrs = {
                "type": "function",
                "code": ast.unparse(node),
                "doc": ast.get_docstring(node),
                "location": {
                    "file_path": file_path,
                    "start_line": function_lineno,
                    "end_line": function_end_lineno,
                },
                "dependencies": {
                    "imports": [],
                    "exported": [],
                },
            }

            # Generate a unique identifier for the function node
            if self.current_scope:
                parent_scope = self.current_scope[-1]
                function_id = f"{parent_scope}.{function_name}"
            else:
                function_id = f"{file_path}:{function_name}"

            # Add the function node to the graph
            
            add_node(graph, function_id, function_attrs)

            # Add edge from the current scope to the function
            if self.current_scope:
                parent = self.current_scope[-1]
                add_edge(graph, parent, function_id, "defines", {"ref_location": {"file_path": file_path, "line_number": function_lineno}})
            else:
                # If not inside a class, add edge from file to function
                
                add_edge(graph, file_path, function_id, "defines", {"ref_location": {"file_path": file_path, "line_number": function_lineno}})

            # Update the current scope
            self.current_scope.append(function_id)

            # Visit the body of the function
            self.generic_visit(node)

            # Remove the function from the current scope
            self.current_scope.pop()

        # def visit_Import(self, node):
        #     for alias in node.names:
        #         imported_module = alias.name
        #         import_lineno = node.lineno

        #         # Find the file path of the imported module
        #         module_file_path = get_module_path(imported_module, file_path, python_files)

        #         # Get the alias name, if used
        #         alias_name = alias.asname if alias.asname else imported_module

        #         # Store the imported module and its alias in the imported_modules dictionary
        #         self.imported_modules[alias_name] = {
        #             "module": imported_module,
        #             "file_path": module_file_path
        #         }

        #         # Add the imported module to the dependencies of the current scope
        #         if self.current_scope:
        #             current_node = self.current_scope[-1]
        #             if current_node in graph.nodes:
        #                 graph.nodes[current_node]["dependencies"]["imports"].append({
        #                     "module": imported_module,
        #                     "alias": alias_name
        #                 })
        #                 add_edge(graph, current_node, f"{module_file_path}:{imported_module}", "imports", {
        #                     "ref_location": {
        #                         "file_path": module_file_path,
        #                         "line_number": import_lineno
        #                     },
        #                     "alias": alias_name
        #                 })
        #         else:
        #             # If not inside a function or class, add the import to the file dependencies
        #             file_node = file_path
        #             if file_node in graph.nodes:
        #                 graph.nodes[file_node]["dependencies"]["imports"].append({
        #                     "module": imported_module,
        #                     "alias": alias_name
        #                 })
        #                 add_edge(graph, file_node, f"{module_file_path}:{imported_module}", "imports", {
        #                     "ref_location": {
        #                         "file_path": module_file_path,
        #                         "line_number": import_lineno
        #                     },
        #                     "alias": alias_name
        #                 })

        # def visit_ImportFrom(self, node):
        #     imported_module = node.module
        #     import_lineno = node.lineno

        #     if imported_module is None:
        #         # Handle the case where imported_module is None
        #         imported_module = ""

        #     # Find the file path of the imported module
        #     module_file_path = get_module_path(imported_module, file_path, python_files)

        #     # Store the imported module and its file path in the imported_modules dictionary
        #     self.imported_modules[imported_module] = {
        #         "module": imported_module,
        #         "file_path": module_file_path
        #     }

        #     # Store the imported functions in the imported_functions dictionary
        #     for alias in node.names:
        #         imported_name = alias.name
        #         alias_name = alias.asname if alias.asname else imported_name

        #         imported_functions[alias_name] = {
        #             "module": imported_module,
        #             "name": imported_name,
        #             "file_path": module_file_path
        #         }

        #         # Add the imported module to the dependencies of the current scope
        #         if self.current_scope:
        #             current_node = self.current_scope[-1]
        #             if current_node in graph.nodes:
        #                 graph.nodes[current_node]["dependencies"]["imports"].append({
        #                     "module": imported_module,
        #                     "alias": alias_name
        #                 })
        #                 add_edge(graph, current_node, f"{module_file_path}:{imported_module}", "imports", {
        #                     "ref_location": {
        #                         "file_path": module_file_path,
        #                         "line_number": import_lineno
        #                     },
        #                     "alias": alias_name
        #                 })
        #         else:
        #             # If not inside a function or class, add the import to the file dependencies
        #             file_node = file_path
        #             if file_node in graph.nodes:
        #                 graph.nodes[file_node]["dependencies"]["imports"].append({
        #                     "module": imported_module,
        #                     "alias": alias_name
        #                 })
        #                 add_edge(graph, file_node, f"{module_file_path}:{imported_module}", "imports", {
        #                     "ref_location": {
        #                         "file_path": module_file_path,
        #                         "line_number": import_lineno
        #                     },
        #                     "alias": alias_name
        #                 })
        
        # def visit_Call(self, node):
        #     # Initialize the called_function variable to None
        #     # This variable will store the name of the called function
        #     called_function = None
            
        #     # Check if the called function is a simple name (e.g., function_name())
        #     if isinstance(node.func, ast.Name):
        #         # If it is a simple name, store the function name in called_function
        #         called_function = node.func.id
            
        #     # Check if the called function is an attribute (e.g., object.method())
        #     elif isinstance(node.func, ast.Attribute):
        #         # Check if the value of the attribute is a name (e.g., object.method())
        #         if isinstance(node.func.value, ast.Name):
        #             # If it is a name, store the entire function call in called_function
        #             # This includes the object name and the method name (e.g., "object.method")
        #             called_function = f"{node.func.value.id}.{node.func.attr}"
                    
        #             # Split the called_function by dots to handle method calls on instances of imported classes
        #             called_function_parts = called_function.split(".")
                    
        #             # Check if the called_function has more than one part (e.g., "object.method")
        #             if len(called_function_parts) > 1:
        #                 # If it has more than one part, consider it as a method call on an instance of an imported class
        #                 # Update the called_function to include only the class name (e.g., "object")
        #                 # This is necessary to correctly identify the target node for the call edge
        #                 called_function = ".".join(called_function_parts[:-1])
            
        #     # Check if the called function is itself a function call (e.g., outer_func(inner_func()))
        #     elif isinstance(node.func, ast.Call):
        #         # If it is a nested function call, recursively visit the inner function call
        #         # This ensures that the inner function call is also processed and added to the graph if necessary
        #         self.visit(node.func)
            
        #     # If a called function is found (not None)
        #     if called_function:
        #         # Get the line number of the function call
        #         call_lineno = node.lineno
                
                
        #         # Check if the function call is made within a scope (e.g., inside a function or class)
        #         if self.current_scope:
        #             # If it is within a scope, get the current scope as the caller
        #             caller = self.current_scope[-1]
                    
        #             if called_function in built_in_functions:
        #                 # The called function is a built-in function
        #                 add_edge(graph, caller, called_function, "calls", {
        #                     "file_path": None,
        #                     "line_number": call_lineno,
        #                     "imported_from": "built-in"
        #                 })
        #             else:
        #                 # Check if the called function is an imported module or a specific imported function
        #                 if called_function in self.imported_modules:
        #                     # The called function is an imported module
        #                     imported_module = self.imported_modules[called_function]
        #                     module_file_path = imported_module["file_path"]

        #                     if ("./tests/test_project/main.py" == file_path) :
        #                         print(called_function)
        #                         print(imported_module)
        #                         print(module_file_path)
        #                         print("--")
        #                     if module_file_path:
        #                         add_edge(graph, caller, f"{module_file_path}:{called_function}", "calls", {
        #                             "file_path": module_file_path,
        #                             "line_number": call_lineno,
        #                             "imported_from": "codebase"
        #                         })
        #                     else:
        #                         add_edge(graph, caller, called_function, "calls", {
        #                             "file_path": None,
        #                             "line_number": call_lineno,
        #                             "imported_from": "pip"
        #                         })
        #                 elif called_function in imported_functions:
        #                     # The called function is a specific imported function
        #                     imported_function = imported_functions[called_function]
        #                     module_file_path = imported_function["file_path"]
        #                     if ("./tests/test_project/main.py" == file_path) :
        #                         print(called_function)
        #                         print(imported_function)
        #                         print(module_file_path)
        #                         print("--")
        #                     if module_file_path:
        #                         add_edge(graph, caller, f"{module_file_path}:{imported_function['name']}", "calls", {
        #                             "file_path": module_file_path,
        #                             "line_number": call_lineno,
        #                             "imported_from": "codebase"
        #                         })
        #                     else:
        #                         add_edge(graph, caller, called_function, "calls", {
        #                             "file_path": None,
        #                             "line_number": call_lineno,
        #                             "imported_from": "pip"
        #                         })
        #                 else:
        #                     # Consider it as a function call within the codebase
        #                     # Add a "calls" edge from the caller to the called function
        #                     # print(call)
        #                     add_edge(graph, caller, f"{file_path}:{called_function}", "calls", {
        #                         "file_path": file_path,
        #                         "line_number": call_lineno,
        #                         "imported_from": "codebase"
        #                     })
                
        #         # If the function call is made at the top level of the module (not within any scope)
        #         else:
        #             # Set the caller as the file path itself
        #             caller = file_path
                    
        #             if called_function in built_in_functions:
        #                 # The called function is a built-in function
        #                 add_edge(graph, caller, called_function, "calls", {
        #                     "file_path": None,
        #                     "line_number": call_lineno,
        #                     "imported_from": "built-in"
        #                 })
        #             else:
        #                 # Check if the called function is an imported module or a specific imported function
        #                 if called_function in self.imported_modules:
        #                     # The called function is an imported module
        #                     imported_module = self.imported_modules[called_function]
        #                     module_file_path = imported_module["file_path"]
        #                     if module_file_path:
        #                         add_edge(graph, caller, f"{module_file_path}:{called_function}", "calls", {
        #                             "file_path": module_file_path,
        #                             "line_number": call_lineno,
        #                             "imported_from": "codebase"
        #                         })
        #                     else:
        #                         add_edge(graph, caller, called_function, "calls", {
        #                             "file_path": None,
        #                             "line_number": call_lineno,
        #                             "imported_from": "pip"
        #                         })
        #                 elif called_function in imported_functions:
        #                     # The called function is a specific imported function
        #                     imported_function = imported_functions[called_function]
        #                     module_file_path = imported_function["file_path"]
        #                     if module_file_path:
        #                         add_edge(graph, caller, f"{module_file_path}:{imported_function['name']}", "calls", {
        #                             "file_path": module_file_path,
        #                             "line_number": call_lineno,
        #                             "imported_from": "codebase"
        #                         })
        #                     else:
        #                         add_edge(graph, caller, called_function, "calls", {
        #                             "file_path": None,
        #                             "line_number": call_lineno,
        #                             "imported_from": "pip"
        #                         })
        #                 else:
        #                     # Consider it as a function call within the codebase
        #                     # Add a "calls" edge from the file node to the called function
        #                     add_edge(graph, caller, f"{file_path}:{called_function}", "calls", {
        #                         "file_path": file_path,
        #                         "line_number": call_lineno,
        #                         "imported_from": "codebase"
        #                     })


    # Create an instance of the ASTVisitor
    visitor = ASTVisitor()

    # Traverse the AST using the visitor
    visitor.visit(ast_tree)

    # Update the graph metadata
    graph.graph["total_nodes"] = len(graph.nodes)
    graph.graph["total_edges"] = len(graph.edges)
    graph.graph["disconnected_components"] = list(nx.weakly_connected_components(graph))



def find_module_file(module_name, python_files):
    # print(python_files)
    for file_path in python_files:
        if file_path.endswith(f"{module_name}.py"):
            return file_path
    return None

def find_imported_name_lineno(module_ast, imported_name):
    class ImportedNameFinder(ast.NodeVisitor):
        def __init__(self, imported_name):
            self.imported_name = imported_name
            self.lineno = None

        def visit_FunctionDef(self, node):
            if node.name == self.imported_name:
                self.lineno = node.lineno
                return

        def visit_ClassDef(self, node):
            if node.name == self.imported_name:
                self.lineno = node.lineno
                return

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == self.imported_name:
                    self.lineno = node.lineno
                    return

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name == self.imported_name:
                    self.lineno = node.lineno
                    return

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name == self.imported_name:
                    self.lineno = node.lineno
                    return

        def generic_visit(self, node):
            if self.lineno is None:
                super().generic_visit(node)

    finder = ImportedNameFinder(imported_name)
    finder.visit(module_ast)
    return finder.lineno


def find_file_in_directory(path):
    """ Find the file in the given directory or its subdirectories. """
    if os.path.isfile(path + '.py'):
        return path + '.py'
    
    if os.path.isdir(path):
        init_file = os.path.join(path, '__init__.py')
        if os.path.isfile(init_file):
            return init_file
        
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    return os.path.join(root, file)
    
    return None