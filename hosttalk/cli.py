"""HostTalk command line: serve, setup, config, doctor."""

from __future__ import annotations

import argparse
import os
import platform
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from .app import create_app
from .config import Config, ConfigError
from .diagnostics import overall, run_checks
from .netinfo import lan_ip, wifi_name
from .services import build_services
from .version import CODENAME, __version__

BANNER = r"""
  __  __            __  ______      __ __
 / / / /____  _____/ /_/_  __/___ _/ //_/
/ /_/ / __ \/ ___/ __ \/ / / __ `/ ,<
/ __  / /_/ (__  ) /_/ / / / /_/ / /| |
\/ /_/\____/____/_.___/_/  \__,_/_/ |_|
""".strip("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hosttalk",
        description="Run a chat room on your local network.",
    )
    parser.add_argument("--version", action="version", version=f"HostTalk {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Start the server (default)")
    add_serve_arguments(serve)

    setup = subparsers.add_parser("setup", help="Create the room password and settings")
    setup.add_argument("--password", default=None)
    setup.add_argument("--room", default=None, help="Room name")
    setup.add_argument("--port", type=int, default=None)
    setup.add_argument("--data-dir", default=None)
    setup.add_argument("--non-interactive", action="store_true")

    config_cmd = subparsers.add_parser("config", help="Read or change settings")
    config_cmd.add_argument("action", choices=["show", "path", "get", "set"])
    config_cmd.add_argument("key", nargs="?")
    config_cmd.add_argument("value", nargs="?")
    config_cmd.add_argument("--data-dir", default=None)

    reset = subparsers.add_parser("reset-password", help="Set a new room password")
    reset.add_argument("--password", default=None)
    reset.add_argument("--data-dir", default=None)

    doctor = subparsers.add_parser("doctor", help="Check the network and data folder")
    doctor.add_argument("--data-dir", default=None)

    subparsers.add_parser("app", help="Start the server with a desktop window")

    subparsers.add_parser("version", help="Print the version")
    return parser


def add_serve_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--port", type=int, default=None, help="Port to listen on")
    parser.add_argument("--host", "--bind", dest="bind", default=None, help="Bind address")
    parser.add_argument("--data-dir", default=None, help="Where config, messages, and uploads live")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--headless", action="store_true", help="Never open a browser or console window")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--password", default=None, help="Set the room password before start")
    parser.add_argument("--open-console", action="store_true", help="Open the host console")
    parser.add_argument("--no-localsend", action="store_true", help="Turn LocalSend discovery off")
    parser.add_argument("--reload", action="store_true", help="Developer reload mode (Flask server)")


def _open(url: str) -> None:
    try:
        if platform.system() == "Windows":
            os.startfile(url)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            import subprocess

            subprocess.Popen(["open", url])
        else:
            webbrowser.open_new_tab(url)
    except Exception:
        # A missing browser is not an error. The URL prints above the prompt.
        sys.stderr.write("Could not open a browser. Open the address by hand.\n")


def _print_banner(config: Config, *, local_url: str, network_url: str, host: str) -> None:
    print(BANNER)
    print(f"  HostTalk {__version__}  {CODENAME}")
    print()
    rows = [
        ("Room", config.room_name),
        ("This machine", local_url),
        ("Network", network_url),
        ("Wi-Fi", wifi_name() or "not detected"),
        ("Password", "set" if config.values["password_hash"] else "NOT SET"),
        ("Data", str(config.data_dir)),
        ("Address", host),
    ]
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"  {label.ljust(width)}   {value}")
    print()
    print("  Keep this window open while the room is in use.")
    print("  Press Ctrl+C to stop.")
    print()


def _print_qr(text: str) -> None:
    try:
        import qrcode  # type: ignore
    except ImportError:
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(text)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def _resolve_config(args: argparse.Namespace) -> Config:
    overrides: dict[str, Any] = {}
    if getattr(args, "port", None) is not None:
        overrides["port"] = args.port
    if getattr(args, "bind", None):
        overrides["bind"] = args.bind
    if getattr(args, "log_level", None):
        overrides["log_level"] = args.log_level
    if getattr(args, "no_browser", False) or getattr(args, "headless", False):
        overrides["open_browser"] = False
    data_dir = Path(args.data_dir).expanduser() if getattr(args, "data_dir", None) else None
    return Config.load(data_dir, overrides)


def command_setup(args: argparse.Namespace) -> int:
    config = Config.load(Path(args.data_dir).expanduser() if args.data_dir else None)
    if config.setup_complete:
        print("This server is already set up. Use reset-password to change the password.")
        return 1
    password = args.password or ""
    if not password and not args.non_interactive:
        import getpass

        password = getpass.getpass("Room password: ")
        confirm = getpass.getpass("Repeat password: ")
        if password != confirm:
            print("Passwords do not match.")
            return 1
    if len(password) < 4:
        print("Use at least 4 characters for the password.")
        return 1
    config.set_password(password)
    patch: dict[str, Any] = {}
    if args.room:
        patch["room_name"] = args.room
    if args.port:
        patch["port"] = args.port
    if patch:
        config.update(patch)
    print(f"Ready. Room: {config.room_name}. Port: {config.port}.")
    print(f"Settings: {config.path}")
    return 0


