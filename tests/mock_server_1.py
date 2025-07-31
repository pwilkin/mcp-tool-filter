from fastmcp import FastMCP

mcp = FastMCP("Mock Server 1")

@mcp.tool
def tool_a(x: int) -> int:
    """A simple tool in server 1."""
    return x * 2

@mcp.tool
def tool_b(y: str) -> str:
    """Another tool in server 1."""
    return f"Hello, {y}"

if __name__ == "__main__":
    mcp.run()
