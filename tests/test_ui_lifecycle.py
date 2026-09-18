import unittest
from unittest.mock import Mock, patch

from arcmic.config import AppSettings
from arcmic.ui import ArcMicApp


class AppLifecycleTests(unittest.TestCase):
    def test_close_exits_instead_of_hiding_to_tray(self):
        app = object.__new__(ArcMicApp)
        app._exiting = False
        app.demo = False
        app.monitor = Mock()
        app.store = Mock()
        app.settings = AppSettings()
        app._tray_icon = None
        app.root = Mock()

        with patch("arcmic.ui.write_managed_config", side_effect=OSError("locked")):
            app.close()

        app.monitor.stop.assert_called_once_with()
        app.root.destroy.assert_called_once_with()
        self.assertTrue(app._exiting)


if __name__ == "__main__":
    unittest.main()
