"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";
import { motion } from "framer-motion";
import { ArrowRight, BookCheck, Loader2 } from "lucide-react";
import { completeTaskAction } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { skillLabel } from "@/lib/skills";

/**
 * The "I read it" button. It stays disabled until the end of the chapter has actually been scrolled into view, a small
 * guard against ticking the box without reading. (It cannot prove understanding: that is what the questions at the end,
 * and your weekly teach-back, are for.)
 */
export function FinishChapter({ taskId, completed, skillSlug }: { taskId: string; completed: boolean; skillSlug: string }) {
  const end = useRef<HTMLDivElement>(null);
  const [reachedEnd, setReachedEnd] = useState(completed);
  const [done, setDone] = useState(completed);
  const [gain, setGain] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  useEffect(() => {
    if (!end.current || reachedEnd) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setReachedEnd(true), { threshold: 0.6 });
    io.observe(end.current);
    return () => io.disconnect();
  }, [reachedEnd]);

  function finish() {
    setError(null);
    start(async () => {
      const res = await completeTaskAction(taskId);
      if (!res.ok) return setError(res.error);
      setDone(true);
      if (!res.data.already_completed) setGain(`+${res.data.skill.delta.toFixed(2)} ${skillLabel(res.data.skill.slug || skillSlug)}`);
    });
  }

  return (
    <div ref={end} className="glass mt-14 rounded-2xl p-6 text-center">
      <BookCheck className="mx-auto mb-2 size-6 text-primary" />
      <h3 className="text-lg font-semibold">{done ? "Chapter complete" : "Finished the chapter?"}</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        {done ? "Nice. Come back to the questions at the end tomorrow, without looking, and see what stuck." : reachedEnd ? "Answer the questions above in your head (or on paper) first. Then mark it done." : "Scroll to the end of the chapter to unlock this."}
      </p>
      {gain && <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 text-sm font-medium text-primary">{gain}</motion.p>}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
      <div className="mt-5 flex justify-center gap-3">
        {!done && <Button onClick={finish} disabled={!reachedEnd || pending}>{pending && <Loader2 className="animate-spin" />} Mark chapter as read</Button>}
        <Button asChild variant="outline"><Link href="/">Back to today&apos;s mission <ArrowRight /></Link></Button>
      </div>
    </div>
  );
}
