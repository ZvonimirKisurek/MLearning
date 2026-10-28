import { isValidElement, type ReactElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { slugify } from "@/lib/slug";
import { cn } from "@/lib/utils";
import { CodeBlock } from "./code-block";

/**
 * Renders LLM-written markdown safely and beautifully. This component is isomorphic (no "use client"): chapters render
 * on the server (zero markdown JS shipped for them) while the grader's feedback renders inside a client component.
 *
 * Safety: react-markdown does NOT render raw HTML (we add no rehype-raw), images are dropped (no tracking pixels), links
 * are limited to http(s)/mailto and always open in a new tab with rel=noopener. The content is also constrained upstream
 * (the backend rejects URLs and unknown citations), so this is defence in depth.
 */
export function normalizeMath(src: string): string {
  // Models sometimes emit \( \) and \[ \] despite instructions; remark-math wants $ and $$.
  return src.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`).replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`);
}

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

function Pre({ children }: { children?: ReactNode }) {
  const code = isValidElement(children) ? (children as ReactElement<{ className?: string; children?: ReactNode }>) : null;
  const lang = /language-([\w+-]+)/.exec(code?.props.className ?? "")?.[1];
  return (
    <CodeBlock lang={lang} text={textOf(code?.props.children ?? children).replace(/\n$/, "")}>
      <pre>{children}</pre>
    </CodeBlock>
  );
}

function SafeLink({ href, children }: { href?: string; children?: ReactNode }) {
  if (!href || !/^(https?:|mailto:)/i.test(href)) return <span>{children}</span>;
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

const heading = (Tag: "h2" | "h3") =>
  function Heading({ children }: { children?: ReactNode }) {
    return <Tag id={slugify(textOf(children))}>{children}</Tag>;
  };

export function Markdown({ children, className, compact = false }: { children: string; className?: string; compact?: boolean }) {
  return (
    <div className={cn("prose-book", compact && "prose-sm-book", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }], [rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={{ pre: Pre, a: SafeLink, img: () => null, h2: heading("h2"), h3: heading("h3") }}
      >
        {normalizeMath(children)}
      </ReactMarkdown>
    </div>
  );
}
