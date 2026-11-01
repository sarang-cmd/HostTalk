"""Flask application factory and page routes."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)

from . import api_chat, api_files, api_host, api_session
from .auth import COLOR_GRID
from .config import project_root
from .netinfo import is_loopback, network_summary
from .services import Services
from .version import __version__


def create_app(services: Services) -> Flask:
    root = project_root()
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
        static_url_path="/static",
    )
    config = services.config
    app.secret_key = config.secret_key
    app.config.update(
        SESSION_COOKIE_NAME="hosttalk",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
        MAX_CONTENT_LENGTH=config.upload_limit_bytes + 1024 * 1024,
        TEMPLATES_AUTO_RELOAD=False,
        JSON_SORT_KEYS=False,
    )
    app.extensions["hosttalk"] = services

    @app.before_request
    def attach_services():
        g.services = services

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if not request.path.startswith("/static"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob: https:; "
                "media-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; font-src 'self'; "
                "frame-ancestors 'self'; base-uri 'none'; form-action 'self'",
            )
        if request.path.startswith("/api/") or request.path == "/healthz":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for blueprint in (api_session.bp, api_chat.bp, api_files.bp, api_host.bp):
        app.register_blueprint(blueprint)

    def template_context() -> dict[str, Any]:
        return {
            "version": __version__,
            "room_name": config.room_name,
            "palette": COLOR_GRID,
            "theme": config.values["default_theme"],
            "static_v": __version__,
        }

    @app.get("/")
    def landing():
        """The front page. Figures come from this instance and render server side."""
        join_code = request.args.get("join", "")
        if join_code:
            return redirect(f"/room?join={quote(join_code)}")
        try:
            counts = instance_stats(services)
        except Exception as exc:
            services.logger.warning("The front page could not read the store: %s", exc)
            counts = None
        return render_template(
            "landing.html",
            counts=counts,
            network=network_summary(request.headers, config.port),
            local=is_loopback(request.remote_addr or ""),
            **template_context(),
        )

    @app.get("/room")
    def room():
        network = network_summary(request.headers, config.port)
        bootstrap = {
            "version": __version__,
            "address": network["address"],
            "ssid": network["ssid"],
            "online": services.presence.count(),
            "room_name": config.room_name,
            "setup_complete": config.setup_complete,
            "requires_password": bool(config.values["password_hash"]),
            "local": is_loopback(request.remote_addr or ""),
            "port": config.port,
            "max_upload_mb": int(config.values["max_upload_mb"]),
            "palette": COLOR_GRID,
            "theme": config.values["default_theme"],
            "gifs_ready": bool(config.giphy_key),
            "previews_enabled": config.previews_enabled,
            "localsend_enabled": bool(config.localsend.get("enabled")),
            "max_room_members": config.max_room_members,
            "join_code": request.args.get("join", ""),
        }
        return render_template(
            "room.html",
            bootstrap=bootstrap,
            **template_context(),
        )

    @app.get("/console")
    def console():
        return render_template(
            "console.html",
            setup_complete=config.setup_complete,
            local=is_loopback(request.remote_addr or ""),
            **template_context(),
        )

    @app.get("/about")
    def about():
        return render_template(
            "about.html",
            network=network_summary(request.headers, config.port),
            **template_context(),
        )

    @app.get("/terms")
    def terms():
        return render_template("terms.html", **template_context())

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html", **template_context())

    @app.get("/healthz")
    def healthz():
        """Liveness plus a database read. A broken store reports degraded, not 500."""
        try:
            stats = services.store.stats()
        except Exception as exc:
            services.logger.error("Health check could not read the store: %s", exc)
            return (
                jsonify(
                    {
                        "ok": False,
                        "status": "degraded",
                        "version": __version__,
                        "port": config.port,
                        "detail": "The database could not be read",
                    }
                ),
                503,
            )
        return jsonify(
            {
                "ok": True,
                "status": "ok",
                "version": __version__,
                "uptime": int(time.time() - services.started_at),
                "port": config.port,
                "people": services.presence.count(),
                "messages": stats["messages"],
                "rooms": stats["rooms"],
            }
        )

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            str(project_root() / "static" / "icons"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
            max_age=86400,
        )

    @app.get("/manifest.webmanifest")
    def manifest():
        payload = {
            "name": f"{config.room_name} on HostTalk",
            "short_name": "HostTalk",
            "description": "A room on your local network. No cloud, no accounts.",
            "start_url": "/room",
            "scope": "/",
            "display": "standalone",
            "background_color": "#F2F1EC",
            "theme_color": "#F2F1EC",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": "/static/icons/icon-maskable-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        }
        response = Response(json.dumps(payload), mimetype="application/manifest+json")
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/sw.js")
    def service_worker():
        response = send_from_directory(str(root / "static"), "sw.js", mimetype="text/javascript")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/robots.txt")
    def robots():
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "Not found"}), 404
        return (
            render_template(
                "error.html",
                code=404,
                title="This page is not here",
                detail="The address may be from an older version of HostTalk.",
                **template_context(),
            ),
            404,
        )

    @app.errorhandler(413)
    def too_large(error):
        message = f"Files limit is {config.values['max_upload_mb']} MB"
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": message}), 413
        return render_template(
            "error.html", code=413, title="That file is too large", detail=message, **template_context()
        ), 413

    @app.errorhandler(500)
    def server_error(error):
        services.logger.exception("Unhandled error on %s", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "The server hit a problem"}), 500
        return (
            render_template(
                "error.html",
                code=500,
                title="The server hit a problem",
                detail="Check the host console logs for the cause.",
                **template_context(),
            ),
            500,
        )

    return app
