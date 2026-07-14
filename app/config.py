from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

def _environment_value(name: str, default: str = "") -> str:
    """Read one setting without copying secrets into process logs or source code."""

    if value := os.getenv(name):
        return value.strip()

    for candidate in (Path(".env"), Path(".env.example")):
        if not candidate.is_file():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return default

@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime configuration."""

    app_name: str = "Gemini Autonomous Document Agent"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_timeout_seconds: float = 90.0
    output_dir: Path = Path("artifacts")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gemini_api_key=_environment_value("GEMINI_API_KEY"),
            gemini_model=_environment_value("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_base_url=_environment_value(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ).rstrip("/"),
            llm_timeout_seconds=float(
                _environment_value("LLM_TIMEOUT_SECONDS", "90")
            ),
            output_dir=Path(_environment_value("OUTPUT_DIR", "artifacts")),
        )
