import { useState } from "react";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import FileUpload from "@/components/investigation/FileUpload";
import InvestigationProgress from "@/components/investigation/InvestigationProgress";
import InvestigationResults from "@/components/investigation/InvestigationResults";
import {
  useCreateInvestigation,
  useInvestigationStatus,
} from "@/hooks/useInvestigation";

const InvestigatePage = () => {
  const [jobId, setJobId] = useState<string | null>(null);
  const { createInvestigation, isLoading: isCreating, error: createError } = useCreateInvestigation();
  const { status, isPolling } = useInvestigationStatus(jobId);

  const handleSubmit = async (files: File[], priorityFiles: string[]) => {
    const id = await createInvestigation(files, priorityFiles.length > 0 ? priorityFiles : undefined);
    if (id) setJobId(id);
  };

  const isDone = status?.status === "done";
  const isError = status?.status === "error";
  const isRunning = status?.status === "running" || status?.status === "pending";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Nav />
      <main className="flex-1 px-6 pb-16">
        <div className="max-w-5xl mx-auto mt-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Audit Investigation
          </h1>
          <p className="text-muted-foreground mb-8">
            Upload financial documents for AI-powered forensic investigation.
            The system will analyze patterns, follow evidence trails, and produce
            an evidence-backed report.
          </p>

          {!jobId && (
            <FileUpload
              onSubmit={handleSubmit}
              isLoading={isCreating}
              error={createError}
            />
          )}

          {jobId && isRunning && (
            <InvestigationProgress status={status} />
          )}

          {jobId && isError && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
              <h2 className="text-lg font-semibold text-destructive mb-2">Investigation Failed</h2>
              <p className="text-sm text-muted-foreground">{status?.error || "An unknown error occurred."}</p>
              <button
                onClick={() => setJobId(null)}
                className="mt-4 px-4 py-2 text-sm rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80"
              >
                Start New Investigation
              </button>
            </div>
          )}

          {jobId && isDone && (
            <InvestigationResults jobId={jobId} onReset={() => setJobId(null)} />
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default InvestigatePage;
