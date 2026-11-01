/** Copy for the page. Components stay free of long text. */

export const repo = "https://github.com/sarang-cmd/HostTalk";
export const releases = `${repo}/releases/latest`;
export const issues = `${repo}/issues`;
export const license = `${repo}/blob/main/LICENSE`;
export const guide = `${repo}#readme`;
export const howItWorks = `${repo}#how-it-works`;
export const deployIt = `${repo}#deploy-it`;

export type Fact = { label: string; value: string };

export const facts: Fact[] = [
  { label: "Python", value: "3.10 or newer" },
  { label: "Storage", value: "SQLite" },
  { label: "Default port", value: "7284" },
  { label: "License", value: "Apache 2.0" },
  { label: "Internet needed", value: "No" },
];

/** The screenshots hold placeholder names, so the page says so. */
export const demoNote =
  "Screenshots come from a demo room. The names and messages are placeholders.";

export const heroCaption =
  "The room at laptop width. Rooms, quotes, reactions, an image attachment, and who is here.";

export type Feature = { title: string; body: string };

export const features: Feature[] = [
  {
    title: "One room, or several",
    body: "The main room holds everyone. Named rooms hold up to 20 people. Direct threads stay between two.",
  },
  {
    title: "Messages stay on the host",
    body: "Every message lands in a SQLite file on the machine that serves the room. No relay, no cloud copy, no analytics.",
  },
  {
    title: "Files up to 20 MB",
    body: "Images show in the thread. Other files download. The browser shrinks an oversized photo before upload.",
  },
  {
    title: "Quotes, reactions, edits",
    body: "Reply with a quote, add a reaction, edit or delete your own text. A deleted message leaves a quiet placeholder.",
  },
  {
    title: "A console for the host",
    body: "Checks, people, rooms, logs, settings, and a stop button, in a browser. The console answers on the host machine only by default.",
  },
  {
    title: "Files from phones",
    body: "LocalSend devices on the same network send files straight into the room. No cable, no cloud drive.",
  },
  {
    title: "Link previews, guarded",
    body: "The host fetches a page title and image when someone posts a link. Requests to private addresses are refused before any request leaves the machine.",
  },
  {
    title: "GIF search, when you add a key",
    body: "Search runs through the host, so the GIPHY key stays on the server. Search is off until a key is set in the console.",
  },
];

export type Step = { title: string; body: string };

export const steps: Step[] = [
  {
    title: "One host",
    body: "A laptop, desktop, or small server starts HostTalk. The app, the database, and uploaded files live on one disk.",
  },
  {
    title: "Same Wi-Fi",
    body: "A guest opens the address and enters a name plus the room password. The browser holds a signed session cookie.",
  },
  {
    title: "Stored here",
    body: "A message is written to the database and streamed to every open browser. No third-party service carries the text.",
  },
];

export type DeployRow = { name: string; note: string };

export const deployRows: DeployRow[] = [
  { name: "systemd", note: "Unit file and installer in deploy/." },
  { name: "launchd", note: "Plist for a login session on macOS." },
  { name: "Docker", note: "Image and compose file with a fixed data volume." },
  { name: "Windows", note: "Batch launcher for a desktop shortcut." },
  { name: "Proxy", note: "Caddy and nginx examples with the stream settings that matter." },
];

export type Limit = { title: string; body: string };

export const limits: Limit[] = [
  {
    title: "No accounts",
    body: "A name and a device key hold your place. Someone with the room password on a new device picks a name and joins. The host keeps a log of name changes.",
  },
  {
    title: "No end-to-end encryption",
    body: "Traffic is plain HTTP inside the local network. The machine hosting the room stores message text in SQLite and reads it. Run HostTalk on hardware you control.",
  },
  {
    title: "No relay across networks",
    body: "Guests outside the Wi-Fi need a VPN or a tunnel you set up. HostTalk does not offer one, and it does not reach the internet to deliver messages.",
  },
  {
    title: "No cloud backup",
    body: "Copy the data folder to back up messages and uploads. Clearing a room in the console deletes its messages for good.",
  },
  {
    title: "Third-party requests are explicit",
    body: "A GIF search sends the words to GIPHY. A link preview fetches the page from the host. Nothing else leaves the network unless you post a link.",
  },
];

export const installLines = [
  "python -m venv .venv",
  "source .venv/bin/activate",
  "pip install -r requirements.txt",
  "python server.py",
];

export const sectionCopy = {
  features: {
    title: "Room chat, with the parts a small group needs.",
    lede: "One server runs the rooms, the files, and the host console. There is no second service to install and no account to create.",
  },
  steps: {
    title: "Three steps, one machine.",
    lede: "The server serves the app, checks the room password, stores each message in SQLite, and pushes new messages to open browsers over one long-lived connection.",
  },
  run: {
    title: "Two commands on the host.",
    lede: "Python 3.10 or newer. No build step, no database server, no Node toolchain. The setup screen opens in a browser on the machine which runs the server.",
  },
  build: {
    title: "Every figure on the server is countable.",
    lede: "The app ships a stats page. It counts rows in the database, bytes in the data folder, lines of code in the build, and the versions under both. The page reads those figures on request and keeps no record of visitors.",
  },
  limits: {
    title: "What it does not do",
    lede: "These limits are part of the design. Knowing them makes the tool easier to trust.",
  },
  shots: {
    title: "On a phone and in the console",
    lede: "The room fits a phone without a separate app. The console gives the host one screen for checks, settings, logs, and people.",
  },
} as const;
