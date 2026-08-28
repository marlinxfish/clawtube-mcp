import pytest
from fastmcp import Client

import server


@pytest.mark.asyncio
async def test_skill_resource_readable():
    async with Client(server.mcp) as client:
        resources = await client.list_resources()
        assert len(resources) > 0

        skill_resources = [
            r for r in resources if str(r.uri).startswith("skill://clawtube")
        ]
        assert len(skill_resources) > 0

        # Read main SKILL.md resource
        main_skill = next(
            (r for r in skill_resources if str(r.uri).endswith("SKILL.md")),
            skill_resources[0],
        )
        content_items = await client.read_resource(main_skill.uri)
        assert len(content_items) > 0
        content_text = content_items[0].text.lower()
        assert "clawtube" in content_text
