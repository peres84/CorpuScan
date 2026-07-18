import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface InvestigationStatus {
  status: "pending" | "running" | "done" | "error";
  step: "parse" | "build_graph" | "investigate" | "report" | "done";
  progress: number;
  error: string | null;
}

export interface EvidenceReference {
  doc_id: string;
  location: string;
  passage: string;
  confidence: number;
}

export interface Finding {
  finding_id: string;
  finding_text: string;
  evidence: EvidenceReference[];
  fraud_likelihood: number;
}

export interface BufferRow {
  doc_id: string;
  filename: string;
  notes_summary: string;
  fraud_likelihood: number;
  primary_next_doc: string | null;
  alt_doc_leads: string[];
  open_questions: string[];
  flagged_entries: { row_ref: string; data: string; reason: string }[];
  tavily_results: { query: string; result: string }[];
  related_files: { filename: string; relationship: string; suspicion_contribution: string }[];
}

export interface InvestigationReport {
  overall_fraud_likelihood: number;
  documents_investigated: number;
  total_documents: number;
  findings: Finding[];
  buffer: BufferRow[];
}

export function useCreateInvestigation() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const createInvestigation = useCallback(async (files: File[], priorityDocIds?: string[]) => {
    setIsLoading(true);
    setError(null);
    setJobId(null);

    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    if (priorityDocIds && priorityDocIds.length > 0) {
      formData.append("priority_doc_ids", priorityDocIds.join(","));
    }

    try {
      const response = await fetch(`${API_BASE}/investigate`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to create investigation");
      }

      const data = await response.json();
      setJobId(data.job_id);
      return data.job_id as string;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { createInvestigation, isLoading, error, jobId };
}

export function useInvestigationStatus(jobId: string | null) {
  const [status, setStatus] = useState<InvestigationStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    setIsPolling(true);
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/investigations/${jobId}`);
        if (response.ok) {
          const data: InvestigationStatus = await response.json();
          setStatus(data);
          if (data.status === "done" || data.status === "error") {
            clearInterval(interval);
            setIsPolling(false);
          }
        }
      } catch {
        // Polling failure — will retry next interval
      }
    }, 2000);

    return () => {
      clearInterval(interval);
      setIsPolling(false);
    };
  }, [jobId]);

  return { status, isPolling };
}

export function useInvestigationFindings(jobId: string | null) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchFindings = useCallback(async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/investigations/${jobId}/findings`);
      if (response.ok) {
        setFindings(await response.json());
      }
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  return { findings, fetchFindings, isLoading };
}

export function useInvestigationBuffer(jobId: string | null) {
  const [buffer, setBuffer] = useState<BufferRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchBuffer = useCallback(async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/investigations/${jobId}/buffer`);
      if (response.ok) {
        setBuffer(await response.json());
      }
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  return { buffer, fetchBuffer, isLoading };
}

export function useInvestigationReport(jobId: string | null) {
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchReport = useCallback(async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/investigations/${jobId}/report`);
      if (response.ok) {
        setReport(await response.json());
      }
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  return { report, fetchReport, isLoading };
}
