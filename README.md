# MCP Tool Filter

This project provides a flexible and configurable MCP (Model-Context-Protocol) server that acts as a proxy to other MCP servers. It allows you to filter the tools exposed by upstream servers and modify their names.

## Features

- **Proxy multiple MCP servers**: Combine tools from different MCP servers into a single endpoint.
- **Tool Filtering**: Restrict the list of available tools from each upstream server.
- **Tool Naming**: Customize the names of proxied tools with different strategies:
    - `passthrough`: Use the original tool name.
    - `prefix`: Add a prefix to the tool name. This defaults to the server name, but can be customized with a `prefix` field.
    - `explicit`: Rename tools using a specific mapping.
- **Configuration via JSON**: All settings are managed through a simple JSON configuration file.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install dependencies**:
    This project uses Poetry for dependency management.
    ```bash
    pip install poetry
    poetry install
    ```
    Alternatively, you can install the dependencies using pip:
    ```bash
    pip install -e .
    ```

## Configuration

The MCP filter is configured via a JSON file. The path to this file can be specified using the `MCP_FILTER_CONFIG` environment variable. If the variable is not set, it defaults to `~/.mcp_filter/config.json`.

The configuration file has two main sections: `mcpServers` and `proxyConfigs`.

### `mcpServers`

This section defines the upstream MCP servers that the filter will connect to. Each server is given a name (e.g., "search", "fetch") and is defined by a command and arguments to run it.

**Example**:
```json
"mcpServers": {
    "search": {
        "command": "npx",
        "args": ["mcp-searxng-public"]
    },
    "fetch": {
        "command": "npx",
        "args": ["mcp-fetch-server"]
    }
}
```

### `proxyConfigs`

This section contains one or more named configurations for the proxy. You can define different filtering and naming rules for different use cases.

Each proxy configuration has two parts: `serverMappings` and `filtering`.

-   **`serverMappings`**: Defines how to map the tools from the upstream servers.
    -   `type`: Can be `passthrough`, `prefix`, or `explicit`.
    -   `map` (for `explicit` type): A dictionary mapping original tool names to new names.

-   **`filtering`**: An optional section to restrict which tools are exposed. If a server is not listed here, all its tools are exposed. If it is listed, only the specified tools are exposed.

**Example**:
```json
{
    "mcpServers": {
        "server1": {
            "command": "python",
            "args": ["tests/mock_server_1.py"]
        },
        "server2": {
            "command": "python",
            "args": ["tests/mock_server_2.py"]
        }
    },
    "proxyConfigs": {
        "passthrough_filtered": {
            "serverMappings": {
                "server1": { "type": "passthrough" },
                "server2": { "type": "passthrough" }
            },
            "filtering": {
                "server1": ["tool_a"],
                "server2": ["tool_d"]
            }
        },
        "prefixed": {
            "serverMappings": {
                "server1": { "type": "prefix" },
                "server2": { "type": "prefix" }
            }
        },
        "custom_prefix": {
            "serverMappings": {
                "server1": {
                    "type": "prefix",
                    "prefix": "my_prefix"
                },
                "server2": { "type": "prefix" }
            }
        }
    }
}
```

## Usage

To run the MCP filter, you need to specify which proxy configuration to use from your config file.

```bash
python -m mcp_filter.main <proxy_config_name>
```

Replace `<proxy_config_name>` with the name of one of the configurations in your `proxyConfigs` section (e.g., `passthrough_filtered`).

### Command-line arguments

-   `proxy_config_name`: (Required) The name of the proxy configuration to use.
-   `--config`: Path to the configuration file. Overrides the `MCP_FILTER_CONFIG` environment variable and the default path.
-   `--transport`: The transport to use for the filter server. Can be `stdio` (default) or `tcp`.
-   `--port`: The port to use for the `tcp` transport (default: 8080).
