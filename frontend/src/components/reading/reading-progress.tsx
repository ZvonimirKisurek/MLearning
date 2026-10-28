"use client";

import { motion, useScroll, useSpring } from "framer-motion";

/** A thin bar under the header that fills as you scroll through the chapter. */
export function ReadingProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.3 });
  return <motion.div aria-hidden style={{ scaleX }} className="fixed inset-x-0 top-14 z-40 h-0.5 origin-left bg-gradient-to-r from-emerald-300 to-sky-300" />;
}
