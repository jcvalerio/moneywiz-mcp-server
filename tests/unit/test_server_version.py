"""The MCP handshake must report this package's version, not the mcp SDK's."""

from functools import partial
import importlib.metadata

import anyio
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
import pytest

import moneywiz_mcp_server
from moneywiz_mcp_server.main import mcp


async def _handshake_server_info() -> tuple[str, str]:
    server = mcp._mcp_server
    streams = create_client_server_memory_streams()
    async with streams as (client, srv), anyio.create_task_group() as tg:
        # start_soon only forwards positional arguments, so bind keywords here
        tg.start_soon(
            partial(
                server.run,
                srv[0],
                srv[1],
                server.create_initialization_options(),
                raise_exceptions=True,
            )
        )
        async with ClientSession(client[0], client[1]) as session:
            result = await session.initialize()
        tg.cancel_scope.cancel()
    return result.serverInfo.name, result.serverInfo.version


@pytest.mark.unit
async def test_initialize_reports_package_version():
    name, version = await _handshake_server_info()

    assert name == "moneywiz-mcp-server"
    assert version == moneywiz_mcp_server.__version__
    assert version == importlib.metadata.version("moneywiz-mcp-server")
    assert version != importlib.metadata.version("mcp")
