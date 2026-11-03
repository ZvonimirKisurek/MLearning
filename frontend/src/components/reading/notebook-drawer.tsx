"use client";

import { forwardRef, useCallback, useEffect, useRef, useState, useTransition } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, CloudOff, Download, Loader2, NotebookPen, X } from "lucide-react";
import { useReactToPrint } from "react-to-print";
import { loadNotebookAction, saveNotesAction } from "@/app/actions";
import { useDebounce } from "@/lib/use-debounce";
import { cn } from "@/lib/utils";

type SaveState = "idle" | "dirty" | "saved" | "error";

/** What gets printed: a plain light-theme page (title, date, notes). Nothing else from the site is in this subtree. */
const PrintSheet = forwardRef<HTMLDivElement, { title: string; notes: string }>(function PrintSheet({ title, notes }, ref) {
  // Only ever rendered while the drawer is open (client-side), so reading the clock here never runs during prerender.
  const date = new Intl.DateTimeFormat("en-US", { dateStyle: "long" }).format(new Date());
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
export function NotebookDrawer({ taskId, open, onClose, onTitle }: { taskId: string | null; open: boolean; onClose: () => void; onTitle?: (t: string) => void }) {
  const [chapterTitle, setChapterTitle] = useState("");
  const [loaded, setLoaded] = useState<"idle" | "ready" | "error">("idle");
  const [notes, setNotes] = useState("");
  const [state, setState] = useState<SaveState>("idle");
  const fetching = useRef(false);
  const saved = useRef("");       // the text the server is known to have
  const latest = useRef("");      // the text currently in the box (readable from callbacks without stale closures)
  const debounced = useDebounce(notes, 1000);
  const printRef = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);

  const [saving, startSaving] = useTransition(); // isPending doubles as the "Saving…" flag while the request is in flight

  // Fetch this task's title + notes the first time the drawer opens for it (the host remounts us per task via `key`).
  useEffect(() => {
    if (!open || !taskId || loaded !== "idle" || fetching.current) return;
    fetching.current = true;
    loadNotebookAction(taskId).then((r) => {
      fetching.current = false;
      if (!r.ok) return setLoaded("error");
      saved.current = latest.current = r.data.notes;
      setNotes(r.data.notes);
      setChapterTitle(r.data.title);
      onTitle?.(r.data.title);
      setLoaded("ready");
    });
  }, [open, taskId, loaded, onTitle]);

  const save = useCallback((text: string) => {
    if (!taskId || loaded !== "ready" || text === saved.current) return;
    startSaving(async () => {
      const res = await saveNotesAction(taskId, text);
      if (!res.ok) return setState("error");
      saved.current = text;
      // If the user kept typing while this request was in flight they are still "dirty"; the next debounce tick saves it.
      setState(latest.current === text ? "saved" : "dirty");
    });
  }, [taskId, loaded]);

  useEffect(() => { save(debounced); }, [debounced, save]);

  function onChange(v: string) {
    latest.current = v;
    setNotes(v);
    setState("dirty");
  }
  const close = useCallback(() => {
    onClose();
    setLoaded((l) => (l === "error" ? "idle" : l)); // let a failed load retry on next open
    save(latest.current); // flush instead of waiting out the debounce
  }, [save, onClose]);

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

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.aside key="notebook" role="dialog" aria-label="My Notebook"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 36 }}
            className="fixed inset-y-0 right-0 z-[10000] flex w-full flex-col border-l border-white/10 bg-background/95 shadow-2xl shadow-black/60 backdrop-blur-xl sm:w-[420px] lg:w-[36vw]">
            <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
              <NotebookPen className="size-4 text-primary" />
              <h2 className="flex-1 text-base font-semibold tracking-tight">My Notebook</h2>
              <button onClick={() => print()} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground">
                <Download className="size-4" /> Download PDF
              </button>
              <button onClick={close} aria-label="Close notebook" className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"><X className="size-5" /></button>
            </header>
            <p className="truncate px-4 pt-3 text-xs text-muted-foreground">{!taskId ? "No chapter selected" : chapterTitle || "Loading…"}</p>
            {!taskId && <p className="m-4 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">Open a chapter or a hands-on lab, then reopen the notebook to take notes on it.</p>}
            {taskId && loaded === "error" && <p className="m-4 text-sm text-destructive">Couldn&apos;t load your notes. Close and reopen to retry.</p>}
            {taskId && loaded !== "error" && (
            <textarea ref={area} value={notes} onChange={(e) => onChange(e.target.value)} maxLength={50000} spellCheck disabled={loaded !== "ready"}
              placeholder="Jot down key ideas, questions, formulas to remember…"
              className="m-4 flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] p-4 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-primary/50 focus:ring-2 focus:ring-primary/20 disabled:opacity-50" />
            )}
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
      {open && <div className="hidden"><PrintSheet ref={printRef} title={chapterTitle} notes={notes} /></div>}
    </>
  );
}
