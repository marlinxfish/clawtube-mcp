"""Unit test suite ClawTube MCP (stub — implementasi menyusul via implementation plan)."""

import pytest


@pytest.mark.asyncio
async def test_server_lists_8_tools():
    from fastmcp import Client

    async with Client("clawtube-mcp/server.py") as client:
        tools = await client.list_tools()
        assert len(tools) == 8
        names = {t.name for t in tools}
        assert "resolve_creator" in names
        assert "create_tip_tx" in names
