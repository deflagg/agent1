# server.py
from mcp.server.fastmcp import FastMCP
from python_repl import PythonREPL

# Create an MCP server
mcp = FastMCP("demo-server")

@mcp.tool()
def execute_code(code: str) -> str:
    """
    Execute the code and return the output.
    Perform any calculations
    Args:
        code: The code to execute
    Returns:
        str: The output of the code
    """
    print(f"Executing code on the server: {code}")
    python_repl = PythonREPL()
    result =python_repl.run(code)
    return result

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers
    Args:
        a: The first number to add
        b: The second number to add
    Returns:
        The sum of the two numbers
    """
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Start the server if this file is run directly
if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run()