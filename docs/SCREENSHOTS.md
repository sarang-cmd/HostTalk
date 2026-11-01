# Screenshot notes

Every image in `static/screenshots` comes from a running build. Nothing is a mockup.

## How the images were made

1. A scratch data folder: `python -m hosttalk setup --data-dir /tmp/htdata --password frontroom --room "Front room" --port 7284`.
2. The server on `127.0.0.1:7284` with `--headless`.
3. Three seeded people plus one room and one direct thread, created through the public API. Seed script: the script in `docs/seed-demo.js`.
4. Chromium at a 1440 by 900 viewport for desktop and 430 by 932 for phone, device scale 2.
5. One browser process per person, so each session cookie and device key stay separate. People join through the join form, with `hosttalk.device` set to the seeded key before the page loads.
6. The stats page is captured after the seeded people join, so the online count shows a live room.
7. Fonts are awaited with `document.fonts.ready`, then the page settles for a second before the shot.

## Labels

The room text is demo copy. "Front room", "Kitchen plans", and the three names are placeholders. The label image in the thread is a generated placeholder, not a real design deliverable. Images do not show a real customer, a real conversation, or a benchmark.

## Files

| File | What it shows |
| --- | --- |
| `landing.png`, `landing-full.png` | Front page at 1440 wide, viewport and full page |
| `landing-mobile.png` | Front page at phone width |
| `join-desktop.png` | Join page at 1440 wide |
| `join-mobile.png` | Join page at 414 wide |
| `room-desktop.png` | The room with three people and an image attachment |
| `room-mobile.png` | The room at phone width |
| `room-mobile-people.png` | The people drawer on a phone |
| `room-dark.png` | Dark theme |
| `invite-dialog.png` | Invite sheet with the QR code |
| `settings-dialog.png` | Personal settings sheet |
| `new-room-dialog.png` | New room sheet |
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

## Front page and room path

The front page moved to `/` and the room to `/room` after the first pass of images. The screenshots above were captured after the move, so addresses read `http://192.168.x.x:7284/room`. A few dialog images from the earlier set still show the bare address without the path. The room itself is unchanged.

## Rerunning

Use any Chromium with a remote debugging port. The capture scripts are local tools and stay out of the repository. Recreate the demo data first, because names bind to device keys and a second run with a fresh data folder starts clean.
