import math
import unittest

from arcmic.config import NOISE_MODES
from arcmic.ui import GainDial, NOISE_MODE_LABELS, NOISE_MODE_ORDER


class GainDialGeometryTests(unittest.TestCase):
    def test_every_noise_mode_is_visible_in_the_selector(self):
        self.assertEqual(set(NOISE_MODE_ORDER), set(NOISE_MODES))
        self.assertEqual(set(NOISE_MODE_LABELS), set(NOISE_MODES))

    def test_thumb_stays_on_arc_centreline(self):
        for value in (0, 6, 12, 20, 30):
            x, y = GainDial.point_for_value(value)
            distance = math.hypot(x - GainDial.CENTER[0], y - GainDial.CENTER[1])
            self.assertAlmostEqual(distance, GainDial.RADIUS, places=7)

    def test_pointer_mapping_round_trips_arc_positions(self):
        for value in (0, 6, 12, 20, 30):
            x, y = GainDial.point_for_value(value)
            self.assertAlmostEqual(GainDial.value_from_point(x, y), value, places=7)

    def test_pointer_just_beyond_zero_endpoint_does_not_wrap_to_maximum(self):
        angle = math.radians(GainDial.START + 1)
        x = GainDial.CENTER[0] + GainDial.RADIUS * math.cos(angle)
        y = GainDial.CENTER[1] - GainDial.RADIUS * math.sin(angle)
        self.assertEqual(GainDial.value_from_point(x, y), 0.0)

    def test_gap_snaps_to_nearest_endpoint(self):
        def point_at(angle_degrees):
            angle = math.radians(angle_degrees)
            return (
                GainDial.CENTER[0] + GainDial.RADIUS * math.cos(angle),
                GainDial.CENTER[1] - GainDial.RADIUS * math.sin(angle),
            )

        self.assertEqual(GainDial.value_from_point(*point_at(GainDial.START + 30)), 0.0)
        self.assertEqual(
            GainDial.value_from_point(*point_at(GainDial.START + GainDial.SPAN - 30)),
            30.0,
        )


if __name__ == "__main__":
    unittest.main()
