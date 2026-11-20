# CSV describe() — an MCP App with a Python backend and a React (TSX) frontend

Upload a CSV inside Claude and see pandas `df.describe(include="all")`, dtypes, missing values and `df.head()` in an interactive view. Claude also gets the text output, so you can ask follow-up questions about your data.

```
 Claude (host)                                     This project
┌───────────────────────────┐   tools/call    ┌────────────────────────────────┐
│ "describe my CSV"         │ ─────────────▶  │ backend/server.py  (Python)    │
│ ┌───────────────────────┐ │  ui:// resource │   open_csv_describer           │
│ │ frontend (React, TSX) │◀┼──────────────── │   describe_csv                 │
│ │ drop CSV → describe_csv│─┼──────────────▶ │   describe_csv_file (local)    │
│ │ → render table        │ │                 │ backend/describe.py (pandas)   │
│ └───────────────────────┘ │                 └────────────────────────────────┘
└───────────────────────────┘
```

| Path | What it is |
|---|---|
| `backend/server.py` | MCP server (Python MCP SDK v2, `MCPServer` + the built-in `Apps` extension). Registers the tools and serves the UI as `ui://csv-describe/view`. |
| `backend/describe.py` | pandas logic: reads the CSV (auto-detects `,` `;` tab `\|`), converts numeric-looking text such as `"10,400"`, runs `df.describe(include="all")`, makes it JSON-safe. |
| `frontend/src/App.tsx` | React UI: drag-and-drop upload, calls `describe_csv`, renders the describe table and preview, sends the summary back to Claude. Uses `useApp` / `useHostStyles` from `@modelcontextprotocol/ext-apps/react`. |
| `frontend/vite.config.ts` | Builds the UI into one self-contained `frontend/dist/index.html` (JS and CSS inlined). |
| `tests/test_server.py` | End-to-end tests over HTTP and stdio. |
| `sample.csv` | Example dataset. |

## Tools

| Tool | Called by | Does |
|---|---|---|
| `open_csv_describer` | Claude | Opens the upload view. |
| `describe_csv` | The view after an upload, or Claude | `df.describe(include="all")` on CSV text (max 5 MB). |
| `describe_csv_file` | Claude Code / local only | Same, for a file path on the machine running the server. On with `--stdio` or `ENABLE_FILE_TOOL=1`. |

---

## Installation, step by step

### Step 1 — Install the prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.11 or newer | `python --version` (or `python3 --version`) |
| Node.js | 20.19+ or 22.12+ | `node --version` |
| Git (optional) | any | `git --version` |

Download Python from python.org and Node.js (LTS) from nodejs.org if needed.

### Step 2 — Get the project

Clone the repository and open a terminal in its folder:

```bash
git clone https://github.com/jagmohaniiit/BaseClaudeMCP.git
cd BaseClaudeMCP
```

No Git? On the GitHub page click **Code → Download ZIP**, extract it, and open a terminal in the extracted `BaseClaudeMCP-main` folder.

### Step 3 — Set up the Python backend

Create a virtual environment and install the dependencies:

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### Step 4 — Build the React frontend

```bash
cd frontend
npm install
npm run build        # type-checks the TSX, then writes frontend/dist/index.html
cd ..
```

The repository already includes a prebuilt `frontend/dist/index.html`, so you can skip this step unless you change the TSX. The server refuses to start if that file is missing, because it serves it as the UI.

### Step 5 — Test it

With the virtual environment still active:

```bash
python tests/test_server.py
```

You should see a list of `ok` lines ending in **All tests passed.**

### Step 6 — Connect it to Claude (pick one)

#### Option A — Claude Code (text results, analyzes local files)

Claude Code calls MCP tools as text and does not render app views, so use the local file tool. Use the **full path** to the virtual environment's Python so the dependencies are found:

**macOS / Linux**
```bash
claude mcp add csv-describe -- /full/path/to/BaseClaudeMCP/.venv/bin/python /full/path/to/BaseClaudeMCP/backend/server.py --stdio
```

**Windows**
```powershell
claude mcp add csv-describe -- C:\full\path\to\BaseClaudeMCP\.venv\Scripts\python.exe C:\full\path\to\BaseClaudeMCP\backend\server.py --stdio
```

Then ask: *"Use csv-describe to describe ./data/sales.csv."*

#### Option B — Claude Desktop on your computer (with the upload view)

Open Claude Desktop → **Settings → Developer → Edit Config**, add the server, save, and restart Claude Desktop:

```json
{
  "mcpServers": {
    "csv-describe": {
      "command": "/full/path/to/BaseClaudeMCP/.venv/bin/python",
      "args": ["/full/path/to/BaseClaudeMCP/backend/server.py", "--stdio"]
    }
  }
}
```

On Windows use `.venv\\Scripts\\python.exe` and double backslashes in the paths.

Ask: *"Open the CSV describer"*, then drop a CSV into the view.

#### Option C — Claude on the web, desktop or mobile (custom connector, with the upload view)

Claude reaches custom connectors from Anthropic's cloud, so the server needs a **public HTTPS URL**; `localhost` won't work. While testing, a free Cloudflare quick tunnel gives you one. You need **two terminal windows**, and both must stay open while you use the connector.

**C1. Install `cloudflared`** (once). Windows: `winget install --id Cloudflare.cloudflared`. macOS: `brew install cloudflared`. Check with `cloudflared --version`.

**C2. Terminal 1 — start the tunnel**

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints an address like `https://<random-words>.trycloudflare.com`. Copy the host name (the part after `https://`).

**C3. Terminal 2 — start the server, allowing the tunnel's host name**

