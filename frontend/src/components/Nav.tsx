import { Link } from "react-router-dom";
import ThemeToggle from "@/components/ThemeToggle";

export const Nav = () => {
  return (
    <header className="sticky top-0 z-40 w-full bg-surface/70 backdrop-blur-md border-b border-border supports-[backdrop-filter]:bg-surface/60">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="font-semibold text-primary text-lg tracking-tight">
          CorpuScan
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link
            to="/dashboard"
            className="inline-flex items-center bg-accent text-accent-foreground rounded-lg px-4 py-2 text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Start now
          </Link>
        </div>
      </div>
    </header>
  );
};

export default Nav;
