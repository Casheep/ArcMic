import unittest

from arcmic.graphics import gain_dial, level_meter, meter_level_from_amplitude, pill_switch, rounded_panel, status_dot


class GraphicsTests(unittest.TestCase):
    def test_renderers_keep_requested_pixel_size(self):
        self.assertEqual(rounded_panel(121, 47, 12, fill="#ffffff", background="#000000").size, (121, 47))
        self.assertEqual(pill_switch(52, 30, 1.0, True, background="#ffffff", accent="#506cf5").size, (52, 30))
        self.assertEqual(level_meter(311, 18, 1.0, 0.5, background="#ffffff", track="#eeeeee", colour="#20b97a").size, (311, 18))
        self.assertEqual(status_dot(12, 1.0, background="#ffffff", colour="#20b97a").size, (12, 12))
        self.assertEqual(
            gain_dial(
                286,
                252,
                1.0,
                12,
                30,
                background="#ffffff",
                track="#eeeeee",
                colour="#506cf5",
                start=210,
                span=-240,
                centre=(143, 129),
                radius=111,
            ).size,
            (286, 252),
        )

    def test_supersampling_creates_smooth_edge_pixels(self):
        image = pill_switch(52, 30, 1.0, True, background="#ffffff", accent="#506cf5").convert("RGB")
        exact = {(255, 255, 255), (80, 108, 245)}
        self.assertTrue(any(pixel not in exact for pixel in image.getdata()))

    def test_rounded_panel_keeps_corner_background_and_centre_fill(self):
        image = rounded_panel(100, 50, 16, fill="#ffffff", background="#123456").convert("RGB")
        self.assertEqual(image.getpixel((0, 0)), (18, 52, 86))
        self.assertEqual(image.getpixel((50, 25)), (255, 255, 255))

    def test_dial_stroke_is_centred_on_pointer_radius(self):
        image = gain_dial(
            286,
            252,
            1.0,
            0,
            30,
            background="#ffffff",
            track="#e1e5ed",
            colour="#506cf5",
            start=210,
            span=-240,
            centre=(143, 129),
            radius=111,
        ).convert("RGB")
        self.assertEqual(image.getpixel((143, 18)), (225, 229, 237))
        self.assertEqual(image.getpixel((143, 34)), (255, 255, 255))

    def test_volume_meter_uses_decibel_scale(self):
        self.assertEqual(meter_level_from_amplitude(0.0), 0.0)
        self.assertEqual(meter_level_from_amplitude(1.0), 1.0)
        self.assertAlmostEqual(meter_level_from_amplitude(0.1), 2 / 3, places=6)

    def test_full_volume_fills_the_complete_meter_track(self):
        image = level_meter(
            311,
            18,
            1.0,
            1.0,
            background="#ffffff",
            track="#e1e5ed",
            colour="#20b97a",
        ).convert("RGB")
        self.assertEqual(image.getpixel((8, 9)), (32, 185, 122))
        self.assertEqual(image.getpixel((302, 9)), (32, 185, 122))

    def test_partial_volume_has_a_semicircular_leading_end(self):
        image = level_meter(
            200,
            18,
            1.0,
            0.5,
            background="#ffffff",
            track="#e1e5ed",
            colour="#20b97a",
        ).convert("RGB")
        # The green segment ends as a half circle: its centre reaches farther
        # right than its top edge.
        centre = image.getpixel((99, 9))
        top = image.getpixel((99, 2))
        self.assertGreater(centre[1], centre[0] + 100)
        self.assertNotEqual(top, centre)


if __name__ == "__main__":
    unittest.main()
