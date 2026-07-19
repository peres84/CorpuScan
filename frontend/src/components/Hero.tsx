import { Link } from "react-router-dom";
import InfiniteGrid from "@/components/InfiniteGrid";

const handleScrollToHow = (e: React.MouseEvent<HTMLAnchorElement>) => {
  e.preventDefault();
  const el = document.getElementById("how");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
};

export const Hero = () => {
  return (
    <section className="relative overflow-hidden">
      <InfiniteGrid />

      <div className="relative max-w-4xl mx-auto px-6 py-28 md:py-36 text-center pointer-events-none">
        <h1 className="mt-6 text-5xl md:text-6xl font-bold text-primary leading-tight">
          AI-powered financial document intelligence.
        </h1>
        <p className="mt-6 text-xl text-secondary max-w-2xl mx-auto">
          Turn quarterly reports into video briefings — or investigate fraud across
          document collections with evidence-backed forensic analysis.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 pointer-events-auto">
          <Link
            to="/dashboard"
            className="inline-flex items-center bg-accent text-accent-foreground rounded-lg text-lg px-6 py-3 font-medium hover:bg-accent/90 transition-colors shadow-sm"
          >
            Start Report Analysis
          </Link>
          <Link
            to="/investigate"
            className="inline-flex items-center border border-accent text-accent rounded-lg text-lg px-6 py-3 font-medium hover:bg-accent/10 transition-colors"
          >
            Start Audit Investigation
          </Link>
          <a
            href="#how"
            onClick={handleScrollToHow}
            className="text-secondary hover:text-primary text-base underline-offset-4 hover:underline transition-colors"
          >
            See how it works
          </a>
        </div>

        <p className="mt-16 text-sm text-secondary">
          For investor relations · Finance · Internal audit · Compliance · Strategy
        </p>
      </div>
    </section>
  );
};

export default Hero;
