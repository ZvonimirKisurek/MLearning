"use client";

import { forwardRef, useCallback, useEffect, useRef, useState, useTransition } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, CloudOff, Download, Loader2, NotebookPen, X } from "lucide-react";
import { useReactToPrint } from "react-to-print";
import { saveNotesAction } from "@/app/actions";
import { useDebounce } from "@/lib/use-debounce";
import { cn } from "@/lib/utils";

type SaveState = "idle" | "dirty" | "saved" | "error";

/** What gets printed: a plain light-theme page (title, date, notes). Nothing else from the site is in this subtree. */
const PrintSheet = forwardRef<HTMLDivElement, { title: string; notes: string; date: string }>(function PrintSheet({ title, notes, date }, ref) {
  return (
    <div ref={ref} style={{ background: "#fff", color: "#111", padding: "32px", fontFamily: "Georgia, serif" }}>
      <p style={{ margin: 0, fontSize: 12, letterSpacing: "0.1em", textTransform: "uppercase", color: "#666" }}>My Notebook · <span suppressHydrationWarning>{date}</span></p>
      <h1 style={{ margin: "6px 0 18px", fontSize: 26, lineHeight: 1.2 }}>{title}</h1>
      <hr style={{ border: 0, borderTop: "1px solid #ccc", marginBottom: 18 }} />
      <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.65, overflowWrap: "anywhere" }}>{notes.trim() || "(no notes yet)"}</div>
    </div>
  );
});

/**
 * Floating "Notebook" button + slide-in drawer. Owns the notes state and the debounced auto-save.
 *
 * Auto-save: typing updates `notes` instantly (the textarea never waits on the network). `useDebounce(notes, 1000)` only
 * changes once typing has paused for a second; that change triggers ONE save. Saves are skipped when the text equals what
 * the server already has, and closing the drawer flushes any unsaved text immediately.
 */
export function NotebookDrawer({ taskId, chapterTitle, initialNotes }: { taskId: string; chapterTitle: string; initialNotes: string }) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState(initialNotes);
  const [state, setState] = useState<SaveState>("idle");
  const saved = useRef(initialNotes);       // the text the server is known to have
  const latest = useRef(initialNotes);      // the text currently in the box (readable from callbacks without stale closures)
  const debounced = useDebounce(notes, 1000);
  const printRef = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);

  const [saving, startSaving] = useTransition(); // isPending doubles as the "Saving…" flag while the request is in flight

  const save = useCallback((text: string) => {
    if (text === saved.current) return;
    startSaving(async () => {
      const res = await saveNotesAction(taskId, text);
      if (!res.ok) return setState("error");
      saved.current = text;
      // If the user kept typing while this request was in flight they are still "dirty"; the next debounce tick saves it.
      setState(latest.current === text ? "saved" : "dirty");
    });
  }, [taskId]);

  useEffect(() => { save(debounced); }, [debounced, save]);

  function onChange(v: string) {
    latest.current = v;
    setNotes(v);
    setState("dirty");
  }
  const close = useCallback(() => {
    setOpen(false);
    save(latest.current); // flush instead of waiting out the debounce
  }, [save]);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => area.current?.focus(), 350); // after the slide-in finishes, so focus doesn't fight the animation
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => { clearTimeout(t); window.removeEventListener("keydown", esc); };
  }, [open, close]);

  // Warn if the tab is closed while a save is pending.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (latest.current !== saved.current) e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  const print = useReactToPrint({
    contentRef: printRef,
    documentTitle: `${chapterTitle} - notes`,
    pageStyle: "@page { margin: 18mm; } body { -webkit-print-color-adjust: exact; }",
  });
  const today = new Intl.DateTimeFormat("en-US", { dateStyle: "long" }).format(new Date());

  return (
    <>
      {!open && (
        <motion.button initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.96 }}
          onClick={() => setOpen(true)} aria-label="Open notebook"
          className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground shadow-lg shadow-black/40">
          <NotebookPen className="size-4" /> Notebook
        </motion.button>
      )}

      <AnimatePresence>
        {open && (
          <motion.aside key="notebook" role="dialog" aria-label="My Notebook"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 36 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-white/10 bg-background/95 shadow-2xl shadow-black/60 backdrop-blur-xl sm:w-[420px] lg:w-[36vw]">
            <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
              <NotebookPen className="size-4 text-primary" />
              <h2 className="flex-1 text-base font-semibold tracking-tight">My Notebook</h2>
              <button onClick={() => print()} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground">
                <Download className="size-4" /> Download PDF
              </button>
              <button onClick={close} aria-label="Close notebook" className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"><X className="size-5" /></button>
            </header>
            <p className="truncate px-4 pt-3 text-xs text-muted-foreground">{chapterTitle}</p>
            <textarea ref={area} value={notes} onChange={(e) => onChange(e.target.value)} maxLength={50000} spellCheck
              placeholder="Jot down key ideas, questions, formulas to remember…"
              className="m-4 flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] p-4 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-primary/50 focus:ring-2 focus:ring-primary/20" />
            <footer className="flex items-center justify-between px-4 pb-4 text-xs text-muted-foreground" aria-live="polite">
              <span className={cn("inline-flex items-center gap-1.5", state === "error" && "text-destructive")}>
                {saving && <><Loader2 className="size-3 animate-spin" /> Saving…</>}
                {!saving && state === "saved" && <><Check className="size-3 text-primary" /> Saved</>}
                {!saving && state === "dirty" && "Unsaved changes…"}
                {state === "error" && <><CloudOff className="size-3" /> Couldn&apos;t save. Keep typing to retry.</>}
              </span>
              <span className="font-mono">{notes.length.toLocaleString("en-US")} / 50,000</span>
            </footer>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* react-to-print clones ONLY the inner ref'd node into a hidden iframe; this wrapper keeps it off-screen on the real page. */}
      <div className="hidden"><PrintSheet ref={printRef} title={chapterTitle} notes={notes} date={today} /></div>
    </>
  );
}
