from fastmcp import FastMCP

mcp = FastMCP("Mock Server 2")

@mcp.tool
def tool_c(z: bool) -> bool:
    """A simple tool in server 2."""
    return not z

@mcp.tool
def tool_d() -> str:
    """Another tool in server 2."""
    return "tool_d from server 2"

if __name__ == "__main__":
    mcp.run()
