import asyncio
import json
import os
from pathlib import Path
import argparse
from typing import Any, Dict, List

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.tools.tool import Tool
from fastmcp.tools.tool_transform import TransformedTool


class MCPProxy:
    def __init__(self, config: Dict[str, Any], proxy_config_name: str):
        self.config = config
        self.proxy_config_name = proxy_config_name
        self.mcp_server = FastMCP(f"MCP Filter: {self.proxy_config_name}")
        self._clients: Dict[str, Client] = {}

    async def start_upstream_servers(self):
        """Starts all configured MCP servers as subprocesses."""
        for name, server_config in self.config.get("mcpServers", {}).items():
            command = server_config["command"]
            args = server_config.get("args", [])
            transport = StdioTransport(command=command, args=args)
            self._clients[name] = Client(transport)
            # We don't connect here, we connect when we need to get tools

    async def stop_upstream_servers(self):
        """Stops all running upstream MCP servers."""
        # The transports manage the lifecycle of the subprocesses.
        # When this process exits, the children will be terminated.
        pass

    async def build_server(self):
        """Builds the proxy MCP server based on the selected configuration."""
        proxy_config = self.config["proxyConfigs"].get(self.proxy_config_name)
        if not proxy_config:
            raise ValueError(f"Proxy configuration '{self.proxy_config_name}' not found.")

        server_mappings = proxy_config.get("serverMappings", {})
        filtering_rules = proxy_config.get("filtering", {})

        for server_name, mapping_info in server_mappings.items():
            if server_name not in self._clients:
                print(f"Warning: Server '{server_name}' from proxy config not found in mcpServers.")
                continue

            client = self._clients[server_name]
            async with client:
                remote_tools = await client.list_tools()
                allowed_tools = filtering_rules.get(server_name)

                for remote_tool in remote_tools:
                    if allowed_tools and remote_tool.name not in allowed_tools:
                        continue

                    tool_name = self._get_tool_name(remote_tool.name, server_name, mapping_info)

                    # Create a wrapper tool
                    wrapper_tool = self._create_wrapper_tool(client, remote_tool, tool_name)
                    self.mcp_server.add_tool(wrapper_tool)

    def _get_tool_name(self, original_name: str, server_name: str, mapping_info: Dict[str, Any]) -> str:
        mapping_type = mapping_info.get("type", "passthrough")
        if mapping_type == "prefix":
            prefix = mapping_info.get("prefix", server_name)
            return f"{prefix}_{original_name}"
        elif mapping_type == "explicit":
            return mapping_info.get("map", {}).get(original_name, original_name)
        else: # passthrough
            return original_name

    def _create_wrapper_tool(self, client: Client, remote_tool, new_name: str) -> TransformedTool:
        """Creates a local tool that calls the remote tool."""

        # Manually create a fastmcp.tools.tool.Tool from the remote_tool
        tool_for_transform = Tool(
            name=remote_tool.name,
            description=remote_tool.description,
            parameters=remote_tool.inputSchema,
            title=remote_tool.title if hasattr(remote_tool, 'title') else new_name,
            tags=remote_tool.tags if hasattr(remote_tool, 'tags') else set(),
            output_schema=remote_tool.outputSchema if hasattr(remote_tool, 'outputSchema') else None,
            serializer=remote_tool.serializer if hasattr(remote_tool, 'serializer') else None,
        )

        async def transform_fn(**kwargs):
            return await client.call_tool(remote_tool.name, **kwargs)

        wrapper = Tool.from_tool(
            tool=tool_for_transform,
            transform_fn=transform_fn,
            name=new_name,
            description=remote_tool.description,
        )
        return wrapper


def load_config(config_path_str: str) -> Dict[str, Any]:
    """Loads the JSON configuration file."""
    if not config_path_str:
        config_path_str = os.environ.get("MCP_FILTER_CONFIG", "~/.mcp_filter/config.json")

    config_path = Path(config_path_str).expanduser()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, "r") as f:
        return json.load(f)


async def main():
    parser = argparse.ArgumentParser(description="MCP Tool Filter")
    parser.add_argument("proxy_config_name", help="The name of the proxyConfig to use.")
    parser.add_argument("--config", help="Path to the configuration file.", default=None)
    parser.add_argument("--transport", help="Server transport.", default="stdio", choices=["stdio", "tcp"])
    parser.add_argument("--port", help="Server port for TCP transport.", type=int, default=8080)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading configuration: {e}")
        return

    proxy = MCPProxy(config, args.proxy_config_name)
    await proxy.start_upstream_servers()
    await proxy.build_server()

    # Use 'http' for the server transport, as 'tcp' is not recognized by run_async
    server_transport = "http" if args.transport == "tcp" else args.transport
    server_task = asyncio.create_task(
        proxy.mcp_server.run_async(transport=server_transport, port=args.port)
    )

    try:
        await server_task
    except asyncio.CancelledError:
        pass
    finally:
        await proxy.stop_upstream_servers()


if __name__ == "__main__":
    asyncio.run(main())
