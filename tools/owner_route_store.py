"""Versioned owner-edited lift-route store.

The server supplies WATERMAP_OWNER_TOKEN from the environment; no secret is
written to disk. Stored routes are canonical GeoJSON-compatible records.
"""
from __future__ import annotations

import hmac
import json
import math
import re
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TELANGANA_ROUTE_BOUNDS = (76.5, 15.3, 81.9, 20.2)
MAX_COORDINATES = 500
MAX_NOTE_CHARS = 2000
MAX_SOURCE_CHARS = 200
IST = timezone(timedelta(hours=5, minutes=30))


class Unauthorized(PermissionError):
    pass


class RouteStore:
    def __init__(self, path: Path, owner_token: str | None):
        self.path = Path(path)
        self.owner_token = owner_token
        self._lock = threading.Lock()

    def authorize(self, token: str | None) -> None:
        if not self.owner_token or not token or not hmac.compare_digest(token, self.owner_token):
            raise Unauthorized("owner token required")

    def _read(self) -> dict:
        if not self.path.exists():
            return {"routes": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("routes"), dict):
            raise ValueError("route store is invalid")
        return payload

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{threading.get_ident()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _clean_text(value: object, field: str, limit: int, *, required: bool = False) -> str:
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        value = value.strip()
        if required and not value:
            raise ValueError(f"{field} is required")
        if len(value) > limit:
            raise ValueError(f"{field} is too long")
        return value

    @classmethod
    def normalize(cls, route: object) -> dict:
        if not isinstance(route, dict):
            raise ValueError("route payload must be an object")
        project_id = cls._clean_text(route.get("project_id"), "project_id", 80, required=True)
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("project_id may contain only letters, numbers, dot, underscore, and hyphen")
        coordinates = route.get("coordinates")
        if not isinstance(coordinates, list) or not 2 <= len(coordinates) <= MAX_COORDINATES:
            raise ValueError(f"route must contain 2 to {MAX_COORDINATES} coordinates")
        west, south, east, north = TELANGANA_ROUTE_BOUNDS
        normalized_coordinates = []
        for coordinate in coordinates:
            if not isinstance(coordinate, list) or len(coordinate) != 2:
                raise ValueError("each coordinate must be [longitude, latitude]")
            lon, lat = coordinate
            if type(lon) not in (int, float) or type(lat) not in (int, float):
                raise ValueError("coordinates must be JSON numbers")
            lon, lat = float(lon), float(lat)
            if not math.isfinite(lon) or not math.isfinite(lat):
                raise ValueError("coordinates must be finite")
            if not (west <= lon <= east and south <= lat <= north):
                raise ValueError("coordinate lies outside the Telangana atlas bounds")
            normalized_coordinates.append([lon, lat])
        return {
            "project_id": project_id,
            "coordinates": normalized_coordinates,
            "note": cls._clean_text(route.get("note"), "note", MAX_NOTE_CHARS),
            "source": cls._clean_text(route.get("source", "Owner route editor"), "source", MAX_SOURCE_CHARS, required=True),
        }

    def save(self, token: str | None, route: object) -> dict:
        self.authorize(token)
        record = self.normalize(route)
        with self._lock:
            payload = self._read()
            project_id = record["project_id"]
            history = payload["routes"].setdefault(project_id, [])
            record["version"] = len(history) + 1
            record["edited_at"] = datetime.now(IST).isoformat()
            record["edited_by"] = "owner"
            record["geometry_status"] = "conceptual/owner-edited"
            history.append(record)
            self._write(payload)
            return deepcopy(record)

    def history(self, project_id: str) -> list[dict]:
        project_id = self._clean_text(project_id, "project_id", 80, required=True)
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("invalid project_id")
        return deepcopy(self._read()["routes"].get(project_id, []))

    def latest(self) -> list[dict]:
        return [deepcopy(history[-1]) for history in self._read()["routes"].values() if isinstance(history, list) and history]

    def revert(self, token: str | None, project_id: str, version: int) -> dict:
        self.authorize(token)
        history = self.history(project_id)
        if type(version) is not int or version < 1 or version > len(history):
            raise ValueError("version not found")
        previous = history[version - 1]
        return self.save(token, {
            "project_id": project_id,
            "coordinates": previous["coordinates"],
            "note": f"Reverted to version {version}",
            "source": previous.get("source", "Owner route editor"),
        })