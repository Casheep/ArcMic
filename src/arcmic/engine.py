from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from .config import (
    INCLUDE_BEGIN,
    equalizer_config_dir,
    local_app_dir,
    patch_main_config,
    program_data_dir,
    remove_managed_include,
)
from .devices import CAPTURE_ROOT, CaptureDevice, list_capture_devices


PRE_MIX_GUID = "{eacd2258-fcac-4ff4-b36d-419e924a6d79}"
EAPO_ROOT = r"SOFTWARE\EqualizerAPO"
CHILD_APOS = EAPO_ROOT + r"\Child APOs"
AUDIO_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Audio"
FX_NAMES = {
    "lfx": "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},1",
    "gfx": "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},2",
    "sfx": "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},5",
    "mfx": "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},6",
    "efx": "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},7",
}
SFX_MODES = "{d3993a3f-99c2-4402-b5ec-a92a0367664b},5"
DEFAULT_MODE = "{C18E2F7E-933D-4965-B7D1-1EEF228D2AF3}"
CAPTURE_PROCESSING_MODES = [
    DEFAULT_MODE,
    "{4780004E-7133-41D8-8C74-660DADD2C0EE}",  # Media
    "{FC1CFC9B-B9D6-4CFA-B5E0-4BB2166878B2}",  # Speech
    "{98951333-B9CD-48B1-A0A3-FF40682D73F7}",  # Communications
]
DISABLE_ENHANCEMENTS = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
ENGINE_FILES = (
    "EqualizerAPO.dll",
    "fftw3f.dll",
    "sndfile.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
)
ENDPOINT_VALUE_ACCESS = winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
RNNOISE_SHA256 = "664ce729baca985652c24515593e43a7c0105f7a0fb64e75b6b90776b9bd6495"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _read_reg_string(root: int, path: str, name: str) -> str:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return ""


def get_eapo_paths() -> tuple[Path | None, Path | None]:
    install = _read_reg_string(winreg.HKEY_LOCAL_MACHINE, EAPO_ROOT, "InstallPath")
    config = _read_reg_string(winreg.HKEY_LOCAL_MACHINE, EAPO_ROOT, "ConfigPath")
    return (Path(install) if install else None, Path(config) if config else None)


def engine_registered() -> bool:
    clsid = rf"CLSID\{PRE_MIX_GUID}\InprocServer32"
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, clsid, 0, winreg.KEY_READ) as key:
            target = str(winreg.QueryValueEx(key, "")[0])
            return bool(target) and Path(target).exists()
    except OSError:
        return False


def endpoint_bound(guid: str) -> bool:
    key_path = CAPTURE_ROOT + rf"\{guid}\FxProperties"
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, access) as key:
            for name in (FX_NAMES["sfx"], FX_NAMES["lfx"]):
                try:
                    if str(winreg.QueryValueEx(key, name)[0]).casefold() == PRE_MIX_GUID.casefold():
                        return True
                except OSError:
                    pass
    except OSError:
        pass
    return False


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rnnoise_current(path: Path) -> bool:
    try:
        return _file_sha256(path) == RNNOISE_SHA256
    except OSError:
        return False


def installation_ready(guid: str) -> bool:
    _, config_path = get_eapo_paths()
    plugin = program_data_dir() / "engine" / "rnnoise_mono.dll"
    main_config = (config_path / "config.txt") if config_path else None
    include_ok = False
    if main_config:
        try:
            content = main_config.read_text(encoding="utf-8-sig")
            expected = f"Include: {equalizer_config_dir() / 'ArcMic.txt'}"
            include_ok = INCLUDE_BEGIN in content and expected in content
        except OSError:
            pass
    return engine_registered() and _rnnoise_current(plugin) and endpoint_bound(guid) and include_ok


def _json_value(value: object, value_type: int) -> dict:
    if isinstance(value, bytes):
        encoded: object = value.hex()
        kind = "bytes"
    else:
        encoded = value
        kind = "plain"
    return {"present": True, "type": value_type, "kind": kind, "value": encoded}


