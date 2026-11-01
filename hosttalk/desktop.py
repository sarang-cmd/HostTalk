"""Desktop shell: the server, a control window, and an app-style browser window."""

from __future__ import annotations

import argparse
import contextlib
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .app import create_app
from .config import Config
from .netinfo import lan_ip, wifi_name
from .services import build_services
from .version import CODENAME, __version__

APP_NAME = "HostTalk"
PORT_RANGE = 8


class Runner:
    """One HTTP server that the window can stop."""

    def __init__(self, config: Config):
        self.config = config
        self.services = build_services(config, start_localsend=bool(config.localsend.get("enabled")))
        self.app = create_app(self.services)
        self.server = None
        self.thread: threading.Thread | None = None
        self.port = config.port
        self.error = ""

    def start(self) -> bool:
        try:
            import waitress  # type: ignore
        except ImportError:
            return self._start_werkzeug()
        for offset in range(PORT_RANGE):
            port = self.config.port + offset
            try:
                self.server = waitress.create_server(
                    self.app,
                    host=self.config.bind,
                    port=port,
                    threads=32,
                    ident=APP_NAME,
                    clear_untrusted_proxy_headers=True,
                )
            except OSError:
                continue
            self.port = port
            self.thread = threading.Thread(target=self.server.run, name="hosttalk-http", daemon=True)
            self.thread.start()
            return True
        self.error = f"No free port between {self.config.port} and {self.config.port + PORT_RANGE - 1}"
        return False

    def _start_werkzeug(self) -> bool:
        from werkzeug.serving import make_server

        for offset in range(PORT_RANGE):
            port = self.config.port + offset
            try:
                self.server = make_server(self.config.bind, port, self.app, threaded=True)
            except OSError:
                continue
            self.port = port
            self.thread = threading.Thread(
                target=self.server.serve_forever, name="hosttalk-http", daemon=True
            )
            self.thread.start()
            return True
        self.error = "No free port near the one in the settings"
        return False

    def stop(self) -> None:
        server = self.server
        if server is None:
            return
        try:
            if hasattr(server, "close"):
                threading.Thread(target=server.close, daemon=True).start()
            elif hasattr(server, "shutdown"):
                server.shutdown()
        except Exception:
            pass
        self.services.localsend.stop()

    @property
    def local_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    @property
    def network_url(self) -> str:
        return f"http://{lan_ip()}:{self.port}/room"

    @property
    def console_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/console"


def _browser_command(url: str) -> list[str] | None:
    """A Chromium-family browser opens the room without tabs or an address bar."""
    system = platform.system()
    candidates: list[str] = []
    if system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        relatives = [
            ("Google", "Chrome", "Application", "chrome.exe"),
            ("Microsoft", "Edge", "Application", "msedge.exe"),
            ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ("Chromium", "Application", "chrome.exe"),
        ]
        for root in filter(None, roots):
            for parts in relatives:
                candidates.append(os.path.join(root, *parts))
    elif system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
            "brave-browser",
        ):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    for path in candidates:
        if Path(path).exists() or shutil.which(path):
            return [path, f"--app={url}", "--window-size=1180,820"]
    return None


def open_room(url: str) -> None:
    command = _browser_command(url)
    if command:
        try:
            subprocess.Popen(command, close_fds=True)
            return
        except OSError:
            pass
    with contextlib.suppress(Exception):
        webbrowser.open(url)


