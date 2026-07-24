import { useState } from "react";

import { useFileData } from "@/hooks/useFileData";

interface FileViewerProps {
  jobId: string;
  fileId: string;
}

const FileViewer = ({ jobId, fileId }: FileViewerProps) => {
  const [view, setView] = useState<"raw" | "table">("raw");
  const { structured, raw, isLoading, error, fetchPage } = useFileData(jobId, fileId);

  if (isLoading && !structured && !raw) {
    return <p className="text-xs text-muted-foreground">Loading file data...</p>;
  }

  if (error) {
    return <p role="alert" className="text-xs text-destructive">{error}</p>;
  }

  const offset = structured?.offset ?? 0;
  const pageSize = structured?.limit ?? 50;
  const hasPreviousPage = offset > 0;
  const hasNextPage = structured?.rows !== null && structured !== null
    ? offset + (structured.rows?.length ?? 0) < structured.row_count
    : false;

  return (
    <section className="space-y-3 rounded-md border bg-background p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-foreground">File data</p>
        <div className="flex rounded-md border p-0.5" aria-label="File data view">
          <button
            type="button"
            onClick={() => setView("raw")}
            className={`rounded px-2 py-1 text-xs ${view === "raw" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            Raw
          </button>
          <button
            type="button"
            onClick={() => setView("table")}
            className={`rounded px-2 py-1 text-xs ${view === "table" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            Table
          </button>
        </div>
      </div>

      {view === "raw" ? (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-muted/50 p-3 font-mono text-xs text-muted-foreground">
          {raw?.content || "No raw content available."}
        </pre>
      ) : structured?.rows ? (
        <div className="space-y-3">
          <div className="max-h-80 overflow-auto rounded border">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-muted">
                <tr>
                  {(structured.columns || structured.original_columns || []).map((column) => (
                    <th key={column} className="whitespace-nowrap px-3 py-2 font-medium text-muted-foreground">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {structured.rows.map((row, rowIndex) => (
                  <tr key={offset + rowIndex} className="border-t">
                    {(structured.columns || structured.original_columns || []).map((column) => (
                      <td key={column} className="whitespace-nowrap px-3 py-2 text-muted-foreground">
                        {row[column] || "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{structured.row_count} rows</span>
            <div className="flex gap-2">
              <button type="button" disabled={!hasPreviousPage || isLoading} onClick={() => fetchPage(Math.max(0, offset - pageSize))} className="rounded border px-2 py-1 disabled:opacity-50">
                Previous
              </button>
              <button type="button" disabled={!hasNextPage || isLoading} onClick={() => fetchPage(offset + pageSize)} className="rounded border px-2 py-1 disabled:opacity-50">
                Next
              </button>
            </div>
          </div>
        </div>
      ) : structured?.key_values ? (
        <dl className="space-y-2">
          {structured.key_values.map((entry) => (
            <div key={`${entry.field}-${entry.value}`} className="rounded border p-2 text-xs">
              <dt className="font-medium text-foreground">{entry.field}</dt>
              <dd className="mt-1 text-muted-foreground">{entry.value}</dd>
              <dd className="mt-1 text-muted-foreground">{entry.context}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-xs text-muted-foreground">No structured data available.</p>
      )}
    </section>
  );
};

export default FileViewer;
