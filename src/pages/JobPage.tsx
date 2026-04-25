import { Link, useParams } from "react-router-dom";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import JobProgress from "@/components/JobProgress";
import JobResult from "@/components/JobResult";
import ErrorBanner from "@/components/ErrorBanner";
import { useJobStatus } from "@/hooks/useJobStatus";
import { getVideoUrl } from "@/lib/api";

const JobPage = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const { status, step, progress, error, videoUrl } = useJobStatus(jobId);

  const isWorking = status === null || status === "pending" || status === "running";
  const isDone = status === "done";
  const isError = status === "error";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Nav />
      <main className="flex-1 px-6 pb-16">
        <div className="max-w-2xl mx-auto bg-surface rounded-2xl shadow-sm p-8 mt-12 border border-gray-200">
          {isWorking && (
            <>
              <h1 className="text-2xl font-semibold text-primary">Generating your briefing</h1>
              <p className="text-secondary mt-1">This usually takes 1 to 3 minutes.</p>
              <div className="mt-8">
                <JobProgress step={step} progress={progress} />
              </div>
              <div className="mt-8 text-center">
                <Link
                  to="/dashboard"
                  className="text-sm text-secondary hover:text-primary underline-offset-4 hover:underline"
                >
                  Cancel
                </Link>
              </div>
            </>
          )}

          {isDone && jobId && (
            <>
              <h1 className="text-2xl font-semibold text-primary">Your briefing is ready</h1>
              <p className="text-secondary mt-1">Review, share, or download.</p>
              <div className="mt-6">
                <JobResult videoUrl={videoUrl ?? getVideoUrl(jobId)} />
              </div>
            </>
          )}

          {isError && (
            <>
              <h1 className="text-2xl font-semibold text-primary">Generation failed</h1>
              <p className="text-secondary mt-1">We couldn&apos;t complete this briefing.</p>
              <div className="mt-6">
                <ErrorBanner message={error ?? "An unknown error occurred."} />
              </div>
              <div className="mt-6">
                <Link
                  to="/dashboard"
                  className="inline-flex items-center bg-accent text-accent-foreground rounded-lg px-5 py-3 font-medium hover:bg-accent/90 transition-colors"
                >
                  Try again
                </Link>
              </div>
            </>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default JobPage;