def _controller(runner: Runner) -> int:
    """A small window with the address, the buttons, and a live count."""
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("460x330")
    root.resizable(False, False)
    root.configure(bg="#f1f0eb")

    families = {name.lower(): name for name in tkfont.families(root)}

    def pick(*names: str) -> str:
        for name in names:
            if name.lower() in families:
                return families[name.lower()]
        return "TkDefaultFont"

    display = pick("Archivo", "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Arial")
    body = pick("Public Sans", "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Arial")

    wrap = tk.Frame(root, bg="#f1f0eb", padx=26, pady=22)
    wrap.pack(fill="both", expand=True)

    tk.Label(
        wrap, text=APP_NAME, font=(display, 20, "bold"), bg="#f1f0eb", fg="#171a18", anchor="w"
    ).pack(fill="x")
    tk.Label(
        wrap,
        text=f"{__version__} {CODENAME} · {runner.config.room_name}",
        font=(body, 10),
        bg="#f1f0eb",
        fg="#6a706a",
        anchor="w",
    ).pack(fill="x", pady=(2, 14))

    def address_row(label: str, value: str) -> tk.Entry:
        tk.Label(wrap, text=label, font=(body, 9), bg="#f1f0eb", fg="#6a706a", anchor="w").pack(
            fill="x"
        )
        entry = tk.Entry(
            wrap,
            font=(body, 11),
            bg="#faf9f6",
            fg="#171a18",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#d6d4ca",
        )
        entry.insert(0, value)
        entry.configure(state="readonly", readonlybackground="#faf9f6")
        entry.pack(fill="x", ipady=5, pady=(2, 10))
        return entry

    address_row("This machine", runner.local_url)
    address_row("Everyone on this network", runner.network_url)

    buttons = tk.Frame(wrap, bg="#f1f0eb")
    buttons.pack(fill="x", pady=(2, 12))

    def make_button(text: str, command, primary: bool = False) -> tk.Button:
        return tk.Button(
            buttons,
            text=text,
            command=command,
            font=(body, 10),
            relief="flat",
            bg="#1d3fa8" if primary else "#e9e7e0",
            fg="#ffffff" if primary else "#171a18",
            activebackground="#16307f" if primary else "#e0ded6",
            activeforeground="#ffffff" if primary else "#171a18",
            padx=12,
            pady=6,
            cursor="hand2",
            borderwidth=0,
        )

    def copy_network() -> None:
        root.clipboard_clear()
        root.clipboard_append(runner.network_url)
        status.configure(text="Network address copied.")

    make_button("Open room", lambda: open_room(runner.local_url), primary=True).pack(
        side="left", padx=(0, 6)
    )
    make_button("Host console", lambda: open_room(runner.console_url)).pack(side="left", padx=6)
    make_button("Copy address", copy_network).pack(side="left", padx=6)

    status = tk.Label(
        wrap,
        text="Listening. Keep this window open while the room is in use.",
        font=(body, 9),
        bg="#f1f0eb",
        fg="#6a706a",
        anchor="w",
    )
    status.pack(fill="x", pady=(4, 0))

    footer = tk.Label(
        wrap,
        text="",
        font=(body, 9),
        bg="#f1f0eb",
        fg="#6a706a",
        anchor="w",
    )
    footer.pack(fill="x", pady=(2, 0))

    def tick() -> None:
        try:
            here = runner.services.presence.count()
            people = "nobody here" if here == 0 else f"{here} here"
            wifi = wifi_name()
            footer.configure(text=f"{people} · port {runner.port}" + (f" · {wifi}" if wifi else ""))
        except Exception:
            pass
        root.after(2000, tick)

    def quit_app() -> None:
        if not messagebox.askokcancel(APP_NAME, "Stop the room and close HostTalk?"):
            return
        status.configure(text="Stopping.")
        root.update_idletasks()
        runner.stop()
        root.after(150, root.destroy)

    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.bind("<Escape>", lambda event: quit_app())
    if not runner.config.setup_complete:
        status.configure(text="No password yet. Open the host console and finish setup.")
    tick()
    root.mainloop()
    return 0


def _wait_forever(runner: Runner) -> int:
    if sys.stdout:
        print(f"HostTalk {__version__} on {runner.local_url}")
        print(f"Network: {runner.network_url}")
        print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        runner.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosttalk app", add_help=True)
    parser.add_argument("-p", "--port", type=int, default=None)
    parser.add_argument("--host", "--bind", dest="bind", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-window", action="store_true", help="Run without the control window")
    args = parser.parse_args(argv)

    config = Config.load(
        Path(args.data_dir).expanduser() if args.data_dir else None,
        overrides={"port": args.port, "bind": args.bind},
    )
    runner = Runner(config)
    if not runner.start():
        print(runner.error or "The server did not start.")
        return 1

    target = runner.console_url if not config.setup_complete else runner.local_url
    if not args.no_browser:
        threading.Timer(0.6, open_room, args=(target,)).start()

    try:
        if args.no_window:
            return _wait_forever(runner)
        try:
            return _controller(runner)
        except Exception:
            # No Tk on this machine. The browser is still open.
            return _wait_forever(runner)
    finally:
        runner.stop()


if __name__ == "__main__":
    raise SystemExit(main())
