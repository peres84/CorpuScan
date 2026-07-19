import { Loader2 } from "lucide-react";
import type { InvestigationStatus } from "@/hooks/useInvestigation";

interface InvestigationProgressProps {
  status: InvestigationStatus | null;
}

const STEP_LABELS: Record<string, string> = {
  parse: "Parsing documents",
  build_graph: "Building document graph",
  investigate: "Running investigation",
  report: "Generating report",
  done: "Complete",
};

const InvestigationProgress = ({ status }: InvestigationProgressProps) => {
  if (!status) {
    return (
      <div className="flex items-center gap-3 p-6 rounded-lg border">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">Initializing...</span>
      </div>
    );
  }

  const stepLabel = STEP_LABELS[status.step] || status.step;
  const progress = status.progress;

  return (
    <div className="rounded-lg border p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">{stepLabel}</p>
          <p className="text-xs text-muted-foreground">
            {progress}% complete
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-muted rounded-full h-2">
        <div
          className="bg-primary h-2 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Step indicators */}
      <div className="flex gap-2">
        {Object.entries(STEP_LABELS).map(([key, label]) => {
          const isActive = key === status.step;
          const stepOrder = Object.keys(STEP_LABELS);
          const currentIdx = stepOrder.indexOf(status.step);
          const thisIdx = stepOrder.indexOf(key);
          const isPast = thisIdx < currentIdx;

          return (
            <div
              key={key}
              className={`flex-1 h-1 rounded-full ${
                isPast
                  ? "bg-primary"
                  : isActive
                  ? "bg-primary/60"
                  : "bg-muted"
              }`}
              title={label}
            />
          );
        })}
      </div>
    </div>
  );
};

export default InvestigationProgress;
