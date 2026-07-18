import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, FileSearch, Clock, RotateCcw } from "lucide-react";
import {
  useInvestigationFindings,
  useInvestigationBuffer,
  useInvestigationReport,
} from "@/hooks/useInvestigation";
import type { Finding, BufferRow, InvestigationReport } from "@/hooks/useInvestigation";

interface InvestigationResultsProps {
  jobId: string;
  onReset: () => void;
}

const InvestigationResults = ({ jobId, onReset }: InvestigationResultsProps) => {
  const { findings, fetchFindings } = useInvestigationFindings(jobId);
  const { buffer, fetchBuffer } = useInvestigationBuffer(jobId);
  const { report, fetchReport } = useInvestigationReport(jobId);
  const [activeTab, setActiveTab] = useState<"findings" | "timeline" | "buffer">("findings");

  useEffect(() => {
    fetchFindings();
    fetchBuffer();
    fetchReport();
  }, [fetchFindings, fetchBuffer, fetchReport]);

  return (
    <div className="space-y-6">
      {/* Summary banner */}
      {report && (
        <div className="rounded-lg border p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Investigation Complete</h2>
            <button
              onClick={onReset}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80"
            >
              <RotateCcw className="h-3 w-3" />
              New Investigation
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-3 rounded-md bg-muted/50">
              <p className="text-2xl font-bold text-foreground">
                {(report.overall_fraud_likelihood * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-muted-foreground">Fraud Likelihood</p>
            </div>
            <div className="text-center p-3 rounded-md bg-muted/50">
              <p className="text-2xl font-bold text-foreground">
                {report.documents_investigated}
              </p>
              <p className="text-xs text-muted-foreground">Docs Investigated</p>
            </div>
            <div className="text-center p-3 rounded-md bg-muted/50">
              <p className="text-2xl font-bold text-foreground">
                {report.findings.length}
              </p>
              <p className="text-xs text-muted-foreground">Findings</p>
            </div>
          </div>
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 border-b">
        <TabButton active={activeTab === "findings"} onClick={() => setActiveTab("findings")}>
          Findings ({findings.length})
        </TabButton>
        <TabButton active={activeTab === "timeline"} onClick={() => setActiveTab("timeline")}>
          Timeline
        </TabButton>
        <TabButton active={activeTab === "buffer"} onClick={() => setActiveTab("buffer")}>
          Investigation Steps ({buffer.length})
        </TabButton>
      </div>

      {/* Tab content */}
      {activeTab === "findings" && <FindingsList findings={findings} />}
      {activeTab === "timeline" && <TimelineView buffer={buffer} />}
      {activeTab === "buffer" && <BufferView buffer={buffer} />}
    </div>
  );
};

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function FindingsList({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <CheckCircle className="h-5 w-5" />
        <span>No suspicious findings detected.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {findings.map((finding) => (
        <div key={finding.finding_id} className="rounded-lg border p-4 space-y-2">
          <div className="flex items-start gap-3">
            <SeverityIcon likelihood={finding.fraud_likelihood} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">
                  {finding.finding_id}
                </span>
                <LikelihoodBadge value={finding.fraud_likelihood} />
              </div>
              <p className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap">
                {finding.finding_text}
              </p>
            </div>
          </div>

          {finding.evidence.length > 0 && (
            <div className="ml-8 space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Evidence:</p>
              {finding.evidence.map((ev, idx) => (
                <div key={idx} className="text-xs text-muted-foreground bg-muted/50 rounded px-2 py-1">
                  <span className="font-mono">{ev.location}</span> — {ev.passage}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function TimelineView({ buffer }: { buffer: BufferRow[] }) {
  return (
    <div className="space-y-2">
      {buffer.map((row, idx) => (
        <div key={row.doc_id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="w-2 h-2 rounded-full bg-primary mt-2" />
            {idx < buffer.length - 1 && <div className="w-px flex-1 bg-border" />}
          </div>
          <div className="pb-4">
            <p className="text-sm font-medium text-foreground">{row.filename}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {row.notes_summary.slice(0, 150)}
              {row.notes_summary.length > 150 ? "..." : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function BufferView({ buffer }: { buffer: BufferRow[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleExpand = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="space-y-2">
      {buffer.map((row, idx) => (
        <div key={row.doc_id} className="rounded-lg border overflow-hidden">
          <button
            onClick={() => toggleExpand(idx)}
            className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/50"
          >
            <FileSearch className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm font-medium text-foreground flex-1 truncate">
              {row.filename}
            </span>
            <LikelihoodBadge value={row.fraud_likelihood} />
          </button>

          {expanded.has(idx) && (
            <div className="px-4 pb-4 space-y-2 border-t bg-muted/20">
              <p className="text-sm text-muted-foreground mt-2 whitespace-pre-wrap">
                {row.notes_summary}
              </p>
              {row.primary_next_doc && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">Next:</span> {row.primary_next_doc}
                </p>
              )}
              {row.open_questions.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  <span className="font-medium">Open questions:</span>
                  <ul className="list-disc ml-4 mt-1">
                    {row.open_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SeverityIcon({ likelihood }: { likelihood: number }) {
  if (likelihood >= 0.7) {
    return <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />;
  }
  if (likelihood >= 0.4) {
    return <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />;
  }
  return <Clock className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />;
}

function LikelihoodBadge({ value }: { value: number }) {
  const percent = (value * 100).toFixed(0);
  const color =
    value >= 0.7
      ? "bg-destructive/10 text-destructive"
      : value >= 0.4
      ? "bg-yellow-500/10 text-yellow-600"
      : "bg-muted text-muted-foreground";

  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${color}`}>
      {percent}%
    </span>
  );
}

export default InvestigationResults;
