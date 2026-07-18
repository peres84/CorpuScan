import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, FileSearch, Clock, RotateCcw, ChevronDown, ChevronRight, FileX } from "lucide-react";
import {
  useInvestigationFindings,
  useInvestigationBuffer,
  useInvestigationReport,
} from "@/hooks/useInvestigation";
import type { Finding, BufferRow, InvestigationReport } from "@/hooks/useInvestigation";
import KnowledgeGraph from "./KnowledgeGraph";

interface InvestigationResultsProps {
  jobId: string;
  onReset: () => void;
}

const InvestigationResults = ({ jobId, onReset }: InvestigationResultsProps) => {
  const { findings, fetchFindings } = useInvestigationFindings(jobId);
  const { buffer, fetchBuffer } = useInvestigationBuffer(jobId);
  const { report, fetchReport } = useInvestigationReport(jobId);
  const [activeTab, setActiveTab] = useState<"findings" | "graph" | "steps">("findings");

  useEffect(() => {
    fetchFindings();
    fetchBuffer();
    fetchReport();
  }, [fetchFindings, fetchBuffer, fetchReport]);

  // Get files not analyzed from report
  const notAnalyzedFiles = report?.not_analyzed_files || [];

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
        <TabButton active={activeTab === "graph"} onClick={() => setActiveTab("graph")}>
          Knowledge Graph
        </TabButton>
        <TabButton active={activeTab === "steps"} onClick={() => setActiveTab("steps")}>
          Investigation Steps ({buffer.length})
        </TabButton>
      </div>

      {/* Tab content */}
      {activeTab === "findings" && <FindingsTimeline findings={findings} buffer={buffer} notAnalyzedFiles={notAnalyzedFiles} />}
      {activeTab === "graph" && <KnowledgeGraph jobId={jobId} />}
      {activeTab === "steps" && <StepsView buffer={buffer} />}
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

function FindingsTimeline({ findings, buffer, notAnalyzedFiles }: { findings: Finding[]; buffer: BufferRow[]; notAnalyzedFiles: string[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleExpand = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  if (findings.length === 0) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <CheckCircle className="h-5 w-5" />
        <span>No suspicious findings detected.</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Findings with timeline dots */}
      <div className="space-y-1">
        {findings.map((finding, idx) => {
          const findingNumber = idx + 1;
          const relatedFile = buffer[idx]?.filename || "Unknown";
          const isExpanded = expanded.has(idx);

          return (
            <div key={finding.finding_id} className="flex gap-3">
              {/* Timeline line */}
              <div className="flex flex-col items-center pt-1">
                <SeverityDot likelihood={finding.fraud_likelihood} />
                {idx < findings.length - 1 && <div className="w-px flex-1 bg-border mt-1" />}
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <button
                  onClick={() => toggleExpand(idx)}
                  className="w-full text-left flex items-start gap-2"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
                      )}
                      <span className="text-sm font-semibold text-foreground">
                        Finding {findingNumber}
                      </span>
                      <LikelihoodBadge value={finding.fraud_likelihood} />
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 ml-5">
                      → {relatedFile}
                    </p>
                  </div>
                </button>

                {isExpanded && (
                  <div className="ml-5 mt-2 space-y-3">
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                      {finding.finding_text}
                    </p>

                    {/* Flagged entries table */}
                    {buffer[idx]?.flagged_entries && buffer[idx].flagged_entries.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-foreground mb-1">Flagged Entries:</p>
                        <div className="border rounded-md overflow-hidden">
                          <table className="w-full text-xs">
                            <thead className="bg-muted/50">
                              <tr>
                                <th className="px-2 py-1 text-left font-medium text-muted-foreground">Ref</th>
                                <th className="px-2 py-1 text-left font-medium text-muted-foreground">Data</th>
                                <th className="px-2 py-1 text-left font-medium text-muted-foreground">Reason</th>
                              </tr>
                            </thead>
                            <tbody>
                              {buffer[idx].flagged_entries.map((entry, eIdx) => (
                                <tr key={eIdx} className="border-t">
                                  <td className="px-2 py-1 font-mono text-muted-foreground">{entry.row_ref}</td>
                                  <td className="px-2 py-1 text-muted-foreground">{entry.data}</td>
                                  <td className="px-2 py-1 text-muted-foreground">{entry.reason}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Tavily research results */}
                    {buffer[idx]?.tavily_results && buffer[idx].tavily_results.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-foreground mb-1">External Research (Tavily):</p>
                        <div className="space-y-1">
                          {buffer[idx].tavily_results.map((tr, tIdx) => (
                            <div key={tIdx} className="text-xs bg-blue-500/5 border border-blue-500/20 rounded px-2 py-1">
                              <span className="font-medium text-blue-600">Query:</span>{" "}
                              <span className="text-muted-foreground">{tr.query}</span>
                              <p className="text-muted-foreground mt-0.5">{tr.result.slice(0, 200)}{tr.result.length > 200 ? "..." : ""}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {finding.evidence.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">Evidence:</p>
                        {finding.evidence.map((ev, evIdx) => (
                          <div key={evIdx} className="text-xs text-muted-foreground bg-muted/50 rounded px-2 py-1">
                            <span className="font-mono">{ev.location}</span> — {ev.passage}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Related files with cross-file discrepancies */}
                    {buffer[idx]?.related_files && buffer[idx].related_files.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-foreground mb-1">Related Files:</p>
                        <div className="space-y-1">
                          {buffer[idx].related_files.map((rf, rfIdx) => (
                            <div key={rfIdx} className="text-xs border rounded px-2 py-1.5 bg-muted/30">
                              <div className="flex items-center gap-1">
                                <FileSearch className="h-3 w-3 text-muted-foreground" />
                                <span className="font-medium text-foreground">{rf.filename}</span>
                              </div>
                              <p className="text-muted-foreground mt-0.5">
                                <span className="font-medium">Relationship:</span> {rf.relationship}
                              </p>
                              <p className="text-muted-foreground">
                                <span className="font-medium">Suspicion:</span> {rf.suspicion_contribution}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Files not analyzed */}
      {notAnalyzedFiles.length > 0 && (
        <div className="rounded-lg border border-dashed p-4 space-y-2">
          <div className="flex items-center gap-3">
            <FileX className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {notAnalyzedFiles.length} file{notAnalyzedFiles.length !== 1 ? "s" : ""} not analyzed
              </p>
              <p className="text-xs text-muted-foreground">
                Uploaded but not visited during the DFS investigation.
              </p>
            </div>
          </div>
          <ul className="ml-8 space-y-0.5">
            {notAnalyzedFiles.map((filename) => (
              <li key={filename} className="text-xs text-muted-foreground flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-muted-foreground/50" />
                {filename}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StepsView({ buffer }: { buffer: BufferRow[] }) {
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
            <span className="text-xs font-mono text-muted-foreground w-6 flex-shrink-0">
              {idx + 1})
            </span>
            <FileSearch className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm font-medium text-foreground flex-1 truncate">
              {row.filename}
            </span>
            <LikelihoodBadge value={row.fraud_likelihood} />
            {expanded.has(idx) ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
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

function SeverityDot({ likelihood }: { likelihood: number }) {
  const color =
    likelihood >= 0.7
      ? "bg-destructive"
      : likelihood >= 0.4
      ? "bg-yellow-500"
      : "bg-muted-foreground";
  return <div className={`w-3 h-3 rounded-full ${color} flex-shrink-0`} />;
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
