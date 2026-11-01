import { cx } from "../lib/cx";

type Props = {
  className?: string;
};

/** The mark and the word, as one link target. */
export function Wordmark({ className }: Props) {
  return (
    <span className={cx("inline-flex items-center gap-2.5 whitespace-nowrap", className)}>
      <svg
        className="size-[26px] shrink-0"
        viewBox="0 0 32 32"
        aria-hidden="true"
        focusable="false"
      >
        <rect width="32" height="32" rx="9" className="fill-ink" />
        <rect x="9" y="14" width="14" height="9" rx="1.5" className="fill-paper" />
        <circle cx="22" cy="10" r="2.4" className="fill-accent" />
      </svg>
      <span>HostTalk</span>
    </span>
  );
}
