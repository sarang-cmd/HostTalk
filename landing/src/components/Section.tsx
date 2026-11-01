import type { ReactNode } from "react";
import { cx } from "../lib/cx";

type Props = {
  id: string;
  title: string;
  lede: string;
  children?: ReactNode;
  /** Small closing note, set below the section body. */
  fineprint?: ReactNode;
};

/**
 * One part of the manual. A hairline opens the section, and a continuous rule
 * runs down the left margin on wide screens, with a node on each opening
 * line. One line, several rooms.
 */
export function Section({ id, title, lede, children, fineprint }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-16 border-t border-line">
      <div className="relative mx-auto max-w-[1120px] px-5 pt-14 pb-14 sm:px-8 sm:pt-20 sm:pb-20 lg:px-12 lg:pt-24 lg:pb-24">
        <span
          aria-hidden="true"
          className="absolute inset-y-0 left-5 hidden w-px bg-line sm:left-8 lg:left-12 lg:block"
        />
        <span
          aria-hidden="true"
          className="absolute top-[6.35rem] left-[45px] hidden size-[7px] rounded-full border border-line-strong bg-paper lg:block"
        />

        <div className="lg:pl-12">
          <div className="grid gap-x-14 gap-y-5 lg:grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)]">
            <h2 id={`${id}-title`} className="max-w-[17ch] text-h2 leading-[1.04]">
              {title}
            </h2>
            <p className="max-w-[58ch] text-lede leading-[1.55] text-ink-2 lg:pt-6">{lede}</p>
          </div>

          {children ? <div className="mt-10 lg:mt-12">{children}</div> : null}
          {fineprint ? (
            <p className={cx("max-w-[62ch] text-xs leading-[1.6] text-muted", "mt-6")}>
              {fineprint}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