def _capture_value(key: winreg.HKEYType, name: str) -> dict:
    try:
        value, value_type = winreg.QueryValueEx(key, name)
        return _json_value(value, value_type)
    except OSError:
        return {"present": False}


def _capture_registry_group(root: int, path: str, names: tuple[str, ...]) -> dict:
    record = {"key_present": False, "values": {name: {"present": False} for name in names}}
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            record["key_present"] = True
            record["values"] = {name: _capture_value(key, name) for name in names}
    except OSError:
        pass
    return record


def _restore_value(key: winreg.HKEYType, name: str, record: dict) -> None:
    if not record.get("present"):
        try:
            winreg.DeleteValue(key, name)
        except OSError:
            pass
        return
    value = record.get("value")
    if record.get("kind") == "bytes":
        value = bytes.fromhex(str(value))
    winreg.SetValueEx(key, name, 0, int(record["type"]), value)


def _restore_registry_group(root: int, path: str, record: dict) -> None:
    values = record.get("values", {}) if isinstance(record, dict) else {}
    if values:
        access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
        with winreg.CreateKeyEx(root, path, 0, access) as key:
            for name, value_record in values.items():
                _restore_value(key, name, value_record)
    if isinstance(record, dict) and not record.get("key_present"):
        try:
            winreg.DeleteKeyEx(root, path, winreg.KEY_WOW64_64KEY, 0)
        except OSError:
            pass


def _load_state() -> dict:
    try:
        return json.loads((program_data_dir() / "install-state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"engine_owned": False, "bindings": {}}


def _save_state(state: dict) -> None:
    path = program_data_dir() / "install-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_engine_payload(target: Path) -> None:
    source = resource_path("vendor", "engine")
    target.mkdir(parents=True, exist_ok=True)
    for name in ENGINE_FILES:
        shutil.copy2(source / name, target / name)
    shutil.copy2(resource_path("vendor", "rnnoise", "rnnoise_mono.dll"), target / "rnnoise_mono.dll")


def _install_minimal_eapo(engine_dir: Path, config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    main_config = config_dir / "config.txt"
    if not main_config.exists():
        main_config.write_text("# ArcMic Equalizer APO configuration\n", encoding="utf-8")

    access = winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, EAPO_ROOT, 0, access) as key:
        winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, str(engine_dir))
        winreg.SetValueEx(key, "ConfigPath", 0, winreg.REG_SZ, str(config_dir))
        winreg.SetValueEx(key, "EnableTrace", 0, winreg.REG_SZ, "false")
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, AUDIO_ROOT, 0, access) as key:
        winreg.SetValueEx(key, "DisableProtectedAudioDG", 0, winreg.REG_DWORD, 1)

    completed = subprocess.run(
        [str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "regsvr32.exe"), "/s", str(engine_dir / "EqualizerAPO.dll")],
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"音频处理器注册失败（代码 {completed.returncode}）")


