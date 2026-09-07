import sys
import types
import unittest
from unittest.mock import patch

from arcmic.devices import (
    CaptureDevice,
    choose_default_device,
    choose_monitor_output,
    device_match_score,
    refresh_wasapi_devices,
)


class DeviceMatchingTests(unittest.TestCase):
    def test_refresh_restarts_portaudio_before_reading_defaults(self):
        calls = []
        fake = types.SimpleNamespace(
            _terminate=lambda: calls.append("stop"),
            _initialize=lambda: calls.append("start"),
        )
        with patch.dict(sys.modules, {"sounddevice": fake}), patch(
            "arcmic.devices.get_wasapi_devices", return_value=([], "", None, 9)
        ):
            result = refresh_wasapi_devices()
        self.assertEqual(calls, ["stop", "start"])
        self.assertEqual(result[3], 9)

    def test_monitor_uses_windows_default_without_saved_override(self):
        outputs = [
            {"index": 2, "name": "Speakers (USB DAC)", "channels": 2},
            {"index": 8, "name": "Headphones (Realtek USB Audio)", "channels": 2},
        ]
        self.assertEqual(choose_monitor_output(outputs, default_index=2)["index"], 2)

    def test_saved_monitor_output_wins(self):
        outputs = [
            {"index": 2, "name": "Headphones (Realtek)", "channels": 2},
            {"index": 8, "name": "Speakers (Example USB DAC)", "channels": 2},
        ]
        self.assertEqual(choose_monitor_output(outputs, "Speakers (Example USB DAC)", 2)["index"], 8)

    def test_prefers_matching_usb_microphone(self):
        usb = CaptureDevice("{usb}", "Microphone", "USB PnP Audio Device", 1)
        realtek = CaptureDevice("{realtek}", "Microphone", "Realtek USB Audio", 1)
        chosen = choose_default_device([realtek, usb], "Microphone (3- USB PnP Audio Device)")
        self.assertEqual(chosen, usb)

    def test_number_prefix_does_not_break_match(self):
        device = CaptureDevice("{usb}", "Microphone", "USB PnP Audio Device", 1)
        self.assertGreater(device_match_score(device, "Microphone (3- USB PnP Audio Device)"), 0.5)

    def test_empty_collection_has_no_default(self):
        self.assertIsNone(choose_default_device([], "anything"))


if __name__ == "__main__":
    unittest.main()
