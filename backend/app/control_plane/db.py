from __future__ import annotations

from pathlib import Path

from backend.config import AppConfig, load_app_config


DEFAULT_CONTROL_PLANE_SQLITE_PATH = Path("data") / "control_plane.sqlite"


def get_control_plane_database_url(settings: AppConfig | None = None) -> str:
    active_settings = settings or load_app_config()
    if active_settings.control_plane_database_url:
        return active_settings.control_plane_database_url
    fallback = active_settings.project_root / DEFAULT_CONTROL_PLANE_SQLITE_PATH
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{fallback.as_posix()}"