def _bind_endpoint(device: CaptureDevice, state: dict, install_mode: str = "sfx") -> None:
    if install_mode not in ("sfx", "lfx"):
        raise ValueError(f"unsupported install mode: {install_mode}")
    fx_path = CAPTURE_ROOT + rf"\{device.guid}\FxProperties"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fx_path, 0, ENDPOINT_VALUE_ACCESS) as fx:
        binding = state.setdefault("bindings", {}).get(device.guid)
        if binding and binding.get("managed") and isinstance(binding.get("backup"), dict):
            backup = binding["backup"]
        else:
            names = list(FX_NAMES.values()) + [SFX_MODES, DISABLE_ENHANCEMENTS]
            backup = {name: _capture_value(fx, name) for name in names}
            binding = {
                "label": device.label,
                "backup": backup,
                "managed": True,
            }
            state["bindings"][device.guid] = binding
            # Persist the exact original endpoint values before changing any of them.
            _save_state(state)

        if install_mode == "sfx":
            delete_names = (FX_NAMES["lfx"], FX_NAMES["gfx"])
            target_name = FX_NAMES["sfx"]
        else:
            delete_names = (FX_NAMES["sfx"], FX_NAMES["mfx"], FX_NAMES["efx"])
            target_name = FX_NAMES["lfx"]
        for name in delete_names:
            try:
                winreg.DeleteValue(fx, name)
            except OSError:
                pass
        winreg.SetValueEx(fx, target_name, 0, winreg.REG_SZ, PRE_MIX_GUID)
        if install_mode == "sfx":
            winreg.SetValueEx(fx, SFX_MODES, 0, winreg.REG_MULTI_SZ, CAPTURE_PROCESSING_MODES)
        elif install_mode == "lfx":
            try:
                winreg.DeleteValue(fx, SFX_MODES)
            except OSError:
                pass
        try:
            winreg.DeleteValue(fx, DISABLE_ENHANCEMENTS)
        except OSError:
            pass

        binding["install_mode"] = install_mode

    preferred_original = backup[FX_NAMES["sfx" if install_mode == "sfx" else "lfx"]]
    child = str(preferred_original.get("value", "")) if preferred_original.get("present") else ""

    child_path = CHILD_APOS + rf"\{device.guid}"
    child_access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, child_path, 0, child_access) as child_key:
        for name in FX_NAMES.values():
            record = backup[name]
            marker = str(record.get("value", "!VALUE")) if record.get("present") else "!VALUE"
            winreg.SetValueEx(child_key, name, 0, winreg.REG_SZ, marker)
        winreg.SetValueEx(child_key, "PreMixChild", 0, winreg.REG_SZ, child)
        winreg.SetValueEx(child_key, "PostMixChild", 0, winreg.REG_SZ, "")
        winreg.SetValueEx(child_key, "AllowSilentBufferModification", 0, winreg.REG_SZ, "false")
        winreg.SetValueEx(child_key, "Version", 0, winreg.REG_SZ, "2")


def _restart_audio_service() -> None:
    command = "Restart-Service -Name Audiosrv -Force -ErrorAction Stop"
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if completed.returncode:
        raise RuntimeError(f"Windows 音频服务重启失败（代码 {completed.returncode}）")


def _set_audio_service(command: str) -> None:
    force = " -Force" if command == "Stop-Service" else ""
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"{command} -Name Audiosrv{force} -ErrorAction Stop",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if completed.returncode:
        raise RuntimeError(f"Windows 音频服务更新准备失败（代码 {completed.returncode}）")


def install_or_repair(device_guid: str = "", install_mode: str = "sfx") -> int:
    if not is_admin():
        return 5
    state = _load_state()
    engine_dir = program_data_dir() / "engine"
    installed_plugin = engine_dir / "rnnoise_mono.dll"
    stop_for_plugin_update = engine_registered() and not _rnnoise_current(installed_plugin)
    if stop_for_plugin_update:
        # A VST DLL loaded by audiodg cannot be replaced in place. Stop only
        # for the short payload copy and always bring audio back on failure.
        _set_audio_service("Stop-Service")
        try:
            _copy_engine_payload(engine_dir)
        finally:
            _set_audio_service("Start-Service")
    else:
        _copy_engine_payload(engine_dir)

    install_path, config_path = get_eapo_paths()
    if not engine_registered() or install_path is None or config_path is None:
        if not state.get("engine_owned"):
            state["minimal_backup"] = {
                "eapo": _capture_registry_group(
                    winreg.HKEY_LOCAL_MACHINE,
                    EAPO_ROOT,
                    ("InstallPath", "ConfigPath", "EnableTrace"),
                ),
                "audio": _capture_registry_group(
                    winreg.HKEY_LOCAL_MACHINE,
                    AUDIO_ROOT,
                    ("DisableProtectedAudioDG",),
                ),
            }
        state["engine_owned"] = True
        # Save the rollback information before changing machine-wide values.
        _save_state(state)
        config_path = program_data_dir() / "config"
        _install_minimal_eapo(engine_dir, config_path)
    else:
        state.setdefault("engine_owned", False)

    assert config_path is not None
    managed = config_path / "ArcMic.txt"
    managed.parent.mkdir(parents=True, exist_ok=True)
    if not managed.exists():
        managed.write_text("# ArcMic is waiting for the first settings update.\n", encoding="utf-8")
    main_config = config_path / "config.txt"
    existing = main_config.read_text(encoding="utf-8-sig") if main_config.exists() else ""
    main_config.parent.mkdir(parents=True, exist_ok=True)
    main_config.write_text(patch_main_config(existing, managed), encoding="utf-8")

    devices = list_capture_devices(active_only=True)
    selected = [device for device in devices if device.guid.casefold() == device_guid.casefold()]
    targets = selected or devices[:1]
    for device in targets:
        _bind_endpoint(device, state, install_mode)

    _save_state(state)
    _restart_audio_service()
    try:
        (local_app_dir() / "setup-error.txt").unlink(missing_ok=True)
    except OSError:
        pass
    return 0


