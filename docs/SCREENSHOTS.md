# Screenshot notes

Every screen image in `static/screenshots` comes from a running build. Nothing is a mockup.

Every image here comes from the 2.2 build. The room pictures show badges, profile
pictures, a room inside a room, the hover toolbar, and the KLIPY key field.
The social preview is a type card, not a screenshot. Its markup lives in
`docs/social-preview.html`.

## How the images were made

1. A fresh, empty data folder: `python -m hosttalk setup --password frontroom --room "Front room" --port 7284 --non-interactive`.
2. The server on `0.0.0.0:7284` with `--headless`.
3. Three people, three rooms, one custom emoji, two pictures, and a badge each, created through the public API. The script is `docs/seed-demo.js`, and it needs Node 18 or newer.
4. A headless Chromium at a 1440 by 900 viewport for desktop and 414 by 896 for phone, device scale 2.
5. One browser context per person, so each session cookie and device key stay separate. The device key is written to local storage before the page loads, and the person joins through the join form.
6. The address in the shots reads `http://192.168.1.24:7284/room`. A resolver rule in the capture browser points that address at the local server, so no real machine has to exist.
7. Fonts are awaited with `document.fonts.ready`, then the page settles for half a second before the shot.

## Where the demo pictures came from

Two profile pictures and one custom emoji are drawn for this set, not photographed.
Mara has a clay disc on a warm field. Jonas has a pale disc over two bands. The
custom emoji is a mug. Ada keeps her initials, so the fallback stays visible.

## Labels

The room text is demo copy. "Front room", "Kitchen plans", "Roof work", and the
three names are placeholders. The label image in the thread is a generated
placeholder, not a real design deliverable. Images do not show a real customer, a
real conversation, or a benchmark.

## Files

| File | What it shows |
| --- | --- |
| `landing.png`, `landing-full.png` | Front page at 1440 wide, viewport and full page |
| `landing-mobile.png` | Front page at phone width, full page |
| `join-desktop.png` | Join page at 1440 wide |
| `join-mobile.png` | Join page at 414 wide |
| `room-desktop.png` | The room with three people, a badge each, an image attachment, and the hover toolbar |
| `room-mobile.png` | The room at phone width |
| `room-mobile-people.png` | The people drawer on a phone |
| `room-dark.png` | Dark theme |
| `invite-dialog.png` | Invite sheet with the QR code |
| `settings-dialog.png` | Personal settings sheet, with the badge picker |
| `new-room-dialog.png` | New room sheet, with the parent room set |
| `search.png` | Search results |
| `stats.png`, `stats-full.png` | Project stats at 1440 wide, viewport and full page |
| `stats-mobile.png` | Project stats at phone width |
| `project-page.png` | The built project page at 1440 wide, full page |
| `console.png` | Host console at 1440 wide |
| `console-full.png` | Host console, full page |
| `console-mobile.png` | Host console at phone width |
| `console-login.png` | Console sign in |
| `about.png`, `about-full.png` | How it works page |
| `terms.png`, `privacy.png` | Draft legal pages |
| `not-found.png` | Error page |
| `demo-label.png` | The placeholder picture posted in the demo thread, kept because the seed script reads it |

`docs/social-preview.png` is separate. The table above covers the folder, and the
card sits in `docs`.

## Social preview

`docs/social-preview.png` is the card GitHub shows when someone shares the repository link. It is 1280 by 640, the size GitHub asks for, and it uses the same paper, ink, and type as the site.

The card is markup, not a drawing. `docs/social-preview.html` holds the layout and reads the fonts and the app window from `static/`, so a rebuild reads the same sources as the site. To capture it:

```bash
# Any headless browser works. Capture the card at 1280 by 640, device scale 2.
# Then scale the result down to 1280 by 640 and save over docs/social-preview.png.
```

Upload the PNG at Settings, General, Social preview. GitHub has no API for that setting, so the file stays in the repository and the upload is one manual step.

`tests/test_landing.py` reads the PNG header and checks the size.

## Rerunning

Use any Chromium with a remote debugging port. The capture scripts are local tools
and stay out of the repository. Recreate the demo data first, because names bind to
device keys and a second run with a fresh data folder starts clean.

A headless browser reports no fine pointer, so the layout rule `@media (hover: none)`
applies and the message toolbar sits in the row instead of floating. The capture
script restores the hover rule for the desktop shots, and the phone shots keep the
touch layout.
