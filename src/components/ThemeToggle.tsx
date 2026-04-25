import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";

export const ThemeToggle = () => {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-pressed={isDark}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-secondary hover:text-primary hover:bg-muted transition-colors"
    >
      <Sun className={`h-4 w-4 transition-all ${isDark ? "scale-0 -rotate-90 absolute" : "scale-100 rotate-0"}`} aria-hidden />
      <Moon className={`h-4 w-4 transition-all ${isDark ? "scale-100 rotate-0" : "scale-0 rotate-90 absolute"}`} aria-hidden />
    </button>
  );
};

export default ThemeToggle;
