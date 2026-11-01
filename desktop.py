"""HostTalk desktop entry point.

Double-click builds run this file. It starts the server, opens the room in an
app window, and keeps a small control window on screen.
"""

from hosttalk.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
