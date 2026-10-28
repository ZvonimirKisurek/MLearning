"use client";

import { MotionConfig, motion } from "framer-motion";

/**
 * A template (unlike a layout) is re-mounted on every navigation, which is exactly what a page-enter animation needs:
 * each route fades and rises in. MotionConfig reducedMotion="user" honours the OS accessibility setting.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
        {children}
      </motion.div>
    </MotionConfig>
  );
}
