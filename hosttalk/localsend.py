"""LocalSend v2 discovery and file transfer.

HostTalk speaks the same protocol as the LocalSend apps, so phones and
desktops on the network show up here without extra software.
"""

from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import json
import logging
import os
import socket
import struct
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

MULTICAST_GROUP = "224.0.0.167"
MULTICAST_PORT = 53317
PROTOCOL_VERSION = "2.1"
ANNOUNCE_INTERVAL = 12.0
DEVICE_TTL = 90.0
REQUEST_TIMEOUT = 0.6
TRANSFER_TIMEOUT = 60.0


class LocalSendError(RuntimeError):
    pass


@dataclass
class Device:
    fingerprint: str
    alias: str
    device_model: str
    device_type: str
    port: int
    protocol: str
    ip: str
    download: bool = True
    version: str = ""
    last_seen: float = field(default_factory=time.time)

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    def to_public(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_seen_ago"] = int(time.time() - self.last_seen)
        data["base_url"] = self.base_url
        return data


def _fingerprint_from(secret: str) -> str:
    return hashlib.sha256(f"hosttalk-localsend:{secret}".encode()).hexdigest()[:40]


class LocalSendManager:
    """Announce HostTalk, collect peers, and push files to a peer."""

    def __init__(
        self,
        *,
        enabled: bool,
        alias: str,
        secret: str,
        pin: str = "",
        protocol: str = "http",
        port: int = MULTICAST_PORT,
        logger: logging.Logger | None = None,
        on_receive: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.enabled = enabled
        self.alias = alias
        self.fingerprint = _fingerprint_from(secret)
        self.pin = pin
        self.protocol = protocol
        self.port = port
        self.logger = logger or logging.getLogger("hosttalk.localsend")
        self.on_receive = on_receive
        self._devices: dict[str, Device] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._sock: socket.socket | None = None
        self._last_error = ""
        self.received: list[dict[str, Any]] = []

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if not self.enabled or self._threads:
            return
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._announce_loop, name="localsend-announce", daemon=True),
            threading.Thread(target=self._listen_loop, name="localsend-listen", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        self.logger.info("LocalSend discovery started")

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads = []

    def reconfigure(self, **kwargs: Any) -> None:
        self.stop()
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.start()

    @property
    def last_error(self) -> str:
        return self._last_error

    # ------------------------------------------------------------ announcing
    def info(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "version": PROTOCOL_VERSION,
            "deviceModel": "HostTalk server",
            "deviceType": "desktop",
            "fingerprint": self.fingerprint,
            "port": self.port,
            "protocol": self.protocol,
            "download": True,
            "announce": True,
        }

    def announce(self) -> None:
        payload = json.dumps({**self.info(), "announce": True}).encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, (MULTICAST_GROUP, self.port))
        except OSError as exc:
            self._last_error = f"Announce failed: {exc}"
            self.logger.warning("LocalSend announce failed: %s", exc)
        finally:
            sock.close()

    def _announce_loop(self) -> None:
        while not self._stop.is_set():
            self.announce()
            self._stop.wait(ANNOUNCE_INTERVAL)

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.port))
            membership = struct.pack(
                "4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            sock.settimeout(1.0)
            self._sock = sock
            while not self._stop.is_set():
                try:
                    data, address = sock.recvfrom(4096)
                except TimeoutError:
                    self._prune()
                    continue
                except OSError as exc:
                    if self._stop.is_set():
                        break
                    self._last_error = str(exc)
                    self.logger.warning("LocalSend listener error: %s", exc)
                    break
                self._handle_datagram(data, address[0])
        except OSError as exc:
            self._last_error = f"Discovery is not available: {exc}"
            self.logger.warning("LocalSend discovery unavailable: %s", exc)
        finally:
            with contextlib.suppress(OSError):
                sock.close()

    def _handle_datagram(self, data: bytes, ip: str) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        fingerprint = str(payload.get("fingerprint", ""))
        if not fingerprint or fingerprint == self.fingerprint:
            return
        device = Device(
            fingerprint=fingerprint,
            alias=str(payload.get("alias", "Unknown device"))[:64],
            device_model=str(payload.get("deviceModel", ""))[:64],
            device_type=str(payload.get("deviceType", "unknown"))[:24],
            port=int(payload.get("port", self.port)),
            protocol=str(payload.get("protocol", "http")),
            ip=ip,
            download=bool(payload.get("download", True)),
            version=str(payload.get("version", "")),
        )
        with self._lock:
            existing = self._devices.get(fingerprint)
            if existing:
                device.last_seen = time.time()
            self._devices[fingerprint] = device

    def _prune(self) -> None:
        cutoff = time.time() - DEVICE_TTL
        with self._lock:
            for key in [key for key, device in self._devices.items() if device.last_seen < cutoff]:
                self._devices.pop(key, None)

    def devices(self) -> list[dict[str, Any]]:
        self._prune()
        with self._lock:
            return [
                device.to_public()
                for device in sorted(self._devices.values(), key=lambda item: item.alias.lower())
            ]

    def device(self, fingerprint: str) -> Device | None:
        with self._lock:
            return self._devices.get(fingerprint)

    # ---------------------------------------------------------------- probing
    def _local_subnets(self) -> list[ipaddress.IPv4Network]:
        networks: list[ipaddress.IPv4Network] = []
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                address = ipaddress.ip_address(info[4][0])
                if address.is_loopback or address.is_link_local:
                    continue
                network = ipaddress.ip_network(f"{address}/24", strict=False)
                if network not in networks:
                    networks.append(network)
        except OSError as exc:
            self.logger.debug("Interface enumeration failed: %s", exc)
        return networks[:2]

    def _probe(self, ip: str) -> Device | None:
        for scheme in ("http", "https"):
            url = f"{scheme}://{ip}:{self.port}/api/localsend/v2/info"
            try:
                response = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False)
                if response.status_code != 200:
                    continue
                payload = response.json()
            except (requests.RequestException, ValueError):
                continue
            fingerprint = str(payload.get("fingerprint", ""))
            if not fingerprint or fingerprint == self.fingerprint:
                continue
            return Device(
                fingerprint=fingerprint,
                alias=str(payload.get("alias", "Unknown device"))[:64],
                device_model=str(payload.get("deviceModel", ""))[:64],
                device_type=str(payload.get("deviceType", "unknown"))[:24],
                port=int(payload.get("port", self.port)),
                protocol=str(payload.get("protocol", scheme)),
                ip=ip,
                download=bool(payload.get("download", True)),
                version=str(payload.get("version", "")),
            )
        return None

    def scan(self, *, subnet_sweep: bool = True) -> list[dict[str, Any]]:
        if not self.enabled:
            raise LocalSendError("LocalSend is turned off in the host console")
        self.announce()
        if subnet_sweep:
            pending: list[str] = []
            for network in self._local_subnets():
                pending.extend(str(host) for host in network.hosts())
            pending = pending[:254]

            def worker(ip: str) -> None:
                device = self._probe(ip)
                if device:
                    with self._lock:
                        self._devices[device.fingerprint] = device

            threads = []
            for ip in pending:
                thread = threading.Thread(target=worker, args=(ip,), daemon=True)
                thread.start()
                threads.append(thread)
                if len(threads) >= 48:
                    for running in threads:
                        running.join(timeout=REQUEST_TIMEOUT + 0.2)
                    threads = []
            for running in threads:
                running.join(timeout=REQUEST_TIMEOUT + 0.2)
        time.sleep(0.4)
        return self.devices()

    # ---------------------------------------------------------------- sending
    def send_file(self, fingerprint: str, path: Path, filename: str, mime: str) -> dict[str, Any]:
        device = self.device(fingerprint)
        if not device:
            raise LocalSendError("That device is not on the network any more")
        size = path.stat().st_size
        file_id = uuid.uuid4().hex[:12]
        payload = {
            "info": self.info(),
            "files": {
                file_id: {
                    "id": file_id,
                    "fileName": filename,
                    "size": size,
                    "fileType": mime or "application/octet-stream",
                    "sha256": _sha256(path),
                    "preview": "",
                }
            },
        }
        session = requests.Session()
        session.verify = False
        try:
            prepared = session.post(
                f"{device.base_url}/api/localsend/v2/prepare-upload",
                json=payload,
                timeout=TRANSFER_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise LocalSendError(f"Could not reach {device.alias}") from exc
        if prepared.status_code == 403:
            raise LocalSendError(f"{device.alias} declined the transfer. Check its PIN.")
        if prepared.status_code >= 400:
            raise LocalSendError(f"{device.alias} answered {prepared.status_code}")
        try:
            tokens = prepared.json()
        except ValueError as exc:
            raise LocalSendError("The device sent an unexpected reply") from exc
        if tokens.get("status") == "declined":
            raise LocalSendError(f"{device.alias} declined the transfer")
        session_id = tokens.get("sessionId")
        file_token = (tokens.get("fileTokens") or {}).get(file_id)
        if not session_id or not file_token:
            raise LocalSendError("The device did not open a transfer session")

        try:
            with path.open("rb") as handle:
                upload = session.post(
                    f"{device.base_url}/api/localsend/v2/upload",
                    params={"sessionId": session_id, "fileId": file_id, "token": file_token},
                    data=handle,
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(size),
                    },
                    timeout=TRANSFER_TIMEOUT,
                )
        except requests.RequestException as exc:
            raise LocalSendError("The transfer stopped before it finished") from exc
        if upload.status_code >= 400:
            raise LocalSendError(f"{device.alias} rejected the file")
        self.logger.info("Sent %s to %s over LocalSend", filename, device.alias)
        return {"ok": True, "device": device.alias, "file": filename, "bytes": size}

    # -------------------------------------------------------------- receiving
    def check_pin(self, supplied: str | None) -> bool:
        return not self.pin or (supplied or "") == self.pin

    def record_received(self, record: dict[str, Any]) -> None:
        self.received.insert(0, record)
        del self.received[20:]
        if self.on_receive:
            try:
                self.on_receive(record)
            except Exception:  # pragma: no cover - callback must not break uploads
                self.logger.exception("LocalSend receive callback failed")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_self_signed_cert(cert_dir: Path, hostname: str = "hosttalk.local") -> tuple[Path, Path] | None:
    """Create a certificate for LocalSend HTTPS mode. Returns (cert, key)."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        return None

    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "localsend.crt"
    key_path = cert_dir / "localsend.key"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    import datetime

    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    with contextlib.suppress(OSError):
        os.chmod(key_path, 0o600)
    return cert_path, key_path
