import { shots } from "../media";
import { Figure } from "./Figure";

export function Shots() {
  return (
    <div className="grid gap-10 sm:grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)] sm:items-start sm:gap-8">
      <Figure
        src={shots.roomMobile}
        alt="The HostTalk room at phone width, with the message composer along the bottom edge."
        width={430}
        height={932}
        className="max-w-[360px]"
        caption="Phone width. Drawers hold the room list and people."
      />
      <Figure
        src={shots.consoleShot}
        alt="The HostTalk host console: checks, people, rooms, logs, and server settings."
        width={1440}
        height={900}
        caption="The host console. Configuration, logs, and moderation on one screen."
      />
    </div>
  );
}
