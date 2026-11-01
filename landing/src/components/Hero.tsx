import { demoNote, facts, guide, heroCaption, releases } from "../content";
import { shots } from "../media";
import { ActionLink } from "./ActionLink";
import { Figure } from "./Figure";

export function Hero() {
  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto max-w-[1120px] px-5 pt-14 pb-12 sm:px-8 sm:pt-20 lg:px-12 lg:pt-24 lg:pb-16"
    >
      <div className="grid gap-x-16 gap-y-12 lg:grid-cols-[minmax(0,1.32fr)_minmax(300px,0.68fr)] lg:items-start">
        <div>
          <h1 id="hero-title" className="max-w-[13ch] text-display leading-[0.95]">
            A room for the people on your network.
          </h1>
          <p className="mt-6 max-w-[44ch] text-lede leading-[1.55] text-ink-2 sm:text-xl">
            HostTalk runs on one machine in the building. Everyone on the same Wi-Fi opens a
            browser, picks a name, and joins. Messages, files, and logs stay on the host.
          </p>
          <div className="mt-7 flex flex-wrap gap-2.5">
            <ActionLink href={releases} tone="primary" external>
              Get the release
            </ActionLink>
            <ActionLink href={guide} external>
              Read the guide
            </ActionLink>
          </div>
          <p className="mt-7 flex items-start gap-2.5 text-sm leading-[1.5] text-ink-2">
            <span
              className="mt-[0.45em] size-[7px] shrink-0 rounded-full bg-live"
              aria-hidden="true"
            />
            Free to run. Apache 2.0. No account, no server bill.
          </p>
        </div>

        <aside aria-label="At a glance" className="lg:pt-1">
          <dl className="border-t border-line">
            {facts.map((fact) => (
              <div
                key={fact.label}
                className="flex items-baseline justify-between gap-6 border-b border-line py-2.5 text-sm"
              >
                <dt className="text-muted">{fact.label}</dt>
                <dd className="text-right font-medium tabular-nums text-ink">{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-6 max-w-[34ch] text-xs leading-[1.6] text-muted">{demoNote}</p>
        </aside>
      </div>

      <Figure
        src={shots.roomDesktop}
        alt="The HostTalk room on a laptop: rooms on the left, a message thread in the middle, people on the right."
        width={1600}
        height={1000}
        priority
        className="mt-14 lg:mt-16"
        caption={heroCaption}
      />
    </section>
  );
}
