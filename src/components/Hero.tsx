import { Link } from "react-router-dom";

const handleScrollToHow = (e: React.MouseEvent<HTMLAnchorElement>) => {
  e.preventDefault();
  const el = document.getElementById("how");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
};

export const Hero = () => {
  return (
    <section className="max-w-4xl mx-auto px-6 py-24 text-center">
      <p className="text-accent uppercase tracking-wider text-xs font-semibold">
        AI briefings for business reports
      </p>
      <h1 className="mt-6 text-5xl md:text-6xl font-bold text-primary leading-tight">
        Turn quarterly reports into 2-minute video briefings.
      </h1>
      <p className="mt-6 text-xl text-secondary max-w-2xl mx-auto">
        Upload a report, get a boardroom-ready explainer video in under 3 minutes.
      </p>
      <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
        <Link
          to="/dashboard"
          className="inline-flex items-center bg-accent text-accent-foreground rounded-lg text-lg px-6 py-3 font-medium hover:bg-accent/90 transition-colors"
        >
          Start now
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
        For investor relations · Finance · Strategy · Internal communications
      </p>
    </section>
  );
};

export default Hero;
