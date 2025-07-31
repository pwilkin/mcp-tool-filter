import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from mcp_filter.main import load_config

TEST_CONFIG_PATH = Path(__file__).parent / "test_config.json"
PORT = 8899

@pytest.fixture
def test_config():
    return json.loads(TEST_CONFIG_PATH.read_text())

def test_load_config():
    config = load_config(str(TEST_CONFIG_PATH))
    assert "mcpServers" in config
    assert "proxyConfigs" in config

def test_load_config_env_var(monkeypatch):
    monkeypatch.setenv("MCP_FILTER_CONFIG", str(TEST_CONFIG_PATH))
    config = load_config(None)
    assert "mcpServers" in config

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def get_proxy_client():
    """A fixture to run the MCPProxy server and yield a client factory."""
    procs = []

    async def _runner(config_name: str):
        cmd = [
            "python",
            "mcp_filter/main.py",
            config_name,
            "--config", str(TEST_CONFIG_PATH),
            "--transport", "tcp",
            "--port", str(PORT)
        ]
        # Use CREATE_NEW_PROCESS_GROUP on Windows to ensure child processes are killed
        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        procs.append(proc)
        await asyncio.sleep(2)  # Give server time to start

        transport = StreamableHttpTransport(url=f"http://localhost:{PORT}")
        client = Client(transport)
        return client

    yield _runner

    for proc in procs:
        proc.terminate()
        proc.wait()


@pytest.mark.asyncio
async def test_passthrough_filtered(get_proxy_client):
    client = await get_proxy_client("passthrough_filtered")
    async with client:
        tools = await client.get_tools()
        tool_names = {t.name for t in tools}

        assert tool_names == {"tool_a", "tool_d"}

        result_a = await client.call_tool("tool_a", x=10)
        assert result_a == 20

        result_d = await client.call_tool("tool_d")
        assert result_d == "tool_d from server 2"

@pytest.mark.asyncio
async def test_prefixed(get_proxy_client):
    client = await get_proxy_client("prefixed")
    async with client:
        tools = await client.get_tools()
        tool_names = {t.name for t in tools}

        assert tool_names == {"server1_tool_a", "server1_tool_b", "server2_tool_c", "server2_tool_d"}

        result = await client.call_tool("server1_tool_a", x=5)
        assert result == 10

@pytest.mark.asyncio
async def test_explicit_rename(get_proxy_client):
    client = await get_proxy_client("explicit_rename")
    async with client:
        tools = await client.get_tools()
        tool_names = {t.name for t in tools}

        assert "renamed_tool_a" in tool_names
        assert "tool_a" not in tool_names

        result = await client.call_tool("renamed_tool_a", x=3)
        assert result == 6

@pytest.mark.asyncio
async def test_mixed_config(get_proxy_client):
    client = await get_proxy_client("mixed")
    async with client:
        tools = await client.get_tools()
        tool_names = {t.name for t in tools}

        # server1: tool_b (prefixed), server2: all (passthrough)
        assert tool_names == {"server1_tool_b", "tool_c", "tool_d"}

        result_b = await client.call_tool("server1_tool_b", y="world")
        assert result_b == "Hello, world"

        result_c = await client.call_tool("tool_c", z=True)
        assert result_c is False
