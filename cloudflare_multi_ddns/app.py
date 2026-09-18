#!/usr/bin/env python3

from __future__ import annotations

import ipaddress
import json
import logging
import signal
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API_BASE = "https://api.cloudflare.com/client/v4"
LOGGER = logging.getLogger("cloudflare_multi_ddns")
DEFAULT_CONFIG = {
    "api_token": "",
    "interval": 300,
    "create_missing": False,
    "dry_run": True,
    "ipv4_url": "https://api.ipify.org",
    "ipv6_url": "https://api6.ipify.org",
    "records": [],
}


class CloudflareError(RuntimeError):
    pass


class CloudflareClient:
    def __init__(self, api_token: str, api_base: str = API_BASE) -> None:
        self.api_token = api_token
        self.api_base = api_base.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "User-Agent": "home-assistant-cloudflare-multi-ddns/0.1.0",
            },
        )

        try:
            with urlopen(request, timeout=30) as response:
                data = json.load(response)
        except HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise CloudflareError(f"Cloudflare HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError) as error:
            raise CloudflareError(f"Impossible de joindre Cloudflare: {error}") from error

        if not data.get("success"):
            messages = ", ".join(
                item.get("message", "erreur inconnue") for item in data.get("errors", [])
            )
            raise CloudflareError(messages or "Réponse Cloudflare invalide")
        return data

    def list_zones(self) -> list[dict[str, Any]]:
        zones: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.request("GET", "/zones", {"page": page, "per_page": 50})
            zones.extend(data.get("result", []))
            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                return zones
            page += 1

    def find_record(
        self, zone_id: str, name: str, record_type: str
    ) -> dict[str, Any] | None:
        data = self.request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            {"name": name, "type": record_type, "match": "all", "per_page": 100},
        )
        records = data.get("result", [])
        if len(records) > 1:
            raise CloudflareError(f"Plusieurs enregistrements {record_type} trouvés pour {name}")
        return records[0] if records else None

    def update_record(
        self, zone_id: str, record_id: str, payload: dict[str, Any]
    ) -> None:
        self.request("PATCH", f"/zones/{zone_id}/dns_records/{record_id}", payload=payload)

    def create_record(self, zone_id: str, payload: dict[str, Any]) -> None:
        self.request("POST", f"/zones/{zone_id}/dns_records", payload=payload)


