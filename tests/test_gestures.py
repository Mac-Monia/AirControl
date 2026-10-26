"""Tests for AirControl's gesture logic, using synthetic hand landmarks.

Run from the project directory:
    python -m unittest discover tests
"""

import json
import math
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

import main  # noqa: E402

WIDTH, HEIGHT = 640, 480

# Knuckle x positions for the index, middle, ring and pinky fingers
KNUCKLE_X = (0.44, 0.50, 0.56, 0.62)

THUMBS = {
    # (middle joint, tip)
    "side": ((0.36, 0.66), (0.33, 0.62)),
    "out": ((0.37, 0.62), (0.31, 0.52)),
    "tucked": ((0.45, 0.66), (0.52, 0.62)),
}


def point(x, y, z=0.0):
    return SimpleNamespace(x=x, y=y, z=z)


def make_hand(fingers=("up", "up", "up", "up"), thumb="side",
              shift_x=0.0, shift_y=0.0):
    """An upright right hand: wrist at the bottom, fingers pointing up.
    Each finger is "up" (straight) or "down" (curled into the palm)."""
    points = [None] * 21
    points[0] = point(0.50, 0.80)
    points[1] = point(0.44, 0.75)
    points[2] = point(0.40, 0.70)
    (ip_x, ip_y), (tip_x, tip_y) = THUMBS[thumb]
    points[3] = point(ip_x, ip_y)
    points[4] = point(tip_x, tip_y)

    for finger, (state, x) in enumerate(zip(fingers, KNUCKLE_X)):
        base = 5 + 4 * finger
        points[base] = point(x, 0.60)
        if state == "up":
            ys = (0.52, 0.47, 0.42)
        else:
            ys = (0.53, 0.57, 0.62)
        for offset, y in enumerate(ys, start=1):
            points[base + offset] = point(x, y)

    return [point(p.x + shift_x, p.y + shift_y, p.z) for p in points]


def pose(points):
    hand_size, _ = main.measure_hand(points, WIDTH, HEIGHT)
    return main.classify_pose(points, hand_size, WIDTH, HEIGHT)


class PoseTests(unittest.TestCase):

    def test_palm(self):
        self.assertEqual(pose(make_hand()), "palm")

    def test_pointing_is_other(self):
        self.assertEqual(pose(make_hand(("up", "down", "down", "down"))), "other")

    def test_peace(self):
        self.assertEqual(pose(make_hand(("up", "up", "down", "down"))), "peace")

    def test_three(self):
        self.assertEqual(pose(make_hand(("up", "up", "up", "down"))), "three")

    def test_rock(self):
        self.assertEqual(pose(make_hand(("up", "down", "down", "up"))), "rock")

    def test_fist(self):
        hand = make_hand(("down",) * 4, thumb="tucked")
        self.assertEqual(pose(hand), "fist")

    def test_thumbs_up(self):
        hand = make_hand(("down",) * 4, thumb="out")
        self.assertEqual(pose(hand), "thumbs_up")

    def test_pinch_with_curled_fingers_is_not_a_fist(self):
        # Index bent down onto the thumb tip, other fingers curled.
        hand = make_hand(("up", "down", "down", "down"))
        hand[8] = point(0.335, 0.615)
        self.assertEqual(pose(hand), "pinch")


class RightPinchTests(unittest.TestCase):

    def test_middle_reaching_to_thumb(self):
        hand = make_hand(("up", "down", "down", "down"))
        # Middle finger bent forward so its tip meets the thumb tip.
        hand[10] = point(0.45, 0.55)
        hand[11] = point(0.38, 0.58)
        hand[12] = point(0.335, 0.615)
        hand_size, _ = main.measure_hand(hand, WIDTH, HEIGHT)
        ratio = main.right_pinch_ratio(hand, hand_size, WIDTH, HEIGHT)
        self.assertIsNotNone(ratio)
        self.assertLess(ratio, main.PINCH_START)

    def test_curled_middle_does_not_count(self):
        hand = make_hand(("up", "down", "down", "down"))
        hand_size, _ = main.measure_hand(hand, WIDTH, HEIGHT)
        self.assertIsNone(main.right_pinch_ratio(hand, hand_size, WIDTH, HEIGHT))

    def test_needs_index_up(self):
        hand = make_hand(("down",) * 4)
        hand_size, _ = main.measure_hand(hand, WIDTH, HEIGHT)
        self.assertIsNone(main.right_pinch_ratio(hand, hand_size, WIDTH, HEIGHT))


