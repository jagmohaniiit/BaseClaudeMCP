"""server.py — MCP server (Python, MCP SDK v2) with an MCP App UI.

Run:
    python backend/server.py              # Streamable HTTP on http://127.0.0.1:8000/mcp
    python backend/server.py --stdio      # stdio, for Claude Code / Claude Desktop config (enables describe_csv_file)

Env: HOST, PORT, ALLOWED_HOSTS (comma list, e.g. your tunnel or domain), ENABLE_FILE_TOOL=1, UI_HTML (path to built UI).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.apps import Apps
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

from describe import MAX_BYTES, describe_frame, describe_text, load_csv

ROOT = Path(__file__).resolve().parent.parent
UI_URI = "ui://csv-describe/view"
UI_PATH = Path(os.environ.get("UI_HTML", ROOT / "frontend" / "dist" / "index.html"))
USE_STDIO = "--stdio" in sys.argv
FILE_TOOL = USE_STDIO or os.environ.get("ENABLE_FILE_TOOL") == "1"

if not UI_PATH.exists():
    sys.exit(f"UI not built: {UI_PATH} is missing. Run `npm install && npm run build` in frontend/ first.")


def _result(text: str, name: str) -> CallToolResult:
    """Describe CSV text; return text for Claude and structured data for the UI."""
    try:
        df = load_csv(text)
    except Exception as exc:  # noqa: BLE001 — surface parse errors to the user
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {exc}")], is_error=True)
    return CallToolResult(
        content=[TextContent(type="text", text=describe_text(df, name))],
        structured_content=describe_frame(df, name),
    )


apps = Apps()


@apps.tool(
    resource_uri=UI_URI,
    name="open_csv_describer",
    title="Open CSV describer",
    description="Show an upload box where the user can drop a CSV file and see pandas df.describe() statistics. "
    "Use when the user wants to upload or summarize a dataset.",
)
def open_csv_describer() -> str:
    return "The CSV describer is open. Ask the user to drop a CSV file into it."


@apps.tool(
    resource_uri=UI_URI,
    visibility=["model", "app"],  # callable by Claude and by the UI after an upload
    name="describe_csv",
    title="Describe CSV",
    description="Run pandas df.describe(include='all') on CSV text: count, mean, std, min, quartiles, max for numeric "
    "columns; count, unique, top, freq for text columns; plus dtypes and missing values. Max 5 MB.",
)
def describe_csv(csv_text: str, name: str = "dataset.csv") -> CallToolResult:
    return _result(csv_text, name)


if FILE_TOOL:

    @apps.tool(
        resource_uri=UI_URI,
        name="describe_csv_file",
        title="Describe a local CSV file",
        description="Run df.describe() on a CSV file on this machine, given its path. Max 5 MB.",
    )
    def describe_csv_file(file_path: str) -> CallToolResult:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            return CallToolResult(content=[TextContent(type="text", text=f"Error: {path} not found.")], is_error=True)
        if path.stat().st_size > MAX_BYTES:
            return CallToolResult(content=[TextContent(type="text", text="Error: file is larger than 5 MB.")], is_error=True)
        return _result(path.read_text(encoding="utf-8", errors="replace"), path.name)


# The built React UI is a single self-contained HTML file (JS and CSS inlined), so no CSP domains are needed.
apps.add_html_resource(UI_URI, UI_PATH.read_text(encoding="utf-8"), name="CSV describe view",
                       description="Upload a CSV and view df.describe()")

mcp = MCPServer("csv-describe", version="1.0.0", extensions=[apps])

if __name__ == "__main__":
    if USE_STDIO:
        mcp.run("stdio")
    else:
        host = os.environ.get("HOST", "127.0.0.1")
        allowed = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed + ["127.0.0.1:*", "localhost:*"],
            allowed_origins=[f"https://{h}" for h in allowed] + ["http://127.0.0.1:*", "http://localhost:*",
                                                                   "https://claude.ai", "https://claude.com"],
        )
        app = mcp.streamable_http_app(
            stateless_http=True,
            json_response=True,  # plain JSON replies: no long-lived streams through the tunnel
            max_request_body_size=12 * 1024 * 1024,  # CSV text travels inside JSON-RPC
            transport_security=security,
            host=host,
        )

        async def no_get_stream(scope, receive, send):
            # A stateless server has nothing to push, so refuse the optional GET /mcp
            # event stream (allowed by the MCP spec) instead of holding it open forever.
            if scope["type"] == "http" and scope["method"] == "GET" and scope["path"].rstrip("/") == "/mcp":
                await send({"type": "http.response.start", "status": 405,
                            "headers": [(b"allow", b"POST"), (b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": b"Method Not Allowed"})
                return
            await app(scope, receive, send)

        import uvicorn
        uvicorn.run(no_get_stream, host=host, port=int(os.environ.get("PORT", "8000")))