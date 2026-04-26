import { useEffect, useRef, useState } from "react";
import { getJob, getVideoUrl, type BackendStep, type JobStatus } from "@/lib/api";

interface UseJobStatusResult {
  status: JobStatus | null;
  step: BackendStep | null;
  progress: number;
  error: string | null;
  videoUrl: string | null;
  heraCompletedClips: number;
  heraTotalClips: number;
  heraAttempt: number;
  heraMaxAttempts: number;
}

const POLL_MS = 1500;

export function useJobStatus(jobId: string | undefined): UseJobStatusResult {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [step, setStep] = useState<BackendStep | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [heraCompletedClips, setHeraCompletedClips] = useState<number>(0);
  const [heraTotalClips, setHeraTotalClips] = useState<number>(0);
  const [heraAttempt, setHeraAttempt] = useState<number>(0);
  const [heraMaxAttempts, setHeraMaxAttempts] = useState<number>(0);
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
        setHeraCompletedClips(Math.max(0, job.hera_completed_clips ?? 0));
        setHeraTotalClips(Math.max(0, job.hera_total_clips ?? 0));
        setHeraAttempt(Math.max(0, job.hera_attempt ?? 0));
        setHeraMaxAttempts(Math.max(0, job.hera_max_attempts ?? 0));
        if (job.error) setError(job.error);
        if (job.status === "done") {
          setVideoUrl(job.video_url ?? getVideoUrl(jobId));
          return;
        }
        if (job.status === "error") return;
        timer = window.setTimeout(tick, POLL_MS);
      } catch (err) {
        if (cancelled.current) return;
        const message = err instanceof Error ? err.message : "Failed to fetch job";
        setError(message);
        if (message.includes("Job not found")) {
          return;
        }
        timer = window.setTimeout(tick, POLL_MS);
      }
    };

    void tick();

    return () => {
      cancelled.current = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [jobId]);

  return {
    status,
    step,
    progress,
    error,
    videoUrl,
    heraCompletedClips,
    heraTotalClips,
    heraAttempt,
    heraMaxAttempts,
  };
}
