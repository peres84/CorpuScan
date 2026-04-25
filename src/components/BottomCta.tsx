import { Link } from "react-router-dom";

export const BottomCta = () => {
  return (
    <section className="max-w-4xl mx-auto px-6 py-16">
      <div className="bg-surface border border-gray-200 rounded-2xl p-10 text-center shadow-sm">
        <h3 className="text-2xl font-semibold text-primary">
          Ready to brief your team in 2 minutes?
        </h3>
        <p className="mt-2 text-secondary">
          Generate a video from your next earnings report.
        </p>
        <div className="mt-6">
          <Link
            to="/dashboard"
            className="inline-flex items-center bg-accent text-accent-foreground rounded-lg text-base px-6 py-3 font-medium hover:bg-accent/90 transition-colors"
          >
            Start now
          </Link>
        </div>
      </div>
    </section>
  );
};

export default BottomCta;
