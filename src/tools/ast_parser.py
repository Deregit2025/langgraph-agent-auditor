import ast
from typing import List

# ------------------------------
# Parse Python code and extract classes, functions, and imports
# ------------------------------
def parse_ast(file_content: str) -> dict:
    """
    Parse Python source code and return dictionary containing:
    - classes: list of class names
    - functions: list of function names
    - imports: list of imported modules
    """
    tree = ast.parse(file_content)
    classes = []
    functions = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else ""
            for n in node.names:
                imports.append(f"{module}.{n.name}" if module else n.name)

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports
    }


# ------------------------------
# Example: check if a specific class inherits from BaseModel
# ------------------------------
def class_inherits_base_model(file_content: str, class_name: str) -> bool:
    tree = ast.parse(file_content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    return True
                elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                    return True
    return False