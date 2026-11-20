import { useCallback, useRef, useState } from "react";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import type { DescribeResult, Scalar } from "./types";

const MAX_BYTES = 5 * 1024 * 1024;

const fmt = (v: Scalar): string => {
  if (v === null || v === undefined) return "–";
  if (typeof v !== "number") return String(v);
  const a = Math.abs(v);
  if (a >= 1e6) return v.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 2 });
  if (a !== 0 && a < 1e-3) return v.toExponential(2);
  return v.toLocaleString(undefined, { maximumFractionDigits: a >= 100 ? 2 : 4 });
};

const isDescribeResult = (v: unknown): v is DescribeResult => {
  const r = v as Partial<DescribeResult> | null | undefined;
  return !!r && typeof r === "object" && !!r.shape && Array.isArray(r.columns) &&
    Array.isArray(r.statistics) && !!r.preview && Array.isArray(r.preview.rows);
};

export default function App() {
  const [result, setResult] = useState<DescribeResult | null>(null);
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const show = useCallback((r: CallToolResult) => {
    if (r.isError || !isDescribeResult(r.structuredContent)) {
      const msg = r.content?.find((c) => c.type === "text");
      setStatus({ text: msg && "text" in msg ? msg.text : "Something went wrong.", error: true });
      return;
    }
    setStatus(null);
    setResult(r.structuredContent as unknown as DescribeResult);
  }, []);

  // Connects to the host (Claude). When Claude itself calls a tool linked to this view, the result arrives here.
  const { app, error } = useApp({
    appInfo: { name: "CSV describe view", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (a) => {
      // Only describe results carry statistics. Other tools linked to this view (e.g. open_csv_describer,
      // whose structuredContent is {"result": "..."}) must be ignored, or rendering them would crash the view.
      a.ontoolresult = (r) => { if (isDescribeResult(r.structuredContent)) show(r); };
    },
  });
  useHostStyles(app, app?.getHostContext()); // match Claude's light/dark theme and fonts

  const handleFile = async (file?: File) => {
    if (!file) return;
    if (!app) {
      setStatus({ text: "Not connected to Claude yet, so the file can't be analyzed. Try reopening the describer.", error: true });
      return;
    }
    if (file.size > MAX_BYTES) {
      setStatus({ text: `"${file.name}" is ${(file.size / 1048576).toFixed(1)} MB; the limit is 5 MB.`, error: true });
      return;
    }
    setStatus({ text: `Running df.describe() on ${file.name}…` });
    try {
      const text = await file.text();
      const r = await app.callServerTool({ name: "describe_csv", arguments: { csv_text: text, name: file.name } });
      show(r);
      const summary = r.content?.find((c) => c.type === "text");
      if (!r.isError && summary && "text" in summary) {
        // Let Claude see the results on the user's next message, so they can ask follow-up questions.
        await app.updateModelContext({
          content: [{ type: "text", text: `The user uploaded a CSV in the describe app:\n${summary.text}` }],
        });
      }
    } catch (e) {
      setStatus({ text: `Could not analyze the file: ${e instanceof Error ? e.message : String(e)}`, error: true });
    }
  };

  // Keep the drop box visible even if the host handshake fails, and show the connection state below it.
  const connection = error
    ? { text: `Could not connect to Claude: ${error.message}`, error: true }
    : !app
      ? { text: "Connecting to Claude…" }
      : null;

  return (
    <main>
      <div
        className={`drop ${dragging ? "over" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
      >
        <strong>Drop a CSV file here</strong> or <button type="button">choose a file</button>
        <div className="muted">Up to 5 MB · comma, semicolon, tab or pipe separated</div>
        <input ref={inputRef} type="file" accept=".csv,.tsv,.txt,text/csv" hidden
               onChange={(e) => handleFile(e.target.files?.[0])} />
      </div>

      {connection && !status && <div className={`status ${connection.error ? "error" : ""}`}>{connection.text}</div>}
      {status && <div className={`status ${status.error ? "error" : ""}`}>{status.text}</div>}

      {result && (
        <>
          <h2>{result.name}</h2>
          <div className="cards">
            <div className="card"><span>Rows</span><b>{fmt(result.shape.rows)}</b></div>
            <div className="card"><span>Columns</span><b>{fmt(result.shape.columns)}</b></div>
            <div className="card"><span>Missing cells</span><b>{fmt(result.columns.reduce((s, c) => s + c.missing, 0))}</b></div>
          </div>

          <h3>df.describe(include="all")</h3>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th />
                  {result.columns.map((c) => (
                    <th key={c.name}>{c.name}<div className="dtype">{c.dtype}</div></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.statistics.map((s) => (
                  <tr key={s}>
                    <th>{s}</th>
                    {result.columns.map((c) => <td key={c.name}>{fmt(c.values[s] ?? null)}</td>)}
                  </tr>
                ))}
                <tr className="missing">
                  <th>missing</th>
                  {result.columns.map((c) => <td key={c.name}>{fmt(c.missing)}</td>)}
                </tr>
              </tbody>
            </table>
          </div>

          <h3>df.head()</h3>
          <div className="scroll">
            <table>
              <thead><tr>{result.preview.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {result.preview.rows.map((row, i) => (
                  <tr key={i}>{row.map((v, j) => <td key={j}>{fmt(v)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
