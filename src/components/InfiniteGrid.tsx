import { useRef } from "react";
import {
  motion,
  useMotionValue,
  useMotionTemplate,
  useAnimationFrame,
  type MotionValue,
} from "framer-motion";

const CELL = 40;

interface GridPatternProps {
  offsetX: MotionValue<number>;
  offsetY: MotionValue<number>;
  strokeColor: string;
  strokeWidth: number;
}

const GridPattern = ({ offsetX, offsetY, strokeColor, strokeWidth }: GridPatternProps) => {
  const transform = useMotionTemplate`translate(${offsetX}px, ${offsetY}px)`;
  return (
    <svg width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern
          id={`grid-${strokeColor.replace(/[^a-z0-9]/gi, "")}`}
          width={CELL}
          height={CELL}
          patternUnits="userSpaceOnUse"
        >
          <path
            d={`M ${CELL} 0 L 0 0 0 ${CELL}`}
            fill="none"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
          />
        </pattern>
      </defs>
      <motion.rect
        x={-CELL}
        y={-CELL}
        width="calc(100% + 80px)"
        height="calc(100% + 80px)"
        fill={`url(#grid-${strokeColor.replace(/[^a-z0-9]/gi, "")})`}
        style={{ transform }}
      />
    </svg>
  );
};

interface InfiniteGridProps {
  className?: string;
}

export const InfiniteGrid = ({ className }: InfiniteGridProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(-9999);
  const mouseY = useMotionValue(-9999);

  const baseOffsetX = useMotionValue(0);
  const baseOffsetY = useMotionValue(0);
  const accentOffsetX = useMotionValue(0);
  const accentOffsetY = useMotionValue(0);

  useAnimationFrame(() => {
    baseOffsetX.set((baseOffsetX.get() + 0.25) % CELL);
    baseOffsetY.set((baseOffsetY.get() + 0.25) % CELL);
    accentOffsetX.set((accentOffsetX.get() + 0.5) % CELL);
    accentOffsetY.set((accentOffsetY.get() + 0.5) % CELL);
  });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
  };

  const handleMouseLeave = () => {
    mouseX.set(-9999);
    mouseY.set(-9999);
  };

  const accentMask = useMotionTemplate`radial-gradient(280px circle at ${mouseX}px ${mouseY}px, black, transparent 70%)`;

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      aria-hidden
      className={
        "absolute inset-0 overflow-hidden pointer-events-auto " + (className ?? "")
      }
    >
      {/* Soft background wash */}
      <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-background" />

      {/* Base subtle grid */}
      <div className="absolute inset-0 opacity-60">
        <GridPattern
          offsetX={baseOffsetX}
          offsetY={baseOffsetY}
          strokeColor="hsl(220 13% 88%)"
          strokeWidth={1}
        />
      </div>

      {/* Accent grid revealed by cursor */}
      <motion.div
        className="absolute inset-0"
        style={{
          WebkitMaskImage: accentMask,
          maskImage: accentMask,
        }}
      >
        <GridPattern
          offsetX={accentOffsetX}
          offsetY={accentOffsetY}
          strokeColor="hsl(188 94% 43%)"
          strokeWidth={1.25}
        />
      </motion.div>

      {/* Top + bottom fade for legibility */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-background to-transparent pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-background to-transparent pointer-events-none" />
    </div>
  );
};

export default InfiniteGrid;
