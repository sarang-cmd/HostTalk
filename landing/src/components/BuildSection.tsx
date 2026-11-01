import { shots } from "../media";
import { Figure } from "./Figure";

export function BuildSection() {
  return (
    <Figure
      src={shots.statsShot}
      alt="The HostTalk stats page: instance figures, a code table with bars, build versions, and bundled libraries."
      width={1600}
      height={1000}
      caption="The stats page on a demo room. Message counts, file bytes, and test totals read from the running build."
    />
  );
}
