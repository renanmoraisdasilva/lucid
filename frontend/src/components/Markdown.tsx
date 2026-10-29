import { Children, isValidElement, useState, type ReactElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

function textOf(children: ReactNode): string {
  if (typeof children === "string") {
    return children;
  }
  if (typeof children === "number") {
    return String(children);
  }
  if (Array.isArray(children)) {
    return children.map(textOf).join("");
  }
  if (isValidElement<{ children?: ReactNode }>(children)) {
    return textOf(children.props.children);
  }
  return "";
}

interface CodeBlockProps {
  language: string;
  code: string;
  children: ReactNode;
}

function CodeBlock({ language, code, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard access can be denied; the copy affordance simply does nothing.
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-surface-border bg-surface-code shadow-md">
      <div className="flex h-9 items-center justify-between border-b border-surface-border bg-surface-elevated/70 px-4">
        <span className="font-mono text-[12px] text-text-muted">{language}</span>
        <button
          type="button"
          onClick={() => void copy()}
          aria-label={`Copy ${language} code`}
          className="flex items-center gap-1.5 text-[12px] text-text-secondary transition-colors hover:text-text-primary"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed">{children}</pre>
    </div>
  );
}

const ALLOWED_PROTOCOLS = ["http", "https", "mailto"];

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown text-[15px] leading-relaxed text-text-primary">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize, rehypeHighlight]}
        components={{
          pre({ children }) {
            const first = Children.toArray(children)[0];
            if (!isValidElement<{ className?: string; children?: ReactNode }>(first)) {
              return <pre>{children}</pre>;
            }
            const className = first.props.className ?? "";
            const language = /language-([\w-]+)/.exec(className)?.[1] ?? "text";
            const code = textOf(first.props.children);
            return (
              <CodeBlock language={language} code={code}>
                {first}
              </CodeBlock>
            );
          },
          a({ href, children }) {
            const safe =
              href !== undefined &&
              ALLOWED_PROTOCOLS.some((protocol) => href.startsWith(`${protocol}:`));
            if (!safe) {
              return <span>{children}</span>;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export type { ReactElement };
