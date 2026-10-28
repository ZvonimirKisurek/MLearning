"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

/** A code block with a language label and a copy button. `text` is the raw source (the children are the highlighted markup). */
export function CodeBlock({ lang, text, children }: { lang?: string; text: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable (insecure context): the text is still selectable */
    }
  }
  return (
    <div className="code-block not-prose my-1">
      <div className="flex items-center justify-between border-b border-white/[0.07] bg-white/[0.03] px-3.5 py-1.5">
        <span className="eyebrow !text-[10px]">{lang || "text"}</span>
        <button onClick={copy} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground" aria-label="Copy code">
          {copied ? <Check className="size-3.5 text-primary" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {children}
    </div>
  );
}
