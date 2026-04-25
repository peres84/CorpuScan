import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { PromoCard } from "@/components/ui/card-9";

interface Step {
  num: string;
  label: string;
  title: React.ReactNode;
  buttonText: string;
}

const STEPS: Step[] = [
  {
    num: "01",
    label: "Step 01 · Upload",
    title: "Drop a quarterly report PDF, paste a URL, or search a query.",
    buttonText: "Upload now",
  },
  {
    num: "02",
    label: "Step 02 · Extract",
    title: "A finance agent finds the signal in the noise.",
    buttonText: "See an example",
  },
  {
    num: "03",
    label: "Step 03 · Narrate",
    title: "A scripter agent writes a 4-scene voiceover.",
    buttonText: "Hear a sample",
  },
  {
    num: "04",
    label: "Step 04 · Render",
    title: "Motion graphics and voice combine into a 2-minute video.",
    buttonText: "Generate yours",
  },
];

export const HowItWorks = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState<Record<string, boolean>>(
    () => Object.fromEntries(STEPS.map((s) => [s.num, true])),
  );

  const handleClose = (num: string) => {
    setVisible((prev) => ({ ...prev, [num]: false }));
  };

  return (
    <section id="how" className="max-w-6xl mx-auto px-6 py-24">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <p className="font-mono text-accent text-xs uppercase tracking-wider">
            The pipeline
          </p>
          <h2 className="mt-3 text-3xl font-semibold text-primary">How it works</h2>
        </div>
        <p className="text-secondary text-sm max-w-sm">
          Four agents work in sequence. From raw PDF to finished briefing in under three minutes.
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <AnimatePresence mode="popLayout">
          {STEPS.map((step) =>
            visible[step.num] ? (
              <PromoCard
                key={step.num}
                label={step.label}
                title={step.title}
                buttonText={step.buttonText}
                onButtonClick={() => navigate("/dashboard")}
                onClose={() => handleClose(step.num)}
              />
            ) : null,
          )}
        </AnimatePresence>
      </div>
    </section>
  );
};

export default HowItWorks;
