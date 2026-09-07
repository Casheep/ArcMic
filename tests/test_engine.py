import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arcmic import engine


class EngineSafetyTests(unittest.TestCase):
    def test_endpoint_access_requests_values_only(self):
        self.assertTrue(engine.ENDPOINT_VALUE_ACCESS & engine.winreg.KEY_SET_VALUE)
        self.assertTrue(engine.ENDPOINT_VALUE_ACCESS & engine.winreg.KEY_QUERY_VALUE)
        self.assertFalse(engine.ENDPOINT_VALUE_ACCESS & engine.winreg.KEY_CREATE_SUB_KEY)

    def test_binary_registry_value_is_json_safe_and_reversible(self):
        record = engine._json_value(b"\x00\x7f\xff", 3)
        self.assertEqual(record["kind"], "bytes")
        self.assertEqual(record["value"], "007fff")

        with patch.object(engine.winreg, "SetValueEx") as set_value:
            engine._restore_value(object(), "binary", record)
        self.assertEqual(set_value.call_args.args[-1], b"\x00\x7f\xff")

    def test_missing_registry_value_is_removed_on_restore(self):
        with patch.object(engine.winreg, "DeleteValue") as delete_value:
            engine._restore_value(object(), "temporary", {"present": False})
        delete_value.assert_called_once()

    def test_audio_service_restart_failure_is_not_silently_ignored(self):
        completed = subprocess.CompletedProcess([], 1)
        with patch.object(engine.subprocess, "run", return_value=completed):
            with self.assertRaises(RuntimeError):
                engine._restart_audio_service()

    def test_audio_service_update_failure_is_not_silently_ignored(self):
        completed = subprocess.CompletedProcess([], 1)
        with patch.object(engine.subprocess, "run", return_value=completed):
            with self.assertRaises(RuntimeError):
                engine._set_audio_service("Stop-Service")

    def test_outdated_rnnoise_payload_requires_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "rnnoise_mono.dll"
            plugin.write_bytes(b"old plugin")
            self.assertFalse(engine._rnnoise_current(plugin))

    def test_bundled_rnnoise_hash_matches_release(self):
        plugin = Path(__file__).parents[1] / "vendor" / "rnnoise" / "rnnoise_mono.dll"
        self.assertEqual(engine._file_sha256(plugin), engine.RNNOISE_SHA256)

    def test_elevated_frozen_process_starts_with_fresh_pyinstaller_environment(self):
        variable = "PYINSTALLER_RESET_ENVIRONMENT"
        observed = []

        def launch(_info):
            observed.append(os.environ.get(variable))
            return True

        info = engine.SHELLEXECUTEINFOW()
        with patch.dict(os.environ, {variable: "previous"}, clear=False):
            with patch.object(engine.ctypes.windll.shell32, "ShellExecuteExW", side_effect=launch):
                self.assertTrue(engine._shell_execute_elevated(info, reset_frozen_environment=True))
            self.assertEqual(os.environ[variable], "previous")

        self.assertEqual(observed, ["1"])


if __name__ == "__main__":
    unittest.main()
