import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import FileViewer from "./FileViewer";

const structuredResponse = {
  file_id: "file-1",
  filename: "ledger.csv",
  extraction_method: "deterministic",
  columns: ["BETRAG"],
  original_columns: ["BETRAG"],
  normalized_columns: ["amount"],
  rows: [{ BETRAG: "50000,00", amount: "50000,00" }],
  key_values: null,
  row_count: 1,
  offset: 0,
  limit: 50,
};

describe("FileViewer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("switches between raw and table views", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      const payload = url.includes("/raw")
        ? { file_id: "file-1", filename: "ledger.csv", content: "Raw ledger content" }
        : structuredResponse;
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }));
    }));

    render(<FileViewer jobId="job-1" fileId="file-1" />);

    expect(await screen.findByText("Raw ledger content")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Table" }));

    await waitFor(() => {
      expect(screen.getByText("50000,00")).toBeInTheDocument();
    });
    expect(screen.queryByText("Raw ledger content")).not.toBeInTheDocument();
  });
});
