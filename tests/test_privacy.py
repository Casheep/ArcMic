import getpass
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrivacyTests(unittest.TestCase):
    def test_runtime_has_no_network_client_or_telemetry(self):
        runtime = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src" / "arcmic").glob("*.py"))
        forbidden = (
            "requests.",
            "urllib.request",
            "http.client",
            "socket.socket",
            "telemetry",
            "analytics",
        )
        for token in forbidden:
            self.assertNotIn(token, runtime.casefold(), token)

    def test_source_contains_no_local_username_or_hardware_identifier(self):
        scanned = []
        for path in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.ps1")):
            scanned.append(path.read_text(encoding="utf-8"))
        source = "\n".join(scanned).casefold()
        local_username = getpass.getuser().casefold()
        if len(local_username) >= 3:
            self.assertNotIn(local_username, source)
        self.assertNotRegex(source, re.compile(r"vid_[0-9a-f]{4}&pid_[0-9a-f]{4}"))


if __name__ == "__main__":
    unittest.main()
