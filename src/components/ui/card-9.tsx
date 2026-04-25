import * as React from "react";
import { X } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { Button, type ButtonProps } from "@/components/ui/button";

interface PromoCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  label: string;
  title: React.ReactNode;
  buttonText?: string;
  buttonVariant?: ButtonProps["variant"];
  onButtonClick?: () => void;
  onClose: () => void;
  showLoader?: boolean;
}

const PromoCard = React.forwardRef<HTMLDivElement, PromoCardProps>(
  (
    {
      className,
      label,
      title,
      buttonText,
      buttonVariant = "secondary",
      onButtonClick,
      onClose,
      showLoader = true,
      ...props
    },
    ref,
  ) => {
    const keyframes = `
      @keyframes promo-card-loader-pulse {
        0%, 100% { opacity: 0.3; transform: scale(0.85); }
        50% { opacity: 1; transform: scale(1); }
      }
    `;

    return (
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.98 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="w-full h-full"
      >
        <div
          ref={ref}
          className={cn(
            "relative overflow-hidden rounded-2xl bg-surface text-primary p-6 shadow-sm",
            "border border-border h-full flex flex-col",
            className,
          )}
          {...props}
        >
          <style>{keyframes}</style>

          {/* SVG grain filter */}
          <svg className="absolute h-0 w-0" aria-hidden="true">
            <filter id="promo-grain">
              <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
              <feColorMatrix type="saturate" values="0" />
            </filter>
          </svg>

          {/* Grainy texture overlay (very subtle on light surface) */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.06] mix-blend-multiply"
            style={{ filter: "url(#promo-grain)" }}
          />

          {/* Subtle accent glow */}
          <div
            aria-hidden
            className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full bg-accent/10 blur-3xl"
          />

          {/* Close Button */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Dismiss"
            className="absolute top-3 right-3 inline-flex h-7 w-7 items-center justify-center rounded-full text-secondary hover:text-primary hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>

          <div className="relative flex flex-col gap-5 h-full">
            {showLoader && (
              <div className="flex items-center gap-1.5" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-accent"
                    style={{
                      animation: "promo-card-loader-pulse 1.2s ease-in-out infinite",
                      animationDelay: `${i * 0.15}s`,
                    }}
                  />
                ))}
              </div>
            )}

            <div className="space-y-2 flex-1">
              <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
                {label}
              </p>
              <h3 className="text-base font-semibold leading-snug text-primary">
                {title}
              </h3>
            </div>

            <div className="pt-1 mt-auto">
              <Button
                variant={buttonVariant}
                onClick={onButtonClick}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {buttonText}
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    );
  },
);

PromoCard.displayName = "PromoCard";

export { PromoCard };