def public_ip(url: str, version: int) -> str:
    request = Request(url, headers={"User-Agent": "home-assistant-cloudflare-multi-ddns/0.1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            value = response.read().decode().strip()
    except (HTTPError, URLError, TimeoutError) as error:
        raise CloudflareError(f"Impossible de détecter l'adresse IPv{version}: {error}") from error

    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise CloudflareError(f"Le service IPv{version} a retourné une adresse invalide") from error
    if address.version != version or not address.is_global:
        raise CloudflareError(f"Le service IPv{version} n'a pas retourné une adresse publique IPv{version}")
    return str(address)


def select_zone(record_name: str, zones: list[dict[str, Any]], configured: str | None) -> dict[str, Any]:
    normalized_name = record_name.rstrip(".").lower()
    if configured:
        configured_name = configured.rstrip(".").lower()
        matches = [zone for zone in zones if zone["name"].lower() == configured_name]
    else:
        matches = [
            zone
            for zone in zones
            if normalized_name == zone["name"].lower()
            or normalized_name.endswith(f".{zone['name'].lower()}")
        ]
        matches.sort(key=lambda zone: len(zone["name"]), reverse=True)
    if not matches:
        target = configured or record_name
        raise CloudflareError(f"Aucune zone accessible ne correspond à {target}")
    return matches[0]


def qualified_record_name(record_name: str, zone_name: str) -> str:
    name = record_name.rstrip(".").lower()
    zone = zone_name.rstrip(".").lower()
    if name == "@":
        return zone
    if name == zone or name.endswith(f".{zone}"):
        return name
    return f"{name}.{zone}"


def validate_config(config: dict[str, Any]) -> None:
    if not config.get("api_token"):
        raise ValueError("api_token est obligatoire")
    records = config.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Au moins un enregistrement DNS est obligatoire")
    seen: set[tuple[str, str]] = set()
    for record in records:
        record["name"] = record.get("name", "").rstrip(".").lower()
        record["type"] = record.get("type", "").upper()
        if not record["name"] or record["type"] not in {"A", "AAAA"}:
            raise ValueError("Chaque enregistrement exige un nom et un type A ou AAAA")
        zone = record.get("zone", "").rstrip(".").lower()
        if zone:
            record["zone"] = zone
        effective_name = qualified_record_name(record["name"], zone) if zone else record["name"]
        key = (effective_name, record["type"])
        if key in seen:
            raise ValueError(f"Enregistrement en double: {record['type']} {effective_name}")
        seen.add(key)


def normalized_config(config: dict[str, Any], current_token: str = "") -> dict[str, Any]:
    candidate = {**DEFAULT_CONFIG, **config}
    candidate["api_token"] = candidate.get("api_token") or current_token
    interval = candidate.get("interval")
    if not isinstance(interval, int) or isinstance(interval, bool) or not 60 <= interval <= 86400:
        raise ValueError("interval doit être compris entre 60 et 86400 secondes")
    for key in ("create_missing", "dry_run"):
        if not isinstance(candidate.get(key), bool):
            raise ValueError(f"{key} doit être vrai ou faux")
    validate_config(candidate)
    return candidate


def sync_records(config: dict[str, Any], client: CloudflareClient) -> tuple[int, int]:
    zones = client.list_zones()
    addresses: dict[str, str] = {}
    for record_type, version, option in (
        ("A", 4, "ipv4_url"),
        ("AAAA", 6, "ipv6_url"),
    ):
        if any(record["type"] == record_type for record in config["records"]):
            addresses[record_type] = public_ip(config[option], version)
            LOGGER.info("Adresse publique IPv%s détectée: %s", version, addresses[record_type])

    changed = 0
    unchanged = 0
    for configured_record in config["records"]:
        configured_name = configured_record["name"]
        record_type = configured_record["type"]
        address = addresses[record_type]
        zone = select_zone(configured_name, zones, configured_record.get("zone"))
        name = qualified_record_name(configured_name, zone["name"])
        existing = client.find_record(zone["id"], name, record_type)

        if existing and existing.get("content") == address:
            LOGGER.info("Inchangé: %s %s", record_type, name)
            unchanged += 1
            continue

        payload: dict[str, Any] = {"content": address}
        if "proxied" in configured_record:
            payload["proxied"] = configured_record["proxied"]
        if "ttl" in configured_record:
            payload["ttl"] = configured_record["ttl"]

        if existing:
            if config.get("dry_run", False):
                LOGGER.info("Simulation: mise à jour de %s %s vers %s", record_type, name, address)
            else:
                client.update_record(zone["id"], existing["id"], payload)
                LOGGER.info("Mis à jour: %s %s vers %s", record_type, name, address)
            changed += 1
            continue

        if not config.get("create_missing", False):
            raise CloudflareError(f"Enregistrement introuvable: {record_type} {name}")
        payload.update({"type": record_type, "name": name})
        payload.setdefault("ttl", 1)
        payload.setdefault("proxied", False)
        if config.get("dry_run", False):
            LOGGER.info("Simulation: création de %s %s vers %s", record_type, name, address)
        else:
            client.create_record(zone["id"], payload)
            LOGGER.info("Créé: %s %s vers %s", record_type, name, address)
        changed += 1
    return changed, unchanged


class AppRuntime:
    def __init__(self, config_path: Path, options_path: Path | None = None) -> None:
        self.config_path = config_path
        self.options_path = options_path
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.config_lock = threading.Lock()
        self.sync_lock = threading.Lock()
        self.config = self._load_config()
        self.status: dict[str, Any] = {
            "state": "waiting" if not self.is_configured() else "idle",
            "last_run": None,
            "last_success": None,
            "changed": 0,
            "unchanged": 0,
            "error": None,
        }

    def _load_config(self) -> dict[str, Any]:
        source = self.config_path if self.config_path.exists() else self.options_path
        if source and source.exists():
            with source.open(encoding="utf-8") as config_file:
                return {**DEFAULT_CONFIG, **json.load(config_file)}
        return dict(DEFAULT_CONFIG)

    def is_configured(self) -> bool:
        return bool(self.config.get("api_token") and self.config.get("records"))

    def public_config(self) -> dict[str, Any]:
        with self.config_lock:
            public = {key: value for key, value in self.config.items() if key != "api_token"}
            public["has_token"] = bool(self.config.get("api_token"))
            return public

    def save_config(self, submitted: dict[str, Any]) -> dict[str, Any]:
        with self.config_lock:
            candidate = normalized_config(submitted, self.config.get("api_token", ""))
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.config_path.with_suffix(".tmp")
            with temporary_path.open("w", encoding="utf-8") as config_file:
                json.dump(candidate, config_file, indent=2)
            temporary_path.replace(self.config_path)
            self.config = candidate
            self.status["state"] = "idle"
            self.status["error"] = None
        self.wake_event.set()
        return self.public_config()

    def test_token(self, submitted_token: str) -> list[dict[str, str]]:
        token = submitted_token
        if not token:
            with self.config_lock:
                token = self.config.get("api_token", "")
        if not token:
            raise ValueError("Saisissez un jeton API Cloudflare")
        zones = CloudflareClient(token).list_zones()
        return [{"id": zone["id"], "name": zone["name"]} for zone in zones]

    def perform_sync(self) -> None:
        if not self.sync_lock.acquire(blocking=False):
            raise CloudflareError("Une synchronisation est déjà en cours")
        try:
            with self.config_lock:
                config = json.loads(json.dumps(self.config))
            validate_config(config)
            self.status.update({"state": "running", "last_run": _now(), "error": None})
            changed, unchanged = sync_records(config, CloudflareClient(config["api_token"]))
            self.status.update(
                {
                    "state": "idle",
                    "last_success": _now(),
                    "changed": changed,
                    "unchanged": unchanged,
                    "error": None,
                }
            )
            LOGGER.info("Synchronisation terminée: %d modifié(s), %d inchangé(s)", changed, unchanged)
        except (CloudflareError, ValueError, KeyError) as error:
            self.status.update({"state": "error", "error": str(error)})
            LOGGER.error("Échec de la synchronisation: %s", error)
        finally:
            self.sync_lock.release()

    def request_sync(self) -> None:
        if not self.is_configured():
            raise ValueError("Configurez un jeton et au moins un enregistrement")
        if self.sync_lock.locked():
            raise CloudflareError("Une synchronisation est déjà en cours")
        threading.Thread(target=self.perform_sync, daemon=True).start()

    def scheduler(self) -> None:
        while not self.stop_event.is_set():
            if self.is_configured():
                self.perform_sync()
            with self.config_lock:
                interval = self.config.get("interval", 300)
            self.wake_event.wait(interval)
            self.wake_event.clear()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApiHandler(BaseHTTPRequestHandler):
    runtime: AppRuntime
    static_path = Path(__file__).parent / "www"

    def log_message(self, format_string: str, *args: Any) -> None:
        LOGGER.debug(format_string, *args)

    def _api_path(self) -> str:
        path = urlparse(self.path).path.rstrip("/")
        marker = path.find("/api/")
        return path[marker:] if marker >= 0 else path

    def _json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Requête invalide") from error
        if length > 1_000_000:
            raise ValueError("Requête trop volumineuse")
        try:
            value = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            raise ValueError("JSON invalide") from error
        if not isinstance(value, dict):
            raise ValueError("Un objet JSON est attendu")
        return value

    def _send_json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, error: Exception) -> None:
        self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_GET(self) -> None:
        path = self._api_path()
        if path == "/api/config":
            self._send_json(HTTPStatus.OK, self.runtime.public_config())
            return
        if path == "/api/status":
            self._send_json(HTTPStatus.OK, dict(self.runtime.status))
            return
        raw_path = urlparse(self.path).path
        if not raw_path.endswith("/") and not raw_path.endswith(("/app.css", "/app.js")):
            self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
            self.send_header("Location", f"{raw_path}/")
            self.end_headers()
            return
        asset = "index.html"
        if raw_path.endswith("/app.css"):
            asset = "app.css"
        elif raw_path.endswith("/app.js"):
            asset = "app.js"
        file_path = self.static_path / asset
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = file_path.read_bytes()
        content_type = "text/html" if asset.endswith(".html") else "text/css" if asset.endswith(".css") else "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_PUT(self) -> None:
        try:
            if self._api_path() != "/api/config":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            config = self.runtime.save_config(self._json_body())
            self._send_json(HTTPStatus.OK, config)
        except (ValueError, OSError) as error:
            self._send_error(error)

    def do_POST(self) -> None:
        try:
            path = self._api_path()
            if path == "/api/test":
                zones = self.runtime.test_token(str(self._json_body().get("api_token", "")))
                self._send_json(HTTPStatus.OK, {"zones": zones})
                return
            if path == "/api/sync":
                self.runtime.request_sync()
                self._send_json(HTTPStatus.ACCEPTED, {"status": "started"})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (CloudflareError, ValueError) as error:
            self._send_error(error)


def run(config_path: Path, options_path: Path | None = None) -> None:
    runtime = AppRuntime(config_path, options_path)
    ApiHandler.runtime = runtime
    server = ThreadingHTTPServer(("0.0.0.0", 8099), ApiHandler)
    scheduler = threading.Thread(target=runtime.scheduler, daemon=True)
    web_server = threading.Thread(target=server.serve_forever, daemon=True)
    scheduler.start()
    web_server.start()
    signal.signal(signal.SIGTERM, lambda *_: runtime.stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: runtime.stop_event.set())
    LOGGER.info("Interface Home Assistant disponible sur le port 8099")
    runtime.stop_event.wait()
    runtime.wake_event.set()
    server.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/config.json")
    try:
        run(path, Path("/data/options.json"))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        LOGGER.critical("Configuration invalide: %s", error)
        raise SystemExit(1) from error
