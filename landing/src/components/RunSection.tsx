import { deployIt, deployRows, installLines } from "../content";

export function RunSection() {
  return (
    <div className="grid gap-10 lg:grid-cols-2 lg:gap-14">
      <div>
        <h3 className="text-2xs font-medium tracking-[0.02em] text-muted">From source</h3>
        <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-surface p-4">
          <code className="font-mono text-[13px] leading-[1.75] text-ink">
            {installLines.join("\n")}
          </code>
        </pre>
        <p className="mt-3 max-w-[52ch] text-xs leading-[1.6] text-muted">
          On Windows use{" "}
          <code className="font-mono text-[12px] text-ink-2">.venv\Scripts\activate</code>. The
          console then opens at{" "}
          <code className="font-mono text-[12px] text-ink-2">http://127.0.0.1:7284/console</code>.
        </p>
      </div>

      <div>
        <h3 className="text-2xs font-medium tracking-[0.02em] text-muted">Other ways to start</h3>
        <table className="mt-3 w-full border-collapse text-sm">
          <tbody>
            {deployRows.map((row) => (
              <tr key={row.name}>
                <th
                  scope="row"
                  className="w-24 border-b border-line py-2.5 pr-4 text-left font-medium whitespace-nowrap text-muted"
                >
                  {row.name}
                </th>
                <td className="border-b border-line py-2.5 text-ink-2">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs leading-[1.6] text-muted">
          Each option is documented in the{" "}
          <a href={deployIt} rel="noreferrer" className="text-ink-2 underline underline-offset-4">
            repository
          </a>
          .
        </p>
      </div>
    </div>
  );
}
