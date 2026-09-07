from __future__ import annotations

import json
import os
import winreg
from dataclasses import asdict, dataclass
from pathlib import Path


APP_NAME = "ArcMic"
DEFAULT_GAIN_DB = 6.0
MAX_GAIN_DB = 30.0
NOISE_MODES = ("off", "natural", "hum", "ai", "ai_hum")
HUM_FILTERS = (
    "Filter: ON PK Fc 50 Hz Gain -24 dB Q 10",
    "Filter: ON PK Fc 100 Hz Gain -18 dB Q 18",
    "Filter: ON PK Fc 150 Hz Gain -12 dB Q 24",
    "Filter: ON PK Fc 200 Hz Gain -9 dB Q 28",
)


def local_app_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME


def program_data_dir() -> Path:
    base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return base / APP_NAME


def equalizer_config_dir() -> Path:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\EqualizerAPO", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return Path(str(winreg.QueryValueEx(key, "ConfigPath")[0]))
    except OSError:
        return program_data_dir() / "config"


@dataclass(slots=True)
class AppSettings:
    enabled: bool = True
    noise_mode: str = "ai_hum"
    gain_db: float = DEFAULT_GAIN_DB
    device_guid: str = ""
    monitor_output_name: str = ""

    def normalized(self) -> "AppSettings":
        self.gain_db = min(MAX_GAIN_DB, max(0.0, round(float(self.gain_db) * 2) / 2))
        if self.noise_mode not in NOISE_MODES:
            self.noise_mode = "ai_hum"
        self.device_guid = self.device_guid.strip()
        self.monitor_output_name = self.monitor_output_name.strip()
        return self


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or local_app_dir() / "settings.json"

    def load(self) -> AppSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {key: payload[key] for key in AppSettings.__dataclass_fields__ if key in payload}
            return AppSettings(**allowed).normalized()
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(settings.normalized()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def quote_eapo(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def render_eapo_config(
    settings: AppSettings,
    plugin_path: Path | None = None,
) -> str:
    """Render the tiny Equalizer APO include owned by ArcMic.

    Noise filters intentionally run before positive gain so they do not receive
    unnecessarily amplified background noise. Natural mode only trims frequencies
    outside the useful voice band. Hum mode additionally removes narrow 50 Hz mains
    harmonics without reconstructing or otherwise altering the voice signal.
    """
    lines = [
        "# ArcMic managed configuration. Manual changes may be overwritten.",
        "# No audio is recorded or uploaded.",
    ]
    settings.normalized()
    if not settings.enabled or not settings.device_guid:
        lines.append("# Enhancement is off.")
        return "\n".join(lines) + "\n"

    lines.append(f"Device: {settings.device_guid}")
    if settings.noise_mode in ("natural", "hum", "ai", "ai_hum"):
        lines.append("Filter: ON HPQ Fc 75 Hz Q 0.7071")
    if settings.noise_mode == "natural":
        lines.append("Filter: ON LPQ Fc 14000 Hz Q 0.7071")
    elif settings.noise_mode == "hum":
        # China and many other regions use 50 Hz mains. Narrow cuts suppress
        # the fundamental and its most audible harmonics while leaving almost
        # all of the speech band untouched.
        lines.extend(HUM_FILTERS)
        lines.append("Filter: ON LPQ Fc 13500 Hz Q 0.7071")
    elif settings.noise_mode == "ai_hum":
        # Remove deterministic electrical hum first so the neural denoiser can
        # concentrate on broadband and changing noise at the same low cost.
        lines.extend(HUM_FILTERS)
        if plugin_path is not None:
            lines.append(f"VSTPlugin: Library {quote_eapo(str(plugin_path))}")
    elif settings.noise_mode == "ai" and plugin_path is not None:
        lines.append(f"VSTPlugin: Library {quote_eapo(str(plugin_path))}")
    lines.append(f"Preamp: {settings.gain_db:.1f} dB")
    return "\n".join(lines) + "\n"


def write_managed_config(settings: AppSettings, path: Path | None = None) -> Path:
    target = path or equalizer_config_dir() / "ArcMic.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    plugin_path = program_data_dir() / "engine" / "rnnoise_mono.dll"
    temporary = target.with_suffix(".tmp")
    content = render_eapo_config(settings, plugin_path)
    temporary.write_text(content, encoding="utf-8")
    try:
        temporary.replace(target)
    except OSError as exc:
        # audiodg/Equalizer APO may keep the live config open without FILE_SHARE_DELETE.
        # Replacing the inode then fails even though editing the file itself is allowed.
        if getattr(exc, "winerror", None) not in (5, 32):
            raise
        temporary.unlink(missing_ok=True)
        target.write_text(content, encoding="utf-8")
    return target


INCLUDE_BEGIN = "# >>> ArcMic managed include >>>"
INCLUDE_END = "# <<< ArcMic managed include <<<"


def patch_main_config(content: str, managed_config_path: Path) -> str:
    """Insert exactly one ArcMic include while preserving existing user filters."""
    lines = content.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == INCLUDE_BEGIN:
            skipping = True
            continue
        if line.strip() == INCLUDE_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)

    while output and not output[-1].strip():
        output.pop()
    output.extend(
        [
            "",
            INCLUDE_BEGIN,
            # Include consumes the entire remainder as its path. Quoting is not
            # supported here (unlike VSTPlugin's splitQuoted parser).
            f"Include: {managed_config_path}",
            INCLUDE_END,
        ]
    )
    return "\n".join(output) + "\n"


def remove_managed_include(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == INCLUDE_BEGIN:
            skipping = True
            continue
        if line.strip() == INCLUDE_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"
