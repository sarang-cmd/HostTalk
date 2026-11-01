import { issues, license, releases, repo } from "../content";

const links = [
  { href: repo, label: "Source" },
  { href: releases, label: "Releases" },
  { href: issues, label: "Issues" },
  { href: license, label: "License" },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-5 py-8 text-xs text-muted sm:px-8 lg:px-12">
        <p>HostTalk, Apache 2.0. Made for one building at a time.</p>
        <nav aria-label="Project" className="flex flex-wrap gap-x-5 gap-y-2">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              rel="noreferrer"
              className="text-muted no-underline transition-colors hover:text-ink hover:underline hover:underline-offset-4"
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
