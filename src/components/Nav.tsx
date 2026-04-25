import { Link } from "react-router-dom";

export const Nav = () => {
  return (
    <header className="sticky top-0 z-40 w-full bg-surface border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="font-semibold text-primary text-lg tracking-tight">
          CorpuScan
        </Link>
        <Link
          to="/dashboard"
          className="inline-flex items-center bg-accent text-accent-foreground rounded-lg px-4 py-2 text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          Start now
        </Link>
      </div>
    </header>
  );
};

export default Nav;
