import { Analytics } from "@vercel/analytics/react";
import { BuildSection } from "./components/BuildSection";
import { Features } from "./components/Features";
import { Hero } from "./components/Hero";
import { Limits } from "./components/Limits";
import { RunSection } from "./components/RunSection";
import { Section } from "./components/Section";
import { Shots } from "./components/Shots";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { Steps } from "./components/Steps";
import { howItWorks, sectionCopy } from "./content";

const noteLink =
  "text-ink-2 underline underline-offset-4 transition-colors hover:text-ink";

export function App() {
  return (
    <div id="top">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-4 focus:py-2 focus:text-sm focus:text-paper"
      >
        Skip to content
      </a>

      <SiteHeader />

      <main id="main">
        <Hero />

        <Section id="what" {...sectionCopy.features}>
          <Features />
        </Section>

        <Section
          id="how"
          {...sectionCopy.steps}
          fineprint={
            <>
              The{" "}
              <a href={howItWorks} rel="noreferrer" className={noteLink}>
                repository notes
              </a>{" "}
              cover the request path, the schema, the session model, and the file guard in more
              detail.
            </>
          }
        >
          <Steps />
        </Section>

        <Section id="run" {...sectionCopy.run}>
          <RunSection />
        </Section>

        <Section
          id="stats"
          {...sectionCopy.build}
          fineprint="No message text, names, or addresses appear on the page. Nothing is sent anywhere."
        >
          <BuildSection />
        </Section>

        <Section id="limits" {...sectionCopy.limits}>
          <Limits />
        </Section>

        <Section id="screens" {...sectionCopy.shots}>
          <Shots />
        </Section>
      </main>

      <SiteFooter />
      <Analytics />
    </div>
  );
}
