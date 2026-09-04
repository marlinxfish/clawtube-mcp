"""Server tests for ClawTube MCP Gateway."""

import pytest
from fastmcp import Client

import server


@pytest.mark.asyncio
async def test_server_lists_7_tools():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        assert len(tools) == 7
        names = {t.name for t in tools}
        expected_names = {
            "resolve_creator",
            "estimate_tip_usd",
            "create_tip_tx",
            "verify_tip_status",
            "get_creator_escrow_balance",
            "verify_creator_claim",
            "refund_expired_tip",
        }
        assert names == expected_names
