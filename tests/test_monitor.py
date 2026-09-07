import struct
import sys
import types
import unittest
from unittest.mock import patch

from arcmic.monitor import AudioMonitor


class _FakeRawStream:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


class MonitorTests(unittest.TestCase):
    def test_monitor_requires_a_real_output_device(self):
        monitor = AudioMonitor(lambda _level: None)
        with self.assertRaises(RuntimeError):
            monitor.start(4, None, monitoring=True)

    def test_monitor_requires_a_real_input_device(self):
        monitor = AudioMonitor(lambda _level: None)
        with self.assertRaises(RuntimeError):
            monitor.start(None, 7, monitoring=True)

    def test_headphone_monitor_duplicates_mono_input_to_stereo(self):
        def query_device(index):
            if index == 4:
                return {"default_samplerate": 48_000, "max_input_channels": 1}
            return {"default_samplerate": 96_000, "max_output_channels": 2}

        fake_sounddevice = types.SimpleNamespace(
            query_devices=query_device,
            RawInputStream=_FakeRawStream,
            RawOutputStream=_FakeRawStream,
        )
        levels = []
        monitor = AudioMonitor(levels.append)
        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            monitor.start(4, 7, monitoring=True)

        source = bytearray(struct.pack("4h", 1000, 1000, 1000, 1000))
        output = bytearray(8 * 2 * 2)
        monitor._input_stream.callback(source, 4, None, None)
        monitor._output_stream.callback(output, 8, None, None)
        values = struct.unpack("16h", output)

        self.assertEqual(values[0], 1000)
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[2], values[3])
        self.assertEqual(values[4], values[5])
        self.assertEqual(values[6], values[7])
        self.assertTrue(monitor.monitoring)
        self.assertTrue(levels)
        monitor.stop()
        self.assertFalse(monitor.running)


if __name__ == "__main__":
    unittest.main()
