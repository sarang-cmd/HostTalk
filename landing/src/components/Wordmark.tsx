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
        <path d="M9.4 20 L9.4 26.8 L15.5 20.4 Z" className="fill-paper" />
        <rect x="6.3" y="11.1" width="19.5" height="10.9" rx="3.1" className="fill-paper" />
        <circle cx="25.4" cy="25.3" r="2.4" className="fill-accent" />
      </svg>
      <span>HostTalk</span>
    </span>
  );
}
