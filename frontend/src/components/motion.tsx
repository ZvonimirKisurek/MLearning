"use client";

import { motion, type HTMLMotionProps } from "framer-motion";

/**
 * Small motion primitives. framer-motion needs the browser (it animates DOM nodes), so they are Client Components;
 * Server Components can still pass their (server-rendered) children into them.
 * Everything respects the OS "reduce motion" setting through MotionConfig in the root template.
 */
const EASE = [0.22, 1, 0.36, 1] as const;

export function Reveal({ delay = 0, y = 14, ...props }: HTMLMotionProps<"div"> & { delay?: number; y?: number }) {
  return <motion.div initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE, delay }} {...props} />;
}

export function Stagger({ children, className, gap = 0.07 }: { children: React.ReactNode; className?: string; gap?: number }) {
  return (
    <motion.div className={className} initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}>
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={{ hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } } }}>
      {children}
    </motion.div>
  );
}

export { motion };
