import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arcmic.config import (
    AppSettings,
    INCLUDE_BEGIN,
    INCLUDE_END,
    patch_main_config,
    remove_managed_include,
    render_eapo_config,
    write_managed_config,
)


class ConfigTests(unittest.TestCase):
    def test_ai_chain_orders_noise_before_gain(self):
        settings = AppSettings(
            enabled=True,
            noise_mode="ai",
            gain_db=9.5,
            device_guid="{11111111-1111-1111-1111-111111111111}",
        )
        rendered = render_eapo_config(settings, Path(r"C:\ProgramData\ArcMic\engine\rnnoise_mono.dll"))
        self.assertIn("Device: {11111111-1111-1111-1111-111111111111}", rendered)
        self.assertLess(rendered.index("Filter:"), rendered.index("VSTPlugin:"))
        self.assertLess(rendered.index("VSTPlugin:"), rendered.index("Preamp:"))
        self.assertIn("Preamp: 9.5 dB", rendered)

    def test_natural_mode_preserves_voice_without_ai(self):
        settings = AppSettings(enabled=True, noise_mode="natural", gain_db=6, device_guid="{x}")
        rendered = render_eapo_config(settings, Path("plugin.dll"))
        self.assertIn("HPQ Fc 75 Hz", rendered)
        self.assertIn("LPQ Fc 14000 Hz", rendered)
        self.assertNotIn("VSTPlugin:", rendered)

    def test_hum_mode_uses_narrow_mains_filters_without_ai(self):
        settings = AppSettings(enabled=True, noise_mode="hum", gain_db=12, device_guid="{x}")
        rendered = render_eapo_config(settings, Path("plugin.dll"))
        self.assertIn("HPQ Fc 75 Hz", rendered)
        self.assertIn("PK Fc 50 Hz Gain -24 dB Q 10", rendered)
        self.assertIn("PK Fc 100 Hz Gain -18 dB Q 18", rendered)
        self.assertIn("PK Fc 150 Hz Gain -12 dB Q 24", rendered)
        self.assertIn("PK Fc 200 Hz Gain -9 dB Q 28", rendered)
        self.assertIn("LPQ Fc 13500 Hz", rendered)
        self.assertNotIn("VSTPlugin:", rendered)

    def test_ai_hum_mode_filters_mains_before_new_ai(self):
        rendered = render_eapo_config(
            AppSettings(enabled=True, noise_mode="ai_hum", gain_db=12, device_guid="{x}"),
            Path(r"C:\rnnoise.dll"),
        )
        self.assertIn("PK Fc 50 Hz Gain -24 dB Q 10", rendered)
        self.assertIn("PK Fc 200 Hz Gain -9 dB Q 28", rendered)
        self.assertIn('VSTPlugin: Library "C:\\rnnoise.dll"', rendered)
        self.assertLess(rendered.index("PK Fc 50 Hz"), rendered.index("VSTPlugin:"))
        self.assertLess(rendered.index("VSTPlugin:"), rendered.index("Preamp:"))

    def test_off_noise_mode_only_applies_gain(self):
        settings = AppSettings(enabled=True, noise_mode="off", gain_db=6, device_guid="{x}")
        rendered = render_eapo_config(settings, Path("plugin.dll"))
        self.assertNotIn("Filter:", rendered)
        self.assertNotIn("VSTPlugin:", rendered)
        self.assertIn("Preamp: 6.0 dB", rendered)

    def test_disabled_chain_is_passthrough(self):
        rendered = render_eapo_config(AppSettings(enabled=False, device_guid="{x}"), Path("plugin.dll"))
        self.assertNotIn("Preamp:", rendered)
        self.assertNotIn("VSTPlugin:", rendered)

    def test_gain_is_clamped_to_safe_product_limit(self):
        settings = AppSettings(gain_db=99).normalized()
        self.assertEqual(settings.gain_db, 30.0)

    def test_unknown_noise_mode_falls_back_to_recommended_ai_hum(self):
        settings = AppSettings(noise_mode="unexpected").normalized()
        self.assertEqual(settings.noise_mode, "ai_hum")

    def test_live_config_falls_back_when_atomic_replace_is_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ArcMic.txt"
            target.write_text("old", encoding="utf-8")
            locked = PermissionError(13, "locked")
            locked.winerror = 5
            with patch("pathlib.Path.replace", side_effect=locked):
                write_managed_config(AppSettings(enabled=False), target)
            self.assertIn("Enhancement is off", target.read_text(encoding="utf-8"))
            self.assertFalse(target.with_suffix(".tmp").exists())

    def test_include_patch_is_idempotent_and_preserves_existing_config(self):
        source = "Include: peace.txt\nPreamp: -2 dB\n"
        path = Path(r"C:\Users\Example\AppData\Local\ArcMic\ArcMic.txt")
        once = patch_main_config(source, path)
        twice = patch_main_config(once, path)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(INCLUDE_BEGIN), 1)
        self.assertEqual(once.count(INCLUDE_END), 1)
        self.assertIn("Include: peace.txt", once)
        self.assertIn("Preamp: -2 dB", once)
        self.assertIn(f"Include: {path}", once)
        self.assertNotIn(f'Include: "{path}"', once)

    def test_include_can_be_removed_without_touching_other_filters(self):
        source = patch_main_config("Filter: ON HP Fc 40 Hz\n", Path(r"C:\ArcMic.txt"))
        restored = remove_managed_include(source)
        self.assertEqual(restored, "Filter: ON HP Fc 40 Hz\n")


if __name__ == "__main__":
    unittest.main()
