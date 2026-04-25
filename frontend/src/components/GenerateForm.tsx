import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dropzone } from "@/components/Dropzone";
import { useGenerate } from "@/hooks/useGenerate";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Loader2 } from "lucide-react";

type TabKey = "upload" | "url" | "search";

const SAMPLE_URL = "https://www.apple.com/newsroom/pdfs/fy2024-q4/FY24_Q4_Consolidated_Financial_Statements.pdf";

export const GenerateForm = () => {
  const [tab, setTab] = useState<TabKey>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const navigate = useNavigate();
  const { mutate, loading, error } = useGenerate();

  const isValid = useMemo<boolean>(() => {
    if (tab === "upload") return file !== null;
    if (tab === "url") return /^https:\/\/.+/i.test(url.trim());
    if (tab === "search") return query.trim().length > 0;
    return false;
  }, [tab, file, url, query]);

  const handleSubmit = async (overrideUrl?: string): Promise<void> => {
    try {
      const payload =
        overrideUrl !== undefined
          ? { url: overrideUrl }
          : tab === "upload"
            ? { file: file ?? undefined }
            : tab === "url"
              ? { url: url.trim() }
              : { query: query.trim() };

      const { jobId } = await mutate(payload);
      navigate(`/dashboard/job/${jobId}`);
    } catch {
      /* error surfaced via hook */
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-surface rounded-2xl shadow-sm p-8 mt-12 border border-border">
      <h1 className="text-2xl font-semibold text-primary">Generate a briefing video</h1>
      <p className="text-secondary mt-1">Choose how you want to provide the report.</p>

      <div className="mt-8">
        <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
          <TabsList className="grid grid-cols-3 w-full bg-muted">
            <TabsTrigger value="upload">Upload PDF</TabsTrigger>
            <TabsTrigger value="url">From URL</TabsTrigger>
            <TabsTrigger value="search">Search</TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="mt-6">
            <Dropzone file={file} onFileChange={setFile} />
          </TabsContent>

          <TabsContent value="url" className="mt-6">
            <label htmlFor="report-url" className="block text-sm font-medium text-primary mb-2">
              Report URL
            </label>
            <input
              id="report-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://investor.apple.com/...10-Q.pdf"
              className="w-full rounded-lg border border-border px-4 py-3 text-primary placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 transition"
            />
            {url.length > 0 && !/^https:\/\//i.test(url.trim()) && (
              <p className="mt-2 text-xs text-destructive">URL must start with https://</p>
            )}
          </TabsContent>

          <TabsContent value="search" className="mt-6">
            <label htmlFor="report-query" className="block text-sm font-medium text-primary mb-2">
              Query
            </label>
            <input
              id="report-query"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Apple Q4 2025 earnings"
              className="w-full rounded-lg border border-border px-4 py-3 text-primary placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 transition"
            />
            <p className="mt-2 text-xs text-secondary">
              We&apos;ll find and read the most relevant report.
            </p>
          </TabsContent>
        </Tabs>
      </div>

      {error && (
        <div className="mt-6">
          <ErrorBanner message={error} />
        </div>
      )}

      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={!isValid || loading}
        className="mt-8 w-full inline-flex items-center justify-center gap-2 bg-accent text-accent-foreground rounded-lg text-lg py-3 font-medium hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {loading ? "Submitting" : "Generate video"}
      </button>

      <div className="mt-4 text-center">
        <button
          type="button"
          onClick={() => void handleSubmit(SAMPLE_URL)}
          disabled={loading}
          className="text-sm text-secondary hover:text-accent underline-offset-4 hover:underline disabled:opacity-50"
        >
          Try a sample report
        </button>
      </div>
    </div>
  );
};

export default GenerateForm;
