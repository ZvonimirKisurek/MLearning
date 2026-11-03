"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

type NotebookState = {
  open: boolean;
  activeTaskId: string | null;
  activeChapterTitle: string;
  openNotebook: () => void;
  closeNotebook: () => void;
  setActiveChapterTitle: (t: string) => void;
  /** Internal: used by <NotebookRouteSync/>. */
  setActiveTaskId: (id: string | null) => void;
};

const Ctx = createContext<NotebookState | null>(null);

export function NotebookProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeChapterTitle, setActiveChapterTitle] = useState("");
  const openNotebook = useCallback(() => setOpen(true), []);
  const closeNotebook = useCallback(() => setOpen(false), []);
  const value = useMemo(
    () => ({ open, activeTaskId, activeChapterTitle, openNotebook, closeNotebook, setActiveChapterTitle, setActiveTaskId }),
    [open, activeTaskId, activeChapterTitle, openNotebook, closeNotebook],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNotebook() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNotebook must be used inside <NotebookProvider>");
  return v;
}

/**
 * Derives the active task from the URL (/read/<id> or /practice/<id>). Kept out of the provider on purpose: usePathname()
 * is request-time data, so only this tiny component (rendered inside <Suspense>) is dynamic, not the whole app tree.
 */
export function NotebookRouteSync() {
  const pathname = usePathname();
  const { setActiveTaskId, setActiveChapterTitle } = useNotebook();
  useEffect(() => {
    const m = pathname.match(/^\/(?:read|practice)\/([^/]+)/);
    const id = m ? decodeURIComponent(m[1]) : null;
    setActiveTaskId(id);
    if (!id) setActiveChapterTitle("");
  }, [pathname, setActiveTaskId, setActiveChapterTitle]);
  return null;
}
