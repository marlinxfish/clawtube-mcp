# clawtube-mcp

Gateway MCP **ClawTube Protocol** (FastMCP v3.4.7) — 8 typed tools untuk AI Agent (Claude Desktop, Cursor, autonomous agents).

## Stack
- **FastMCP v3.4.7** (Python ≥3.12, dikelola `uv`)
- Client async HTTPX ke `clawtube-backend`
- Skill operasional agen: auto-generate via **Skills Provider** (repo `clawtube-skills`)

## Menjalankan
```bash
uv run fastmcp run server.py                      # stdio (lokal)
uv run fastmcp run server.py --transport sse --port 8081  # remote/cloud
uv run --group dev pytest -v                      # test suite
```

## 8 Tools
`resolve_creator` · `estimate_tip_usd` · `create_tip_tx` · `verify_tip_status` · `get_creator_escrow_balance` · `verify_creator_claim` · `refund_expired_tip` · `sweep_expired_escrow`

## Konfigurasi Client
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