def command_config(args: argparse.Namespace) -> int:
    config = Config.load(Path(args.data_dir).expanduser() if args.data_dir else None)
    if args.action == "show":
        import json

        print(json.dumps(config.redacted(), indent=2))
        return 0
    if args.action == "path":
        print(config.path)
        return 0
    if not args.key:
        print("Add a key, for example: hosttalk config get port")
        return 1
    if args.key in {"klipy_key", "password_hash", "host_password_hash", "secret_key"}:
        print("That key is write-only. Set it in the host console.")
        return 1
    if args.action == "get":
        value = config.values.get(args.key)
        print(value if not isinstance(value, dict) else __import__("json").dumps(value, indent=2))
        return 0
    if args.value is None:
        print("Add a value, for example: hosttalk config set port 7284")
        return 1
    raw = args.value
    parsed: Any = raw
    if args.key in {"port", "max_room_members", "max_upload_mb", "retention_days"}:
        parsed = int(raw)
    elif args.key in {"open_browser", "console_local_only", "previews_enabled", "gifs_enabled"}:
        parsed = str(raw).lower() in {"1", "true", "yes", "on"}
    try:
        config.update({args.key: parsed})
    except (ConfigError, ValueError) as exc:
        print(f"Not saved: {exc}")
        return 1
    print(f"{args.key} = {config.values.get(args.key)}")
    if args.key in {"port", "bind"}:
        print("Restart the server to use the new address.")
    return 0


def command_reset_password(args: argparse.Namespace) -> int:
    config = Config.load(Path(args.data_dir).expanduser() if args.data_dir else None)
    password = args.password or ""
    if not password:
        import getpass

        password = getpass.getpass("New room password: ")
        confirm = getpass.getpass("Repeat password: ")
        if password != confirm:
            print("Passwords do not match.")
            return 1
    try:
        config.set_password(password)
    except ConfigError as exc:
        print(str(exc))
        return 1
    print("Password changed. People already in the room stay connected until they reload.")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    config = Config.load(Path(args.data_dir).expanduser() if args.data_dir else None)
    services = build_services(config, start_localsend=False)
    checks = run_checks(services)
    for check in checks:
        marker = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}[check["status"]]
        print(f"[{marker}] {check['label']}: {check['detail']}")
        if check.get("fix") and check["status"] != "ok":
            print(f"         fix: {check['fix']}")
    print()
    print(f"Overall: {overall(checks)}")
    return 1 if overall(checks) == "fail" else 0


def command_serve(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    if args.password:
        try:
            config.set_password(args.password)
        except ConfigError as exc:
            print(str(exc))
            return 1
    if args.no_localsend:
        config.update({"localsend": {**config.localsend, "enabled": False}})

    services = build_services(config, start_localsend=bool(config.localsend.get("enabled")))
    app = create_app(services)

    local_url = f"http://127.0.0.1:{config.port}/"
    host_ip = lan_ip()
    network_url = f"http://{host_ip}:{config.port}/room"
    console_url = f"http://127.0.0.1:{config.port}/console"

    if not config.setup_complete:
        print("No password set yet. Open the host console to finish setup.")

    _print_banner(config, local_url=local_url, network_url=network_url, host=config.bind)
    if host_ip != "127.0.0.1":
        _print_qr(network_url)

    target = console_url if (not config.setup_complete or args.open_console) else local_url
    if config.values["open_browser"] and not args.headless and not args.no_browser:
        threading.Timer(1.0, _open, args=(target,)).start()

    waitress = None
    if not args.reload:
        try:
            import waitress  # type: ignore

            server = waitress.create_server(
                app,
                host=config.bind,
                port=config.port,
                threads=48,
                ident="HostTalk",
                clear_untrusted_proxy_headers=True,
            )
        except OSError as exc:
            print(f"Cannot listen on {config.bind}:{config.port}: {exc}")
            print("Change the port in the host console, or start with --port 7285.")
            return 1
        except ImportError:
            server = None
    else:
        server = None

    if server is not None:
        def stop() -> None:
            threading.Thread(target=server.close, daemon=True).start()

        services.control.on_stop(stop)
        try:
            server.run()
        except KeyboardInterrupt:
            server.close()
        finally:
            services.localsend.stop()
        return 0

    # Fallback for development reloads or when waitress is unavailable.
    from werkzeug.serving import make_server

    try:
        httpd = make_server(config.bind, config.port, app, threaded=True)
    except OSError as exc:
        print(f"Cannot listen on {config.bind}:{config.port}: {exc}")
        return 1
    thread = threading.Thread(target=httpd.serve_forever, name="hosttalk-http", daemon=True)
    thread.start()
    services.control.on_stop(lambda: httpd.shutdown())
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        httpd.shutdown()
    finally:
        services.localsend.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    known = {"serve", "setup", "config", "reset-password", "doctor", "version", "app"}
    if not argv or (argv[0].startswith("-") and argv[0] not in {"-h", "--help", "--version"}) or argv[0] not in known and argv[0] not in {"-h", "--help", "--version"}:
        argv.insert(0, "serve")
    if argv[0] == "app":
        # The desktop window keeps its own flags, so pass the rest straight on.
        from .desktop import main as desktop_main

        return desktop_main(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"HostTalk {__version__} {CODENAME}")
        return 0
    if args.command == "setup":
        return command_setup(args)
    if args.command == "config":
        return command_config(args)
    if args.command == "reset-password":
        return command_reset_password(args)
    if args.command == "doctor":
        return command_doctor(args)
    if args.command is None:
        parser.print_help()
        return 1
    return command_serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