class ClickTests(unittest.TestCase):

    def setUp(self):
        main.reset_click()
        main.last_click_time = -math.inf
        main.last_left_click_time = -math.inf
        patcher = mock.patch.object(main.pyautogui, "click")
        self.click = patcher.start()
        self.addCleanup(patcher.stop)
        quiet = mock.patch("builtins.print")
        quiet.start()
        self.addCleanup(quiet.stop)

    def run_frames(self, ratio, right_ratio, frames, start, step=1 / 30):
        clicks = []
        for frame in range(frames):
            clicked = main.detect_click(ratio, right_ratio, start + frame * step)
            if clicked:
                clicks.append(clicked)
        return clicks, start + frames * step

    def test_pinch_clicks_once(self):
        clicks, _ = self.run_frames(0.1, None, 10, 0.0)
        self.assertEqual(clicks, ["left"])
        self.click.assert_called_once_with()

    def test_short_pinch_is_ignored(self):
        clicks, now = self.run_frames(0.1, None, 2, 0.0)
        clicks2, _ = self.run_frames(0.6, None, 5, now)
        self.assertEqual(clicks + clicks2, [])

    def test_two_quick_pinches_double_click(self):
        clicks, now = self.run_frames(0.1, None, 3, 0.0)
        more, now = self.run_frames(0.6, None, 3, now)
        clicks += more
        more, _ = self.run_frames(0.1, None, 3, now)
        clicks += more
        self.assertEqual(clicks, ["left", "double"])

    def test_slow_second_pinch_is_single_click(self):
        clicks, now = self.run_frames(0.1, None, 3, 0.0)
        more, now = self.run_frames(0.6, None, 3, now)
        clicks += more
        more, _ = self.run_frames(0.1, None, 3, now + 2.0)
        clicks += more
        self.assertEqual(clicks, ["left", "left"])

    def test_middle_pinch_right_clicks(self):
        clicks, _ = self.run_frames(0.6, 0.1, 5, 0.0)
        self.assertEqual(clicks, ["right"])
        self.click.assert_called_once_with(button="right")

    def test_not_allowed_while_settling(self):
        for frame in range(5):
            self.assertIsNone(
                main.detect_click(0.1, None, frame / 30, allowed=False)
            )
        self.click.assert_not_called()


class SwipeTests(unittest.TestCase):

    def setUp(self):
        main.reset_swipe()
        main.last_swipe_time = -math.inf
        self.hand_size = 115.0

    def move(self, start_x, end_x, seconds, start_time, frames=10,
             start_y=0.5, end_y=None):
        end_y = start_y if end_y is None else end_y
        result = None
        for frame in range(frames + 1):
            t = frame / frames
            hand = make_hand(("up", "up", "up", "down"))
            hand[main.PALM_CENTER] = point(
                start_x + (end_x - start_x) * t,
                start_y + (end_y - start_y) * t
            )
            swipe = main.swipe_with(
                hand, self.hand_size, WIDTH, HEIGHT,
                start_time + seconds * t
            )
            result = result or swipe
        return result

    def test_fast_flick_left(self):
        self.assertEqual(self.move(0.7, 0.4, 0.2, 0.0), "swipe_left")

    def test_fast_flick_up(self):
        result = self.move(0.5, 0.5, 0.2, 0.0, start_y=0.7, end_y=0.35)
        self.assertEqual(result, "swipe_up")

    def test_slow_drift_is_ignored(self):
        self.assertIsNone(self.move(0.7, 0.4, 2.0, 0.0, frames=60))

    def test_return_stroke_is_blocked(self):
        self.assertEqual(self.move(0.7, 0.4, 0.2, 0.0), "swipe_left")
        self.assertIsNone(self.move(0.4, 0.7, 0.2, 0.3))

    def test_repeat_after_cooldown(self):
        self.assertEqual(self.move(0.7, 0.4, 0.2, 0.0), "swipe_left")
        self.assertEqual(self.move(0.7, 0.4, 0.2, 1.0), "swipe_left")


class HoldTriggerTests(unittest.TestCase):

    def test_fires_once_per_hold(self):
        hold = main.HoldTrigger()
        fired = [hold.update(True, t / 30, 0.5) for t in range(60)]
        self.assertEqual(fired.count(True), 1)
        self.assertEqual(fired.index(True), 15)

    def test_short_dropout_keeps_hold(self):
        hold = main.HoldTrigger()
        for t in range(10):
            hold.update(True, t / 30, 0.5)
        hold.update(False, 10 / 30, 0.5)  # one missed frame
        fired = [hold.update(True, t / 30, 0.5) for t in range(11, 20)]
        self.assertTrue(any(fired))

    def test_release_rearms(self):
        hold = main.HoldTrigger()
        for t in range(30):
            hold.update(True, t / 30, 0.5)
        hold.update(False, 2.0, 0.5)
        hold.update(False, 2.5, 0.5)
        fired = [hold.update(True, 3 + t / 30, 0.5) for t in range(30)]
        self.assertEqual(fired.count(True), 1)


