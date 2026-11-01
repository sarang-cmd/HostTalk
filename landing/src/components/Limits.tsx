import { limits } from "../content";

export function Limits() {
  return (
    <dl className="border-t border-line">
      {limits.map((limit) => (
        <div
          key={limit.title}
          className="grid gap-1.5 border-b border-line py-4 sm:grid-cols-[minmax(0,0.36fr)_minmax(0,0.64fr)] sm:gap-6 sm:py-5"
        >
          <dt className="text-sm font-medium text-ink">{limit.title}</dt>
          <dd className="m-0 max-w-[62ch] text-sm leading-[1.6] text-muted">{limit.body}</dd>
        </div>
      ))}
    </dl>
  );
}
