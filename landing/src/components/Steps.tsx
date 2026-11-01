import { steps } from "../content";
import { cx } from "../lib/cx";

export function Steps() {
  return (
    <ol className="grid border-t border-line sm:grid-cols-3">
      {steps.map((step, position) => (
        <li
          key={step.title}
          className={cx(
            "border-b border-line py-5 sm:border-b-0 sm:py-6 sm:pr-6",
            position > 0 && "sm:border-l sm:border-line sm:pl-6",
          )}
        >
          <h3 className="text-sm text-ink">{step.title}</h3>
          <p className="mt-1.5 max-w-[38ch] text-sm leading-[1.55] text-muted">{step.body}</p>
        </li>
      ))}
    </ol>
  );
}
