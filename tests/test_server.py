"""End-to-end tests: over Streamable HTTP (how Claude connects) and stdio (how Claude Code connects).

Run from the project root:  python tests/test_server.py
"""

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
SERVER = str(ROOT / "backend" / "server.py")
PORT = 8917


def ok(cond: bool, msg: str) -> None:
    if not cond:
        sys.exit(f"FAIL: {msg}")
    print("ok  ", msg)


async def http_tests() -> None:
    async with Client(f"http://127.0.0.1:{PORT}/mcp") as c:
        tools = (await c.list_tools()).tools
        names = sorted(t.name for t in tools)
        ok(names == ["describe_csv", "open_csv_describer"], f"HTTP lists {names} (file tool hidden)")
        ok(all(t.meta and t.meta["ui"]["resourceUri"] == "ui://csv-describe/view" for t in tools), "tools link to the UI")

        res = (await c.read_resource("ui://csv-describe/view")).contents[0]
        ok(res.mime_type == "text/html;profile=mcp-app" and len(res.text) > 10_000, "UI served as an MCP App (single-file React build)")

        csv = (ROOT / "sample.csv").read_text()
        r = await c.call_tool("describe_csv", {"csv_text": csv, "name": "sample.csv"})
        s = r.structured_content
        ok(not r.is_error and s["shape"] == {"rows": 241, "columns": 7}, "describe_csv: 241 rows x 7 columns")
        ok({"count", "mean", "std", "min", "25%", "50%", "75%", "max", "unique", "top", "freq"} <= set(s["statistics"]),
           "statistics match df.describe(include='all')")
        rev = next(col for col in s["columns"] if col["name"] == "revenue")
        ok(rev["missing"] > 0 and isinstance(rev["values"]["mean"], float), f"revenue: mean {rev['values']['mean']}, {rev['missing']} missing")
        region = next(col for col in s["columns"] if col["name"] == "region")
        ok(region["values"]["unique"] == 5 and region["values"]["mean"] is None, "region is categorical (unique/top/freq; NaN -> null)")
        print("\n" + r.content[0].text[:600] + "\n...\n")

        bad = await c.call_tool("describe_csv", {"csv_text": "a,b\n"})
        ok(bad.is_error, "header-only CSV rejected with an error")
        big = await c.call_tool("describe_csv", {"csv_text": "a,b\n" + "1,2\n" * 1_400_000})
        ok(big.is_error and "5 MB" in big.content[0].text, "over-size upload rejected (5 MB limit)")


async def stdio_tests() -> None:
    params = StdioServerParameters(command=sys.executable, args=[SERVER, "--stdio"], cwd=str(ROOT))
    async with Client(params) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        ok("describe_csv_file" in names, "stdio exposes describe_csv_file")
        r = await c.call_tool("describe_csv_file", {"file_path": str(ROOT / "sample.csv")})
        ok(r.structured_content["shape"]["rows"] == 241, "describe_csv_file reads a local file")


def wait_for_server(proc: subprocess.Popen, log_path: Path, timeout: float = 60) -> None:
    """Wait until the HTTP server accepts connections; show its log if it exits or times out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            sys.exit(f"FAIL: server exited during startup (code {proc.returncode}). Server output:\n{log_path.read_text(errors='replace')}")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    sys.exit(f"FAIL: server did not start within {timeout:.0f}s. Server output:\n{log_path.read_text(errors='replace')}")


if __name__ == "__main__":
    print(f"Python {sys.version.split()[0]} at {sys.executable}")
    env = {**os.environ, "PORT": str(PORT), "PYTHONIOENCODING": "utf-8"}
    log_path = Path(tempfile.gettempdir()) / "csv_describe_test_server.log"
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, SERVER], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_for_server(proc, log_path)
            asyncio.run(http_tests())
        finally:
            proc.terminate()
            proc.wait(timeout=10)
    asyncio.run(stdio_tests())
    print("\nAll tests passed.")