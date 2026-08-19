import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const PAGE_SIZE = 50;

export interface KeyValueEntry {
  field: string;
  value: string;
  context: string;
}

export interface StructuredFileData {
  file_id: string;
  filename: string;
  extraction_method: string;
  columns: string[] | null;
  original_columns: string[] | null;
  normalized_columns: string[] | null;
  rows: Record<string, string>[] | null;
  key_values: KeyValueEntry[] | null;
  row_count: number;
  offset: number | null;
  limit: number | null;
}

interface RawFileData {
  file_id: string;
  filename: string;
  content: string;
}

export function useFileData(jobId: string, fileId: string) {
  const [structured, setStructured] = useState<StructuredFileData | null>(null);
  const [raw, setRaw] = useState<RawFileData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStructured = useCallback(async (offset = 0) => {
    const response = await fetch(
      `${API_BASE}/investigations/${jobId}/files/${fileId}/structured?offset=${offset}&limit=${PAGE_SIZE}`,
    );
    if (!response.ok) {
      throw new Error("Unable to load structured file data.");
    }
    const data: StructuredFileData = await response.json();
    setStructured(data);
  }, [fileId, jobId]);

  const fetchPage = useCallback(async (offset: number) => {
    setIsLoading(true);
    setError(null);
    try {
      await fetchStructured(offset);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load file data.");
    } finally {
      setIsLoading(false);
    }
  }, [fetchStructured]);

  useEffect(() => {
    let active = true;

    async function loadFileData() {
      setIsLoading(true);
      setError(null);
      try {
        const rawResponse = await fetch(`${API_BASE}/investigations/${jobId}/files/${fileId}/raw`);
        if (!rawResponse.ok) {
          throw new Error("Unable to load raw file data.");
        }
        const rawData: RawFileData = await rawResponse.json();
        const structuredResponse = await fetch(
          `${API_BASE}/investigations/${jobId}/files/${fileId}/structured?offset=0&limit=${PAGE_SIZE}`,
        );
        if (!structuredResponse.ok) {
          throw new Error("Unable to load structured file data.");
        }
        const structuredData: StructuredFileData = await structuredResponse.json();
        if (active) {
          setRaw(rawData);
          setStructured(structuredData);
        }
      } catch (requestError) {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load file data.");
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    loadFileData();
    return () => {
      active = false;
    };
  }, [fileId, jobId]);

  return { structured, raw, isLoading, error, fetchPage };
}