class ActionTests(unittest.TestCase):

    def test_parse_hotkey(self):
        self.assertEqual(
            main.parse_action("Ctrl+Shift+Tab"),
            ("keys", ["ctrl", "shift", "tab"], 1)
        )

    def test_parse_repeat(self):
        self.assertEqual(
            main.parse_action("volumeup*5"), ("keys", ["volumeup"], 5)
        )

    def test_parse_special(self):
        self.assertEqual(main.parse_action("none"), ("none", None, 1))
        self.assertEqual(main.parse_action("mouse:double"), ("mouse", "double", 1))
        self.assertEqual(main.parse_action("profile:next"), ("profile", "next", 1))

    def test_parse_rejects_unknown(self):
        for spec in ("ctrl+nokey", "volumeup*0", "volumeup*x", "mouse:side"):
            with self.assertRaises(ValueError, msg=spec):
                main.parse_action(spec)

    def test_defaults_are_valid(self):
        _, warnings = main.build_gesture_actions(main.DEFAULT_GESTURES)
        self.assertEqual(warnings, [])

    def test_bad_entries_are_reported(self):
        gestures, _ = main.merge_gestures({
            "navigate": {
                "swipe_left": "badkey",
                "wave": "space",
                "thumbs_up": "profile:nowhere",
                "rock": None,
            }
        })
        actions, warnings = main.build_gesture_actions(gestures)
        self.assertEqual(len(warnings), 3)
        self.assertNotIn("swipe_left", actions["navigate"])
        self.assertEqual(actions["navigate"]["rock"]["parsed"][0], "none")

    def test_user_gestures_override_one_entry(self):
        gestures, _ = main.merge_gestures({"media": {"swipe_up": "volumeup"}})
        self.assertEqual(gestures["media"]["swipe_up"], "volumeup")
        self.assertEqual(
            gestures["media"]["swipe_down"],
            main.DEFAULT_GESTURES["media"]["swipe_down"]
        )


class SettingsTests(unittest.TestCase):

    def test_tuning_checks_types(self):
        saved = (main.SCROLL_SPEED, main.SCROLL_INVERT, main.BETA)
        try:
            warnings = main.apply_tuning({
                "SCROLL_SPEED": 3000,
                "SCROLL_INVERT": "yes",
                "BETA": 0.01,
                "SCREEN_W": 10,
                "NOT_A_SETTING": 1,
            })
            self.assertEqual(main.SCROLL_SPEED, 3000)
            self.assertEqual(main.BETA, 0.01)
            self.assertFalse(main.SCROLL_INVERT)
            self.assertEqual(len(warnings), 3)
        finally:
            main.SCROLL_SPEED, main.SCROLL_INVERT, main.BETA = saved

    def test_example_settings_match_defaults(self):
        path = os.path.join(PROJECT_DIR, "settings.example.json")
        with open(path) as file:
            data = json.load(file)

        self.assertEqual(data["gestures"], main.DEFAULT_GESTURES)
        self.assertIn(data["profile"], main.DEFAULT_GESTURES)
        for name, value in data["tuning"].items():
            self.assertIn(name, main.TUNABLE)
            self.assertEqual(value, getattr(main, name), name)


class MappingTests(unittest.TestCase):

    def test_map_to_screen(self):
        self.assertEqual(main.map_to_screen(0.2, 0.2, 0.8, 1001), 0.0)
        self.assertAlmostEqual(main.map_to_screen(0.5, 0.2, 0.8, 1001), 500.0)
        self.assertEqual(main.map_to_screen(0.95, 0.2, 0.8, 1001), 1000.0)

    def test_reach_region_ignores_strays(self):
        samples = [
            (0.3 + 0.4 * (i % 21) / 20, 0.25 + 0.5 * (i // 21) / 20)
            for i in range(21 * 21)
        ]
        samples.append((0.0, 0.0))  # a stray detection
        left, top, right, bottom = main.reach_region(samples)
        self.assertGreater(left, 0.29)
        self.assertGreater(top, 0.24)
        self.assertLess(right, 0.71)
        self.assertLess(bottom, 0.76)

    def test_reach_region_too_small(self):
        with self.assertRaises(ValueError):
            main.reach_region([(0.5 + i * 0.001, 0.5) for i in range(50)])

    def test_scale_region_stays_in_frame(self):
        saved = main.active_region
        try:
            with mock.patch.object(main, "save_calibration"), \
                    mock.patch("builtins.print"):
                main.active_region = (0.0, 0.0, 0.9, 0.9)
                for _ in range(10):
                    main.scale_region(1.2, 0.0)
                left, top, right, bottom = main.active_region
                self.assertGreaterEqual(left, 0.0)
                self.assertLessEqual(right, 1.0)

                for _ in range(30):
                    main.scale_region(0.8, 0.0)
                left, top, right, bottom = main.active_region
                self.assertAlmostEqual(right - left, 0.2)
        finally:
            main.active_region = saved


class FilterTests(unittest.TestCase):

    def test_steady_input_stays_put(self):
        f = main.OneEuroFilter(0.6, 0.007, 1.0)
        for i in range(30):
            value = f(100.0, i / 30)
        self.assertAlmostEqual(value, 100.0)

    def test_follows_a_step(self):
        f = main.OneEuroFilter(0.6, 0.007, 1.0)
        f(0.0, 0.0)
        for i in range(1, 120):
            value = f(500.0, i / 30)
        self.assertGreater(value, 490.0)


if __name__ == "__main__":
    unittest.main()
