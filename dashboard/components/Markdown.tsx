"use client";

// Findings come back from the model as GitHub-flavoured markdown. This renders
// it with the dashboard's own type scale (no typography plugin), and lets the
// reader flip to the raw source — useful when pasting a finding elsewhere.

import { Check, Code2, Copy, Eye } from "lucide-react";
import { useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "./ui";

export function CodeBlock({ text }: { text: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-line bg-obsidian px-3.5 py-3 font-mono text-[12px] leading-relaxed text-muted">
      <code>{text}</code>
    </pre>
  );
}

/** Markdown body with a rendered/source toggle and a copy button.
    `actions` slots caller-supplied controls in beside the copy button. */
export function Markdown({ text, actions }: { text: string; actions?: ReactNode }) {
  const [source, setSource] = useState(false);

  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-center justify-end gap-1">
        <IconButton
          label={source ? "Show rendered" : "Show markdown"}
          onClick={() => setSource((s) => !s)}
        >
          {source ? (
            <Eye className="h-3.5 w-3.5" strokeWidth={2} />
          ) : (
            <Code2 className="h-3.5 w-3.5" strokeWidth={2} />
          )}
        </IconButton>
        <CopyButton text={text} />
        {actions}
      </div>

      {source ? (
        <CodeBlock text={text} />
      ) : (
        <div className="space-y-2.5 text-[13px] leading-relaxed text-muted">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
            {text}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <IconButton
      label={copied ? "Copied" : "Copy markdown"}
      onClick={() => {
        copy(text).then((ok) => {
          if (!ok) return;
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-signal" strokeWidth={2} />
      ) : (
        <Copy className="h-3.5 w-3.5" strokeWidth={2} />
      )}
    </IconButton>
  );
}

/** The async clipboard needs a secure context; the dashboard is often served
    over plain HTTP, so fall back to the legacy selection copy. */
async function copy(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard) throw new Error("no clipboard api");
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    el.remove();
    return ok;
  }
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="rounded-md border border-line bg-ink p-1.5 text-faint transition-colors hover:border-cyan/40 hover:text-fg"
    >
      {children}
    </button>
  );
}

/* Element map — the dashboard has no typography plugin, so every tag that can
   show up in a finding is styled explicitly. */
const heading = (size: string) =>
  function Heading({ children }: { children?: ReactNode }) {
    return (
      <p className={cn("mt-3 font-display font-semibold text-fg first:mt-0", size)}>
        {children}
      </p>
    );
  };

const MD: Components = {
  h1: heading("text-[15px]"),
  h2: heading("text-[14px]"),
  h3: heading("text-[13px]"),
  h4: heading("text-[13px]"),
  h5: heading("text-[13px]"),
  h6: heading("text-[13px]"),
  p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => (
    <ul className="list-disc space-y-1 pl-5 marker:text-faint">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal space-y-1 pl-5 marker:text-faint">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-cyan underline decoration-cyan/30 underline-offset-2 hover:decoration-cyan"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-line pl-3 text-faint">{children}</blockquote>
  ),
  hr: () => <hr className="border-line" />,
  // react-markdown routes fenced blocks through <pre><code>; the inline case
  // is any <code> that isn't wrapped in a <pre>.
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const body = String(children ?? "").replace(/\n$/, "");
    if (className?.startsWith("language-") || body.includes("\n")) {
      return <CodeBlock text={body} />;
    }
    return (
      <code className="rounded border border-line bg-obsidian px-1 py-0.5 font-mono text-[12px] text-fg">
        {body}
      </code>
    );
  },
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-line px-2 py-1 text-left font-display font-semibold text-fg">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border border-line px-2 py-1 align-top">{children}</td>,
};
