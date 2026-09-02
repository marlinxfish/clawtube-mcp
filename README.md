# clawtube-mcp

MCP Gateway for **ClawTube Protocol** (FastMCP v3.4.7) — 8 typed tools for AI Agents (Claude Desktop, Cursor, autonomous agents).

## Stack
- **FastMCP v3.4.7** (Python ≥3.12, managed with `uv`)
- Async HTTPX client connecting to `clawtube-backend`
- Operational Agent Skill: auto-generated via **Skills Provider** (`clawtube-skills` repo)

## Running
```bash
uv run fastmcp run server.py                      # stdio (local)
uv run fastmcp run server.py --transport sse --port 8081  # remote/cloud
uv run --group dev pytest -v                      # test suite
```

## 8 Tools
`resolve_creator` · `estimate_tip_usd` · `create_tip_tx` · `verify_tip_status` · `get_creator_escrow_balance` · `verify_creator_claim` · `refund_expired_tip` · `sweep_expired_escrow`

## Client Configuration
```json
{
  "mcpServers": {
    "clawtube-local": {
      "command": "uv",
      "args": ["--directory", "/path/to/clawtube-mcp", "run", "fastmcp", "run", "server.py"]
    }
  }
}
```