def set_diagnostic_trace(enabled: bool) -> int:
    if not is_admin():
        return 5
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, EAPO_ROOT, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key, "EnableTrace", 0, winreg.REG_SZ, "true" if enabled else "false")
    _restart_audio_service()
    return 0


def restore_system() -> int:
    if not is_admin():
        return 5
    state = _load_state()
    for guid, binding in state.get("bindings", {}).items():
        if not binding.get("managed"):
            continue
        fx_path = CAPTURE_ROOT + rf"\{guid}\FxProperties"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fx_path, 0, ENDPOINT_VALUE_ACCESS) as fx:
                for name, record in binding.get("backup", {}).items():
                    _restore_value(fx, name, record)
        except OSError:
            continue
        try:
            winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, CHILD_APOS + rf"\{guid}", winreg.KEY_WOW64_64KEY, 0)
        except OSError:
            pass

    _, config_path = get_eapo_paths()
    if config_path:
        main = config_path / "config.txt"
        try:
            main.write_text(remove_managed_include(main.read_text(encoding="utf-8-sig")), encoding="utf-8")
        except OSError:
            pass

    if state.get("engine_owned"):
        engine_dll = program_data_dir() / "engine" / "EqualizerAPO.dll"
        if engine_dll.exists():
            subprocess.run(
                [
                    str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "regsvr32.exe"),
                    "/u",
                    "/s",
                    str(engine_dll),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        backup = state.get("minimal_backup", {})
        eapo_backup = backup.get("eapo", {}) if isinstance(backup, dict) else {}
        if not eapo_backup.get("key_present"):
            try:
                winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, CHILD_APOS, winreg.KEY_WOW64_64KEY, 0)
            except OSError:
                pass
        _restore_registry_group(winreg.HKEY_LOCAL_MACHINE, EAPO_ROOT, eapo_backup)
        audio_backup = backup.get("audio", {}) if isinstance(backup, dict) else {}
        if audio_backup:
            _restore_registry_group(winreg.HKEY_LOCAL_MACHINE, AUDIO_ROOT, audio_backup)

    state["bindings"] = {}
    state["engine_owned"] = False
    _save_state(state)
    _restart_audio_service()
    return 0


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def _shell_execute_elevated(info: SHELLEXECUTEINFOW, reset_frozen_environment: bool) -> bool:
    """Start the elevated process without reusing a one-file parent runtime."""
    variable = "PYINSTALLER_RESET_ENVIRONMENT"
    previous = os.environ.get(variable)
    if reset_frozen_environment:
        os.environ[variable] = "1"
    try:
        return bool(ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)))
    finally:
        if reset_frozen_environment:
            if previous is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = previous


def run_elevated_and_wait(arguments: list[str]) -> int:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        executable = sys.executable
        params = subprocess.list2cmdline(arguments)
        directory = str(Path(sys.executable).parent)
    else:
        executable = sys.executable
        entry = Path(__file__).resolve().parents[2] / "run_arcmic.py"
        params = subprocess.list2cmdline([str(entry), *arguments])
        directory = str(entry.parent)

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = executable
    info.lpParameters = params
    info.lpDirectory = directory
    info.nShow = 0
    if not _shell_execute_elevated(info, reset_frozen_environment=frozen):
        return int(ctypes.windll.kernel32.GetLastError()) or 1
    try:
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 120_000)
        exit_code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
        return int(exit_code.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)
