import { useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { PromoCard } from "@/components/ui/card-9";

interface Step {
  num: string;
  label: string;
  title: React.ReactNode;
}

const STEPS: Step[] = [
  {
    num: "01",
    label: "Step 01 · Upload",
    title: "Upload financial documents — invoices, ledgers, bank statements, contracts.",
  },
  {
    num: "02",
    label: "Step 02 · Graph",
    title: "AI builds a knowledge graph connecting entities across all documents.",
  },
  {
    num: "03",
    label: "Step 03 · Investigate",
    title: "A forensic agent follows evidence trails using depth-first search.",
  },
  {
    num: "04",
    label: "Step 04 · Report",
    title: "Evidence-backed findings with exact document, page, and passage references.",
  },
];

export const HowInvestigationWorks = () => {
  const [visible, setVisible] = useState<Record<string, boolean>>(
    () => Object.fromEntries(STEPS.map((s) => [s.num, true])),
  );

  const handleClose = (num: string) => {
    setVisible((prev) => ({ ...prev, [num]: false }));
  };

  return (
    <section className="max-w-6xl mx-auto px-6 py-24 border-t border-border">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <p className="font-mono text-accent text-xs uppercase tracking-wider">
            Audit Investigation
          </p>
          <h2 className="mt-3 text-3xl font-semibold text-primary">How fraud investigation works</h2>
        </div>
        <p className="text-secondary text-sm max-w-sm">
          An AI forensic investigator analyzes document collections, discovers hidden
          relationships, and produces evidence-backed findings.
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 items-stretch auto-rows-fr">
        <AnimatePresence mode="popLayout">
          {STEPS.map((step) =>
            visible[step.num] ? (
              <PromoCard
                key={step.num}
                label={step.label}
                title={step.title}
                onClose={() => handleClose(step.num)}
              />
            ) : null,
          )}
        </AnimatePresence>
      </div>

      <div className="mt-10 text-center">
        <Link
          to="/investigate"
          className="inline-flex items-center border border-accent text-accent rounded-lg px-6 py-3 font-medium hover:bg-accent/10 transition-colors"
        >
          Start an investigation
        </Link>
      </div>
    </section>
  );
};

export default HowInvestigationWorks;
