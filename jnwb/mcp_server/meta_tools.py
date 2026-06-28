import ast
from pathlib import Path
from typing import Dict, Any
from jnwb.mcp_server.server import mcp

@mcp.tool()
def add_tool(code: str) -> Dict[str, Any]:
    """
    Validate and permanently add a new Python tool to the MCP server.
    
    Args:
        code: Python source code of the tool (must define at least one function).
        
    Returns:
        Structured JSON confirming registration or error dictionary.
    """
    try:
        parsed = ast.parse(code)
    except SyntaxError as e:
        return {
            "error": f"Syntax error in code: {str(e)}",
            "error_type": "ParseError"
        }
        
    func_defs = [node for node in parsed.body if isinstance(node, ast.FunctionDef)]
    if not func_defs:
        return {
            "error": "Code must contain at least one function definition (def my_func(...):)",
            "error_type": "ParseError"
        }
        
    func_name = func_defs[0].name
    
    # Check decorator list
    has_decorator = False
    for decorator in func_defs[0].decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr == 'tool':
                has_decorator = True
        elif isinstance(decorator, ast.Attribute) and decorator.attr == 'tool':
            has_decorator = True
            
    formatted_code = code.strip()
    if not has_decorator:
        formatted_code = f"@mcp.tool()\n{formatted_code}"
        
    custom_tools_file = Path(__file__).parent / "custom_tools.py"
    try:
        content = custom_tools_file.read_text()
        
        if f"def {func_name}" in content:
            return {
                "error": f"A function named '{func_name}' already exists in custom_tools.py.",
                "error_type": "DuplicateTool"
            }
            
        new_content = content.rstrip() + "\n\n" + formatted_code + "\n"
        custom_tools_file.write_text(new_content)
        
        return {
            "status": "success",
            "added_tool": func_name,
            "message": f"Tool '{func_name}' has been successfully validated and appended to custom_tools.py. Please restart the MCP server to load the new tool."
        }
    except Exception as e:
        return {
            "error": f"Failed to modify custom_tools.py: {str(e)}",
            "error_type": "Unknown"
        }
