import type { ReactNode } from "react";
import { cx } from "../lib/cx";

type Props = {
  href: string;
  children: ReactNode;
  tone?: "primary" | "secondary";
  external?: boolean;
  className?: string;
};

/** A link styled as a button. Buttons here always navigate, so it is an anchor. */
export function ActionLink({ href, children, tone = "secondary", external, className }: Props) {
  return (
    <a
      href={href}
      {...(external ? { rel: "noreferrer" } : {})}
      className={cx(
        "inline-flex h-10 items-center justify-center rounded-lg border px-4 text-sm font-medium no-underline transition-colors",
        tone === "primary"
          ? "border-accent bg-accent text-white hover:border-accent-ink hover:bg-accent-ink"
          : "border-line-strong bg-surface text-ink hover:bg-surface-2",
        className,
      )}
    >
      {children}
    </a>
  );
}
