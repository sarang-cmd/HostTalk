import { releases, repo } from "../content";
import { cx } from "../lib/cx";
import { Wordmark } from "./Wordmark";

type Link = { href: string; label: string; inPage?: boolean };

const links: Link[] = [
  { href: "#how", label: "How it works", inPage: true },
  { href: "#run", label: "Run it", inPage: true },
  { href: releases, label: "Releases" },
  { href: repo, label: "Source" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-[1120px] items-center justify-between gap-3 px-5 sm:px-8 lg:px-12">
        <a
          href="#top"
          className="shrink-0 text-[17px] font-semibold tracking-[-0.02em] text-ink no-underline"
          style={{ fontFamily: "var(--font-display)" }}
        >
          <Wordmark />
        </a>

        <nav aria-label="Site" className="flex min-w-0 items-center gap-3.5 sm:gap-6">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={cx(
                "text-sm whitespace-nowrap text-ink-2 no-underline transition-colors",
                "hover:text-ink hover:underline hover:underline-offset-4",
                // Below the small breakpoint the page keeps the two links
                // that leave it, the same rule the CSS build used.
                link.inPage && "hidden sm:inline",
              )}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
