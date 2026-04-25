import { Check } from "lucide-react";
import type { BackendStep } from "@/lib/api";

interface JobProgressProps {
  step: BackendStep | null;
  progress: number;
}

interface UiStep {
  key: string;
  label: string;
  backendSteps: BackendStep[];
}

const UI_STEPS: UiStep[] = [
  { key: "ingest", label: "Reading source material", backendSteps: ["ingest"] },
  { key: "finance", label: "Extracting key facts", backendSteps: ["finance"] },
  { key: "scripter", label: "Writing voiceover script", backendSteps: ["scripter"] },
  { key: "tts", label: "Recording narration", backendSteps: ["tts"] },
  { key: "hera", label: "Generating motion graphics", backendSteps: ["hera_plan", "hera_render"] },
  { key: "compose", label: "Rendering final video", backendSteps: ["compose"] },
];

const ORDER: BackendStep[] = ["ingest", "finance", "scripter", "tts", "hera_plan", "hera_render", "compose", "done"];

function stepState(uiStep: UiStep, current: BackendStep | null): "pending" | "running" | "done" {
  if (!current) return "pending";
  const currentIdx = ORDER.indexOf(current);
  const stepMaxIdx = Math.max(...uiStep.backendSteps.map((s) => ORDER.indexOf(s)));
  if (current === "done") return "done";
  if (uiStep.backendSteps.includes(current)) return "running";
  if (currentIdx > stepMaxIdx) return "done";
  return "pending";
}

export const JobProgress = ({ step, progress }: JobProgressProps) => {
  return (
    <div>
      <ul className="space-y-3">
        {UI_STEPS.map((s) => {
          const state = stepState(s, step);
          return (
            <li key={s.key} className="flex items-center gap-3">
              <span className="inline-flex h-6 w-6 items-center justify-center shrink-0">
                {state === "done" && (
                  <span className="h-6 w-6 rounded-full bg-accent text-accent-foreground inline-flex items-center justify-center">
                    <Check className="h-3.5 w-3.5" aria-hidden />
                  </span>
                )}
                {state === "running" && (
                  <span className="relative inline-flex h-6 w-6 items-center justify-center">
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-accent/40 animate-ping" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-accent" />
                  </span>
                )}
                {state === "pending" && (
                  <span className="h-3 w-3 rounded-full bg-gray-200" />
                )}
              </span>
              <span
                className={`text-sm ${
                  state === "pending"
                    ? "text-secondary"
                    : state === "running"
                      ? "text-primary font-medium"
                      : "text-primary"
                }`}
              >
                {s.label}
              </span>
            </li>
          );
        })}
      </ul>

      <div className="mt-8">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-secondary uppercase tracking-wider font-semibold">
            Progress
          </span>
          <span className="font-mono text-xs text-secondary">{Math.round(progress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className="h-2 bg-accent rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default JobProgress;
