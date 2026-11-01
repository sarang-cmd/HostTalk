"""HostTalk entry point.

Kept at the repository root so the PyInstaller builds keep working.
Run ``python server.py`` or ``python server.py --port 8080``.
"""

from hosttalk.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