The server rejects requests for host names it doesn't know (`421 Invalid Host header`), so set `ALLOWED_HOSTS` **in the same window** that starts the server. Use the host name only: no `https://`, no `/mcp`.

| Shell | Commands (from the project folder) |
|---|---|
| PowerShell | `.venv\Scripts\Activate.ps1`<br>`$env:ALLOWED_HOSTS = "<random-words>.trycloudflare.com"`<br>`python backend\server.py` |
| Command Prompt (cmd) | `.venv\Scripts\activate.bat`<br>`set ALLOWED_HOSTS=<random-words>.trycloudflare.com`<br>`python backend\server.py` |
| Git Bash / macOS / Linux | `source .venv/Scripts/activate` (Git Bash) or `source .venv/bin/activate`<br>`ALLOWED_HOSTS=<random-words>.trycloudflare.com python backend/server.py` |

Only the server needs to run. The frontend is **not** a separate server: `backend/server.py` serves the built `frontend/dist/index.html` to Claude, so you don't need `npm run dev`.

**C4. Check the public URL before adding it to Claude**

- Open `https://<random-words>.trycloudflare.com/mcp` in a browser. **`Method Not Allowed` (405) is the expected answer**: the endpoint only accepts POST.
- To check the full path, including the host-name check, send a real MCP request:
  ```bash
  curl -X POST https://<random-words>.trycloudflare.com/mcp \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
  ```
  A JSON list of tools means it's working. `Invalid Host header` means `ALLOWED_HOSTS` is wrong (go back to C3).

**C5. Add the connector in Claude**

1. Open **Settings → Connectors → Add custom connector**. On Team or Enterprise plans an Owner may need to add it in **Admin settings → Connectors** first.
2. Name: `CSV Describe`. URL: **`https://<random-words>.trycloudflare.com/mcp`**. The **`/mcp` at the end is required**; without it, adding fails.
3. Click **Add**, then **Connect**.

**C6. Use it**

1. Start a **new chat**, open the tools (**+**) menu, and turn on **CSV Describe**.
2. Ask: *"Open the CSV describer"*. The view may open **in a side pane** next to the chat.
3. Drop a CSV into the box, or click **choose a file**. The `df.describe()` table appears, and Claude can answer follow-up questions about it.

**Important: quick-tunnel addresses change.** Each time you restart `cloudflared` you get a new random address. Then you must (1) restart the server with the new `ALLOWED_HOSTS` and (2) remove the connector in Claude and add it again with the new URL. The old URL returns `530`. For a permanent address, use a [named Cloudflare tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) or deploy the server.

**For real use**, deploy to any Python host (Render, Fly.io, Railway, a VM, Cloud Run) with the UI built, then add `https://<your-host>/mcp` as the connector URL:

```bash
HOST=0.0.0.0 PORT=8080 ALLOWED_HOSTS=describe.example.com python backend/server.py
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `UI not built: …/frontend/dist/index.html is missing` | Run Step 4. |
| `ModuleNotFoundError: No module named 'mcp'` or `pandas` | Activate the virtual environment (Step 3), or use the venv's Python path in Claude's config. |
| `No module named 'mcp.server.fastmcp'` in other code | You're on MCP Python SDK v2; `FastMCP` is now `MCPServer` (`from mcp.server.mcpserver import MCPServer`). This project already uses v2. |
| `421 Misdirected Request` / `Invalid Host header` through a tunnel | Set `ALLOWED_HOSTS` to the tunnel or domain name (host only) **in the window that starts the server**, then restart it. |
| Browser shows `Method Not Allowed` at `/mcp` | Expected: the endpoint only accepts POST. The server and tunnel are working. |
| `502 Bad Gateway` from Cloudflare | The tunnel is up but nothing answers on port 8000. Start `python backend/server.py`. |
| `530` from Cloudflare / adding the connector fails | The tunnel address no longer exists, usually because `cloudflared` was restarted. Use the new address: update `ALLOWED_HOSTS`, restart the server, re-add the connector. |
| Adding the connector fails with a working tunnel | Check the URL ends in **`/mcp`**. |
| `ERR ... stream canceled by remote` in the `cloudflared` window | Usually harmless: Claude closed a request early. Only a concern if every upload fails. |
| The view shows briefly or not at all, or old behaviour persists after a frontend change | The server reads `frontend/dist/index.html` only at startup. Run `npm run build` in `frontend/`, **restart the server**, then start a new chat. |
| Upload box shows "Could not connect to Claude" | The view loaded but the host handshake failed. Reload the page (Ctrl+Shift+R), start a new chat, and try a window without ad-block extensions. |
| `.venv\Scripts\Activate.ps1` cannot be loaded (scripts disabled) | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use cmd and `activate.bat`. |
| `bash: ForEach-Object: command not found` or `export` not recognized | You mixed shells: `ForEach-Object` and `$env:` are PowerShell; `export` and `xargs` are Git Bash. Use the commands for the shell you're in. |
| Upload says the file is too large | The limit is 5 MB; change `MAX_BYTES` in `backend/describe.py` and `frontend/src/App.tsx`. |
| A number column shows no mean | It contains text that isn't numeric in more than 5% of rows; check the column with `describe_csv` output's `top` value. |

## Before sharing with others

- **Add authentication.** Anyone who can reach the URL can call the tools. Claude supports OAuth for custom connectors.
- **Keep `describe_csv_file` off on public servers** (it's off over HTTP by default): it reads files from the server's disk.
- Uploaded data is processed in memory and not stored.

## Developing

- Change the statistics in `backend/describe.py`; change the view in `frontend/src/App.tsx`, then `npm run build` and restart the server.
- `npm run typecheck` in `frontend/` checks the TSX without building.
