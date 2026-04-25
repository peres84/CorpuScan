export type JobStatus = "pending" | "running" | "done" | "error";

export type BackendStep =
  | "ingest"
  | "finance"
  | "scripter"
  | "tts"
  | "hera_plan"
  | "hera_render"
  | "compose"
  | "done";

export interface JobState {
  status: JobStatus;
  step: BackendStep;
  progress: number;
  error?: string;
  video_url?: string;
}

export interface GenerateInput {
  file?: File;
  url?: string;
  query?: string;
}

const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export function getApiBaseUrl(): string {
  return BASE_URL;
}

export async function postGenerate(input: GenerateInput): Promise<{ job_id: string }> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.url) form.append("url", input.url);
  if (input.query) form.append("query", input.query);

  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Request failed (${res.status})`);
  }

  return (await res.json()) as { job_id: string };
}

export async function getJob(jobId: string): Promise<JobState> {
  const res = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job (${res.status})`);
  }
  return (await res.json()) as JobState;
}

export function getVideoUrl(jobId: string): string {
  return `${BASE_URL}/jobs/${encodeURIComponent(jobId)}/video`;
}
