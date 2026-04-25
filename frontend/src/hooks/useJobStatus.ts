import { useEffect, useRef, useState } from "react";
import { getJob, getVideoUrl, type BackendStep, type JobStatus } from "@/lib/api";

interface UseJobStatusResult {
  status: JobStatus | null;
  step: BackendStep | null;
  progress: number;
  error: string | null;
  videoUrl: string | null;
}

const POLL_MS = 1500;

export function useJobStatus(jobId: string | undefined): UseJobStatusResult {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [step, setStep] = useState<BackendStep | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const cancelled = useRef<boolean>(false);

  useEffect(() => {
    if (!jobId) return;
    cancelled.current = false;
    let timer: number | undefined;

    const tick = async (): Promise<void> => {
      try {
        const job = await getJob(jobId);
        if (cancelled.current) return;
        setStatus(job.status);
        setStep(job.step);
        setProgress(Math.max(0, Math.min(100, job.progress)));
        if (job.error) setError(job.error);
        if (job.status === "done") {
          setVideoUrl(job.video_url ?? getVideoUrl(jobId));
          return;
        }
        if (job.status === "error") return;
        timer = window.setTimeout(tick, POLL_MS);
      } catch (err) {
        if (cancelled.current) return;
        setError(err instanceof Error ? err.message : "Failed to fetch job");
        timer = window.setTimeout(tick, POLL_MS);
      }
    };

    void tick();

    return () => {
      cancelled.current = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [jobId]);

  return { status, step, progress, error, videoUrl };
}
