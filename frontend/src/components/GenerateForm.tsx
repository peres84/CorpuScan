import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dropzone } from "@/components/Dropzone";
import { useGenerate } from "@/hooks/useGenerate";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Loader2 } from "lucide-react";

type TabKey = "upload" | "url" | "search";
type TemplateId = "growth_comparison" | "earnings_comparison";
type OutputAspectRatio = "16:9" | "9:16";

const SAMPLE_URL = "https://www.apple.com/newsroom/pdfs/fy2024-q4/FY24_Q4_Consolidated_Financial_Statements.pdf";
const TEMPLATE_OPTIONS: Array<{ id: TemplateId; title: string; description: string }> = [
  {
    id: "growth_comparison",
    title: "Comparing Growth",
    description: "Focus on revenue growth, segment drivers, and momentum changes across uploaded periods.",
  },
  {
    id: "earnings_comparison",
    title: "Comparing Earnings",
    description: "Focus on margins, EPS, operating leverage, and the quality of profitability changes.",
  },
];

export const GenerateForm = () => {
  const [tab, setTab] = useState<TabKey>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [templateId, setTemplateId] = useState<TemplateId | null>("growth_comparison");
  const [outputAspectRatio, setOutputAspectRatio] = useState<OutputAspectRatio | null>("16:9");
  const navigate = useNavigate();
  const { mutate, loading, error } = useGenerate();

  const isValid = useMemo<boolean>(() => {
    if (tab === "upload") {
      return files.length > 0 && files.length <= 4 && templateId !== null && outputAspectRatio !== null;
    }
    if (tab === "url") return /^https:\/\/.+/i.test(url.trim());
    if (tab === "search") return query.trim().length > 0;
    return false;
  }, [tab, files, url, query, templateId, outputAspectRatio]);

  const handleSubmit = async (overrideUrl?: string): Promise<void> => {
    try {
      const payload =
        overrideUrl !== undefined
          ? { url: overrideUrl }
          : tab === "upload"
            ? {
                files,
                templateId: templateId ?? undefined,
                outputAspectRatio: outputAspectRatio ?? undefined,
              }
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
            <Dropzone files={files} onFilesChange={setFiles} />
            <div className="mt-6">
              <p className="text-sm font-medium text-primary">Template</p>
              <p className="mt-1 text-xs text-secondary">Pick the angle for PDF-based analysis.</p>
              <div className="mt-3 grid gap-3">
                {TEMPLATE_OPTIONS.map((option) => {
                  const selected = templateId === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setTemplateId(option.id)}
                      className={`rounded-xl border p-4 text-left transition-colors ${
                        selected
                          ? "border-accent bg-accent/5"
                          : "border-border bg-surface hover:border-accent/50"
                      }`}
                    >
                      <p className="text-sm font-semibold text-primary">{option.title}</p>
                      <p className="mt-1 text-sm text-secondary">{option.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="mt-6">
              <p className="text-sm font-medium text-primary">Output format</p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                {[
                  { value: "16:9" as const, label: "Desktop 16:9", description: "Landscape briefing for laptops and embeds." },
                  { value: "9:16" as const, label: "Mobile 9:16", description: "Portrait briefing for phone-first playback." },
                ].map((option) => {
                  const selected = outputAspectRatio === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setOutputAspectRatio(option.value)}
                      className={`rounded-xl border p-4 text-left transition-colors ${
                        selected
                          ? "border-accent bg-accent/5"
                          : "border-border bg-surface hover:border-accent/50"
                      }`}
                    >
                      <p className="text-sm font-semibold text-primary">{option.label}</p>
                      <p className="mt-1 text-sm text-secondary">{option.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>
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
