from __future__ import annotations

import re
import winreg
from dataclasses import dataclass
from difflib import SequenceMatcher


CAPTURE_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
CONNECTION_NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
DEVICE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"


@dataclass(frozen=True, slots=True)
class CaptureDevice:
    guid: str
    connection_name: str
    device_name: str
    state: int

    @property
    def label(self) -> str:
        connection = self.connection_name.strip() or "麦克风"
        device = self.device_name.strip()
        if device and device.casefold() not in connection.casefold():
            return f"{connection} · {device}"
        return connection


def _read_value(key: winreg.HKEYType, name: str, default: object = "") -> object:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def list_capture_devices(active_only: bool = True) -> list[CaptureDevice]:
    devices: list[CaptureDevice] = []
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CAPTURE_ROOT, 0, access)
    except OSError:
        return devices

    with root:
        index = 0
        while True:
            try:
                guid = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            try:
                endpoint = winreg.OpenKey(root, guid, 0, access)
                with endpoint:
                    state = int(_read_value(endpoint, "DeviceState", 0))
                if active_only and not (state & 0x1):
                    continue
                properties = winreg.OpenKey(root, guid + r"\Properties", 0, access)
                with properties:
                    connection = str(_read_value(properties, CONNECTION_NAME, "Microphone"))
                    device = str(_read_value(properties, DEVICE_NAME, ""))
                devices.append(CaptureDevice(guid, connection, device, state))
            except (OSError, ValueError):
                continue
    return sorted(devices, key=lambda item: item.label.casefold())


def _normalise_name(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\b(microphone|mic|麦克风|input|device|default|communications?)\b", " ", value)
    value = re.sub(r"[^\w]+", " ", value)
    return " ".join(value.split())


def device_match_score(device: CaptureDevice, audio_name: str) -> float:
    left = _normalise_name(device.label)
    right = _normalise_name(audio_name)
    if not left or not right:
        return 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    containment = 1.0 if left in right or right in left else 0.0
    return ratio * 0.45 + overlap * 0.40 + containment * 0.15


def choose_default_device(devices: list[CaptureDevice], audio_name: str) -> CaptureDevice | None:
    if not devices:
        return None
    return max(devices, key=lambda device: device_match_score(device, audio_name))


def get_wasapi_devices() -> tuple[list[dict], str, int | None, int | None]:
    """Return WASAPI input devices, default input name/index and default output index."""
    try:
        import sounddevice as sd

        hostapis = sd.query_hostapis()
        wasapi_index = next(
            (index for index, api in enumerate(hostapis) if "WASAPI" in api["name"]),
            None,
        )
        if wasapi_index is None:
            return [], "", None, None
        api = hostapis[wasapi_index]
        all_devices = sd.query_devices()
        inputs = [
            {"index": index, "name": item["name"], "channels": int(item["max_input_channels"])}
            for index, item in enumerate(all_devices)
            if item["hostapi"] == wasapi_index and item["max_input_channels"] > 0
        ]
        default_in = int(api["default_input_device"])
        default_out = int(api["default_output_device"])
        default_name = all_devices[default_in]["name"] if default_in >= 0 else ""
        return inputs, default_name, default_in if default_in >= 0 else None, default_out if default_out >= 0 else None
    except Exception:
        return [], "", None, None


def refresh_wasapi_devices() -> tuple[list[dict], str, int | None, int | None]:
    """Refresh PortAudio so a recently changed Windows default is observed."""
    try:
        import sounddevice as sd

        terminate = getattr(sd, "_terminate", None)
        initialize = getattr(sd, "_initialize", None)
        if callable(terminate) and callable(initialize):
            terminate()
            initialize()
    except Exception:
        pass
    return get_wasapi_devices()


def list_wasapi_outputs() -> list[dict]:
    try:
        import sounddevice as sd

        hostapis = sd.query_hostapis()
        wasapi_index = next((index for index, api in enumerate(hostapis) if "WASAPI" in api["name"]), None)
        if wasapi_index is None:
            return []
        return [
            {"index": index, "name": item["name"], "channels": int(item["max_output_channels"])}
            for index, item in enumerate(sd.query_devices())
            if item["hostapi"] == wasapi_index and item["max_output_channels"] > 0
        ]
    except Exception:
        return []


def choose_monitor_output(outputs: list[dict], preferred_name: str = "", default_index: int | None = None) -> dict | None:
    if not outputs:
        return None
    if preferred_name:
        exact = next((item for item in outputs if str(item["name"]).casefold() == preferred_name.casefold()), None)
        if exact:
            return exact
    default = next((item for item in outputs if int(item["index"]) == default_index), None)
    return default or outputs[0]


def match_wasapi_index(device: CaptureDevice, wasapi_inputs: list[dict]) -> int | None:
    if not wasapi_inputs:
        return None
    best = max(wasapi_inputs, key=lambda item: device_match_score(device, str(item["name"])))
    return int(best["index"])
