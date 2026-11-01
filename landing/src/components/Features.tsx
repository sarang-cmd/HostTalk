import { features } from "../content";
import { cx } from "../lib/cx";

export function Features() {
  return (
    <ul className="grid border-t border-line sm:grid-cols-2">
      {features.map((feature, position) => (
        <li
          key={feature.title}
          className={cx(
            "border-b border-line py-5 sm:py-6",
            position % 2 === 0 ? "sm:pr-8" : "sm:border-l sm:border-line sm:pl-8",
          )}
        >
          <h3 className="text-sm text-ink">{feature.title}</h3>
          <p className="mt-1.5 max-w-[46ch] text-sm leading-[1.55] text-muted">{feature.body}</p>
        </li>
      ))}
    </ul>
  );
}
