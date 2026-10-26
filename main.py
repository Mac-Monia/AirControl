
import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import math
import time
import json
import os
import sys
import copy
import ctypes
import threading
import statistics
from collections import deque


# ---------------- CONFIGURATION ----------------
# Any number or True/False below can also be set in settings.json
# under "tuning" (see settings.example.json).

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

SCREEN_W, SCREEN_H = pyautogui.size()

# Camera
CAMERA_INDEX = 0
CAMERA_W = 640
CAMERA_H = 480
CAMERA_FPS = 30
# Seconds without a new frame before the camera is reopened
CAMERA_TIMEOUT = 3.0

# 1 = more accurate landmarks, 0 = faster (use 0 if the FPS shown
# on screen is below about 20)
MODEL_COMPLEXITY = 1

# Only this inner part of the camera frame is mapped to the screen,
# so the screen edges are reachable without the hand leaving the view.
# Reach calibration (press R) and the sensitivity keys replace this.
FRAME_MARGIN_X = 0.15
FRAME_MARGIN_Y = 0.15

# Keep the cursor off the exact screen corners so our own moves
# never trigger the PyAutoGUI fail-safe.
SCREEN_EDGE_PADDING = 2

# Cursor tuning (One Euro filter)
# Lower MIN_CUTOFF = less jitter when still, more lag.
# Higher BETA = less lag during fast movement.
MIN_CUTOFF = 0.6
BETA = 0.007
DERIVATIVE_CUTOFF = 1.0

# The cursor is moved on its own thread at this rate, gliding between
# camera frames so motion stays smooth even at low camera FPS.
CURSOR_RATE = 120
# Seconds for the cursor to cover most of the gap to its target
CURSOR_GLIDE = 0.04

# Sensitivity keys (+ / -) shrink or grow the active region by this factor
SENSITIVITY_STEP = 0.9
# Smoothing keys ([ / ]) divide or multiply MIN_CUTOFF by this factor
SMOOTHING_STEP = 1.25

# Pinch tuning: 3D distance relative to hand size
PINCH_START = 0.22
PINCH_RELEASE = 0.35

# Freeze the cursor as the fingers close so the click lands on target
FREEZE_RATIO = 0.30

# Require a short, stable gesture
PINCH_FRAMES_REQUIRED = 3
RELEASE_FRAMES_REQUIRED = 2
# Short enough that two quick pinches fit in a double-click
CLICK_COOLDOWN = 0.2

# Right-click: keep the index finger up and pinch the thumb and middle
# finger together. Uses the pinch thresholds above.
# How far the middle fingertip must reach from its knuckle (relative to
# hand size); a middle finger curled into the palm also sits near the
# thumb and must not right-click.
MIDDLE_REACH_RATIO = 0.45

# Double-click: pinch twice quickly. After a click the cursor holds
# still for this many seconds so a second click lands on the same spot.
# 0 = use the system's double-click time.
DOUBLE_CLICK_TIME = 0.0
# Moving the fingertip this far (fraction of frame width) after a
# click frees the cursor early.
CLICK_LOCK_MOVE = 0.04

# After scrolling, swiping, zooming, dragging or a held pose, ignore
# pinches for this long so the hand can settle back into pointing.
MODE_SETTLE_TIME = 0.25

# Scroll tuning: peace sign (index + middle up, ring + pinky folded),
# then move the hand up or down to scroll.
SCROLL_FRAMES_REQUIRED = 3
# Wheel units per full frame height of movement (120 = one notch on Windows)
SCROLL_SPEED = 2500
# Ignore movement smaller than this (fraction of frame height)
SCROLL_DEAD_ZONE = 0.006
# True = hand up scrolls down, like dragging a touchscreen
SCROLL_INVERT = False
# A fingertip this much farther from the wrist than its middle joint
# counts as extended.
FINGER_EXTENDED_RATIO = 1.15

# Drag and drop: open palm to get ready, close fist to grab,
# open palm again to drop.
GRAB_FRAMES_REQUIRED = 3
# Frames of an unrelated gesture before "ready" is cancelled; long
# enough to cover the in-between frames while the fist closes.
READY_EXIT_FRAMES = 15

# Zoom: pinch with both hands, then move them apart to zoom in or
# together to zoom out. Sends Ctrl + mouse wheel, which zooms in most apps.
ZOOM_FRAMES_REQUIRED = 3
# Frames without a two-hand pinch before zoom stops; covers missed
# detections so a single dropped frame does not end the zoom.
ZOOM_EXIT_FRAMES = 4
# Change in hand distance per zoom step, on a log scale
# (0.15 = hands about 16% farther apart or closer together)
ZOOM_STEP = 0.15
# True = hands apart zooms out
ZOOM_INVERT = False

# Swipe: raise three fingers (index, middle, ring), then flick the hand
# left, right, up or down. What a swipe does depends on the profile.
SWIPE_FRAMES_REQUIRED = 3
# The hand must move this far (in hand sizes) within SWIPE_WINDOW seconds
SWIPE_DISTANCE = 0.9
SWIPE_WINDOW = 0.35
# The main direction must be this many times larger than the other one
SWIPE_AXIS_RATIO = 1.5
# Seconds before another swipe in the same direction, and in the
# opposite direction (so the hand's return stroke does not count).
SWIPE_COOLDOWN = 0.4
SWIPE_REVERSE_BLOCK = 1.0

# Held poses fire once per hold: thumbs up, rock sign (index + pinky up)
# and both palms open (pause / resume). Seconds each must be held.
POSE_HOLD_TIME = 0.6
PROFILE_HOLD_TIME = 0.8
PAUSE_HOLD_TIME = 1.2
# A pose may drop out this long (missed detections) without restarting
POSE_HOLD_GAP = 0.15
# Thumb tip distance from the index knuckle (relative to hand size)
# for a fist to count as a thumbs up.
THUMB_OUT_RATIO = 0.55

# Landmarks the cursor can follow
INDEX_TIP = 8
PALM_CENTER = 9
# How fast the cursor eases back to the fingertip after following the palm
OFFSET_DECAY = 0.85

# Frames without a hand before tracking is reset; avoids dropping a
# drag on a single missed detection.
TRACKING_LOST_FRAMES = 5

# Landmarks this close to the frame edge (fraction) mean the hand is
# partly out of view; held poses are ignored then.
EDGE_MARGIN = 0.02
# Average frame brightness (0-255) below which a low light warning shows
LOW_LIGHT_LEVEL = 60

# Display
SHOW_LANDMARKS = True
# Keep the camera window above other windows
ALWAYS_ON_TOP = False
# Ctrl+Alt+P pauses and Ctrl+Alt+Q quits even when the camera window is
# not focused (Windows only).
GLOBAL_HOTKEYS = True

# Pinch calibration (press C): measures your hand and overrides the
# pinch thresholds above. Reach calibration (press R) and the
# sensitivity and smoothing keys are saved in the same file.
CALIBRATION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "calibration.json"
)
CALIBRATION_STEPS = (
    ("open", "Point with index finger, thumb relaxed"),
    ("pinch", "Pinch thumb and index together"),
)
REACH_STEPS = (
    ("reach", "Trace the edges of a comfortable area with your index finger"),
)
# Seconds per step; the first part of each step is ignored while
# the hand settles.
CALIBRATION_STEP_TIME = 2.5
REACH_CALIBRATION_TIME = 6.0
CALIBRATION_SETTLE_TIME = 1.0
# Where each threshold sits between your pinched (0) and open (1) ratio
CALIBRATION_START = 0.30
CALIBRATION_FREEZE = 0.45
CALIBRATION_RELEASE = 0.55

# Gesture actions and tuning overrides
SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "settings.json"
)

# What each configurable gesture does. "all" applies in every profile
# unless the profile sets the same gesture. Actions are key names
# joined with "+" (any PyAutoGUI key), optionally repeated with "*N",
# or "mouse:left|right|middle|double", "profile:next|previous|<name>",
# "pause" or "none".
DEFAULT_GESTURES = {
    "all": {
        "thumbs_up": {"action": "playpause", "label": "Play / pause"},
        "rock": {"action": "profile:next", "label": "Next profile"},
    },
    "navigate": {
        "swipe_left": {"action": "alt+right", "label": "Forward"},
        "swipe_right": {"action": "alt+left", "label": "Back"},
        "swipe_up": {"action": "ctrl+tab", "label": "Next tab"},
        "swipe_down": {"action": "ctrl+shift+tab", "label": "Previous tab"},
    },
    "media": {
        "swipe_left": {"action": "nexttrack", "label": "Next track"},
        "swipe_right": {"action": "prevtrack", "label": "Previous track"},
        "swipe_up": {"action": "volumeup*5", "label": "Volume up"},
        "swipe_down": {"action": "volumedown*5", "label": "Volume down"},
    },
    "slides": {
        "swipe_left": {"action": "right", "label": "Next slide"},
        "swipe_right": {"action": "left", "label": "Previous slide"},
        "swipe_up": {"action": "shift+f5", "label": "Start slideshow"},
        "swipe_down": {"action": "esc", "label": "End slideshow"},
        "thumbs_up": {"action": "b", "label": "Black screen"},
    },
}

# Gestures that can be assigned in settings.json, as shown on screen
GESTURE_NAMES = {
    "swipe_left": "3 fingers, flick left",
    "swipe_right": "3 fingers, flick right",
    "swipe_up": "3 fingers, flick up",
    "swipe_down": "3 fingers, flick down",
    "thumbs_up": "Thumbs up (hold)",
    "rock": "Index + pinky up (hold)",
}

# Configuration names that settings.json may not change
FIXED_SETTINGS = {"SCREEN_W", "SCREEN_H", "INDEX_TIP", "PALM_CENTER"}
TUNABLE = {
    name for name, value in list(globals().items())
    if name.isupper()
    and isinstance(value, (int, float))
    and name not in FIXED_SETTINGS
}

WINDOW_NAME = "AirControl"

# Windows API, for global hotkeys and the system double-click time
user32 = ctypes.windll.user32 if sys.platform == "win32" else None
VK_CONTROL = 0x11
VK_MENU = 0x12

# (tip, middle joint) of the index, middle, ring and pinky fingers
FINGERS = ((8, 6), (12, 10), (16, 14), (20, 18))

# ---------------- FILTER ----------------

class OneEuroFilter:
    """Adaptive low-pass filter: smooth when slow, responsive when fast."""

    def __init__(self, min_cutoff, beta, d_cutoff):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self.value = None
        self.derivative = 0.0
        self.last_time = None

    @staticmethod
    def alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, now):
        if self.value is None:
            self.value = x
            self.last_time = now
            return x

        dt = max(now - self.last_time, 1e-3)
        self.last_time = now

        # Smooth the speed estimate, then use it to pick the cutoff.
        raw_derivative = (x - self.value) / dt
        a_d = self.alpha(self.d_cutoff, dt)
        self.derivative += a_d * (raw_derivative - self.derivative)

        cutoff = self.min_cutoff + self.beta * abs(self.derivative)
        a = self.alpha(cutoff, dt)
        self.value += a * (x - self.value)
        return self.value


class CursorMover(threading.Thread):
    """Glides the OS cursor toward the latest target at a steady rate."""

    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.target = None
        self.running = True
        self.failsafe = False

    def set_target(self, x, y):
        with self.lock:
            self.target = (x, y)

    def release(self):
        # Stop steering; the next target starts from wherever the
        # cursor is by then, even if the real mouse moved it.
        with self.lock:
            self.target = None

    def stop(self):
        self.running = False

    def run(self):
        current = None
        last_position = None
        last_time = time.monotonic()

        try:
            while self.running:
                now = time.monotonic()
                dt = now - last_time
                last_time = now

                with self.lock:
                    target = self.target

                if target is None:
                    current = None
                    last_position = None
                else:
                    if current is None:
                        current = pyautogui.position()

                    # Frame-rate independent easing toward the target.
                    a = 1.0 - math.exp(-dt / CURSOR_GLIDE)
                    current = (
                        current[0] + a * (target[0] - current[0]),
                        current[1] + a * (target[1] - current[1])
                    )

                    position = (round(current[0]), round(current[1]))

                    # Skip redundant OS calls when the cursor has not moved.
                    if position != last_position:
                        pyautogui.moveTo(*position)
                        last_position = position

                time.sleep(1.0 / CURSOR_RATE)

        except pyautogui.FailSafeException:
            self.failsafe = True


class CameraReader(threading.Thread):
    """Reads frames on its own thread so processing always gets the
    newest one, and reopens the camera if it stops delivering."""

    def __init__(self, index):
        super().__init__(daemon=True)
        self.index = index
        self.capture = None
        self.condition = threading.Condition()
        self.frame = None
        self.frame_id = 0
        self.running = True
        self.last_frame_time = time.monotonic()

    def open(self):
        capture = cv2.VideoCapture(self.index)
        if not capture.isOpened():
            capture.release()
            return False

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_W)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)
        capture.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        # Keep the driver's queue short to keep latency low.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.capture = capture
        self.last_frame_time = time.monotonic()
        return True

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            if self.capture is not None:
                ok, frame = self.capture.read()
            else:
                ok, frame = False, None

            now = time.monotonic()

            if ok:
                with self.condition:
                    self.frame = frame
                    self.frame_id += 1
                    self.last_frame_time = now
                    self.condition.notify_all()
                continue

            time.sleep(0.05)

            # Silent for too long (unplugged, taken by another app):
            # close it and try again, once per timeout.
            if now - self.last_frame_time >= CAMERA_TIMEOUT:
                if self.capture is not None:
                    self.capture.release()
                    self.capture = None
                print("Camera not responding, reopening...")
                if not self.open():
                    self.last_frame_time = now

        if self.capture is not None:
            self.capture.release()

    def read(self, last_id, timeout):
        """Waits for a frame newer than last_id. Returns (id, frame),
        with frame None if none arrived in time."""
        with self.condition:
            self.condition.wait_for(
                lambda: self.frame_id != last_id, timeout
            )
            if self.frame_id == last_id:
                return last_id, None
            return self.frame_id, self.frame


class HoldTrigger:
    """Fires once when a pose has been held long enough; the pose must
    then be let go before it can fire again."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start = None
        self.last_seen = None
        self.fired = False

    def update(self, active, now, hold_time):
        if active:
            if self.start is None:
                self.start = now
            self.last_seen = now

            if not self.fired and now - self.start >= hold_time:
                self.fired = True
                return True

        elif self.last_seen is not None and now - self.last_seen > POSE_HOLD_GAP:
            self.reset()

        return False

    def progress(self, now, hold_time):
        if self.start is None or self.fired:
            return 0.0
        return clamp((now - self.start) / hold_time, 0.0, 1.0)

# ---------------- STATE ----------------

filter_x = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
filter_y = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
cursor_mover = CursorMover()
tracking_landmark = None
offset_x = 0.0
offset_y = 0.0
lost_frames = 0
primary_wrist = None  # last position of the hand that steers the cursor

# Part of the camera frame mapped to the screen: (left, top, right, bottom)
active_region = (
    FRAME_MARGIN_X, FRAME_MARGIN_Y, 1 - FRAME_MARGIN_X, 1 - FRAME_MARGIN_Y
)
default_min_cutoff = MIN_CUTOFF

pinch_frames = 0
release_frames = 0
pinching = False
pinch_button = None  # "left" or "right" while a pinch is confirmed or held
click_armed = True
last_click_time = 0.0
last_left_click_time = -math.inf
# The cursor holds still after a click so a second one can double-click.
click_lock_until = 0.0
click_lock_point = None
# Last time a mode other than pointing was active
last_mode_time = -math.inf

scroll_frames = 0
scrolling = False
scroll_anchor_y = None
scroll_remainder = 0.0

grab_state = "idle"  # "idle", "ready" or "dragging"
grab_pending = None
grab_frames = 0

zoom_frames = 0
zooming = False
zoom_anchor = None

swipe_frames = 0
swiping = False
swipe_history = deque()  # (time, x, y) of the palm, in pixels
last_swipe_direction = None
last_swipe_time = -math.inf

thumbs_hold = HoldTrigger()
rock_hold = HoldTrigger()
pause_hold = HoldTrigger()
paused = False

# Filled in by load_settings()
gesture_actions = {}
profiles = ["navigate"]
profile_index = 0

hotkeys_down = set()

calibration_steps = CALIBRATION_STEPS
calibration_step = None  # index into calibration_steps while running
calibration_step_start = 0.0
calibration_samples = {}

message = ""
message_until = 0.0
action_text = ""
action_until = 0.0
hud_warning = ""
debug_lines = []
show_help = False
show_debug = False

# ---------------- HELPERS ----------------

def clamp(value, low, high):
    return max(low, min(value, high))


def landmark_distance(a, b, width, height):
    # Scale to pixels so x and y share units; MediaPipe's z uses
    # roughly the same scale as x.
    return math.sqrt(
        ((a.x - b.x) * width) ** 2
        + ((a.y - b.y) * height) ** 2
        + ((a.z - b.z) * width) ** 2
    )


def map_to_screen(value, low, high, size):
    # Stretch the active region of the frame to the full screen.
    normalized = clamp((value - low) / (high - low), 0.0, 1.0)
    return normalized * (size - 1)


def move_cursor(points, landmark, now):
    global tracking_landmark, offset_x, offset_y

    left, top, right, bottom = active_region
    point = points[landmark]
    target_x = map_to_screen(point.x, left, right, SCREEN_W)
    target_y = map_to_screen(point.y, top, bottom, SCREEN_H)

    if landmark != tracking_landmark and filter_x.value is not None:
        # Switching tracking points: start from the current cursor
        # position so it does not jump.
        offset_x = filter_x.value - target_x
        offset_y = filter_y.value - target_y
    elif landmark == INDEX_TIP:
        # Ease back to the fingertip's own position while pointing.
        offset_x *= OFFSET_DECAY
        offset_y *= OFFSET_DECAY

    tracking_landmark = landmark

    x = filter_x(target_x + offset_x, now)
    y = filter_y(target_y + offset_y, now)

    cursor_mover.set_target(
        clamp(x, SCREEN_EDGE_PADDING, SCREEN_W - 1 - SCREEN_EDGE_PADDING),
        clamp(y, SCREEN_EDGE_PADDING, SCREEN_H - 1 - SCREEN_EDGE_PADDING)
    )


def reset_tracking():
    global tracking_landmark, offset_x, offset_y, primary_wrist
    global click_lock_until

    filter_x.reset()
    filter_y.reset()
    cursor_mover.release()
    tracking_landmark = None
    offset_x = 0.0
    offset_y = 0.0
    primary_wrist = None
    click_lock_until = 0.0
    reset_click()
    reset_scroll()
    reset_grab()
    reset_zoom()
    reset_swipe()
    thumbs_hold.reset()
    rock_hold.reset()


def measure_hand(points, width, height):
    # Hand size: the larger of palm width and palm length, so the
    # ratio stays stable when the hand rotates.
    hand_size = max(
        landmark_distance(points[5], points[17], width, height),
        landmark_distance(points[0], points[9], width, height)
    )

    if hand_size <= 1.0:
        return hand_size, None

    pinch_distance = landmark_distance(points[4], points[8], width, height)
    return hand_size, pinch_distance / hand_size


def right_pinch_ratio(points, hand_size, width, height):
    # Thumb to middle fingertip, counted only while the index finger
    # points up and the middle finger reaches out to the thumb.
    if not finger_extended(points, 8, 6, width, height):
        return None

    reach = landmark_distance(points[12], points[9], width, height)
    if reach / hand_size < MIDDLE_REACH_RATIO:
        return None

    return landmark_distance(points[4], points[12], width, height) / hand_size


def hand_in_view(points):
    return all(
        EDGE_MARGIN < point.x < 1 - EDGE_MARGIN
        and EDGE_MARGIN < point.y < 1 - EDGE_MARGIN
        for point in points
    )


def pick_primary_hand(hands):
    global primary_wrist

    # MediaPipe does not keep hands in a fixed order, so follow the
    # one nearest to where the cursor hand was last seen.
    if primary_wrist is None or len(hands) == 1:
        primary = hands[0]
    else:
        primary = min(
            hands,
            key=lambda hand: (
                (hand.landmark[0].x - primary_wrist[0]) ** 2
                + (hand.landmark[0].y - primary_wrist[1]) ** 2
            )
        )

    primary_wrist = (primary.landmark[0].x, primary.landmark[0].y)
    return primary


def reset_click():
    global pinch_frames, release_frames, pinching, click_armed, pinch_button

    pinch_frames = 0
    release_frames = 0
    pinching = False
    pinch_button = None
    click_armed = True


def hold_click():
    global pinch_frames, release_frames, pinching, click_armed, pinch_button

    # Treat the pinch as already used, so letting go of one hand
    # after zooming does not click.
    pinch_frames = 0
    release_frames = 0
    pinching = True
    pinch_button = "left"
    click_armed = False


def reset_zoom():
    global zoom_frames, zooming, zoom_anchor

    zoom_frames = 0
    zooming = False
    zoom_anchor = None


def reset_grab():
    global grab_state, grab_pending, grab_frames

    # Never leave the mouse button stuck down.
    if grab_state == "dragging":
        pyautogui.mouseUp()
        print("DROP")

    grab_state = "idle"
    grab_pending = None
    grab_frames = 0


def reset_scroll():
    global scroll_frames, scrolling, scroll_anchor_y, scroll_remainder

    scroll_frames = 0
    scrolling = False
    scroll_anchor_y = None
    scroll_remainder = 0.0


def reset_swipe():
    global swipe_frames, swiping, last_swipe_direction

    swipe_frames = 0
    swiping = False
    swipe_history.clear()
    last_swipe_direction = None


def finger_extended(points, tip, pip, width, height):
    wrist = points[0]
    return (
        landmark_distance(wrist, points[tip], width, height)
        > FINGER_EXTENDED_RATIO
        * landmark_distance(wrist, points[pip], width, height)
    )


def finger_folded(points, tip, pip, width, height):
    wrist = points[0]
    return (
        landmark_distance(wrist, points[tip], width, height)
        < landmark_distance(wrist, points[pip], width, height)
    )


def thumb_out(points, hand_size, width, height):
    # The thumb points away from the hand: its tip is far from the
    # index knuckle and farther from the pinky knuckle than its own
    # middle joint is (a tucked thumb curls toward the pinky).
    reach = landmark_distance(points[4], points[5], width, height)
    return (
        reach / hand_size > THUMB_OUT_RATIO
        and landmark_distance(points[4], points[17], width, height)
        > landmark_distance(points[3], points[17], width, height)
    )


def classify_pose(points, hand_size, width, height):
    """Names the hand pose: palm, three, peace, rock, thumbs_up, fist,
    pinch or other (pointing and everything else)."""
    up = [finger_extended(points, tip, pip, width, height)
          for tip, pip in FINGERS]
    down = [finger_folded(points, tip, pip, width, height)
            for tip, pip in FINGERS]
    index, middle, ring, pinky = range(4)

    if all(up):
        return "palm"
    if up[index] and up[middle] and up[ring] and down[pinky]:
        return "three"
    if up[index] and up[middle] and down[ring] and down[pinky]:
        return "peace"
    if up[index] and down[middle] and down[ring] and up[pinky]:
        return "rock"
    if all(down):
        # The index finger curls to meet the thumb when pinching, so a
        # pinch with the other fingers curled looks like a fist.
        pinch = landmark_distance(points[4], points[8], width, height)
        if pinch / hand_size < PINCH_START:
            return "pinch"
        if (
            pinch / hand_size > PINCH_RELEASE
            and thumb_out(points, hand_size, width, height)
        ):
            return "thumbs_up"
        return "fist"
    return "other"


def finger_states(points, width, height):
    # For the debug view: + extended, - folded, ~ in between
    states = []
    for name, (tip, pip) in zip("IMRP", FINGERS):
        if finger_extended(points, tip, pip, width, height):
            states.append(name + "+")
        elif finger_folded(points, tip, pip, width, height):
            states.append(name + "-")
        else:
            states.append(name + "~")
    return " ".join(states)


def update_grab(gesture):
    global grab_state, grab_pending, grab_frames

    # A fist with the thumb out, or with the thumb on the index
    # fingertip, still grabs.
    if gesture in ("thumbs_up", "pinch"):
        gesture = "fist"

    # Work out which state this gesture leads to, and how many
    # frames it must be held first.
    target = None
    needed = GRAB_FRAMES_REQUIRED

    if grab_state == "idle":
        if gesture == "palm":
            target = "ready"
    elif grab_state == "ready":
        if gesture == "fist":
            target = "dragging"
        elif gesture != "palm":
            target = "idle"
            needed = READY_EXIT_FRAMES
    elif gesture == "palm":
        target = "ready"

    if target != grab_pending:
        grab_pending = target
        grab_frames = 0

    if target is None:
        return

    grab_frames += 1
    if grab_frames < needed:
        return

    if target == "dragging":
        pyautogui.mouseDown()
        print("GRAB")
    elif grab_state == "dragging":
        pyautogui.mouseUp()
        print("DROP")

    grab_state = target
    grab_pending = None
    grab_frames = 0


def update_scroll_mode(peace):
    global scroll_frames, scrolling, scroll_anchor_y, scroll_remainder

    # Count toward entering or leaving scroll mode so a single
    # misread frame does not toggle it.
    if peace != scrolling:
        scroll_frames += 1
    else:
        scroll_frames = 0

    if scroll_frames >= SCROLL_FRAMES_REQUIRED:
        scrolling = peace
        scroll_frames = 0
        scroll_anchor_y = None
        scroll_remainder = 0.0


def scroll_with(points):
    global scroll_anchor_y, scroll_remainder

    # Track the point between the two raised fingertips.
    y = (points[8].y + points[12].y) / 2

    if scroll_anchor_y is None:
        scroll_anchor_y = y
        return

    # Measure from an anchor instead of the last frame so slow
    # movements still add up past the dead zone.
    delta = scroll_anchor_y - y
    if abs(delta) < SCROLL_DEAD_ZONE:
        return

    if SCROLL_INVERT:
        delta = -delta

    amount = delta * SCROLL_SPEED + scroll_remainder
    clicks = int(amount)
    scroll_remainder = amount - clicks
    scroll_anchor_y = y

    if clicks:
        pyautogui.scroll(clicks)


def update_swipe_mode(three):
    global swipe_frames, swiping, last_swipe_direction

    if three != swiping:
        swipe_frames += 1
    else:
        swipe_frames = 0

    if swipe_frames >= SWIPE_FRAMES_REQUIRED:
        swiping = three
        swipe_frames = 0
        swipe_history.clear()
        # Letting go of the pose re-arms every direction.
        if not swiping:
            last_swipe_direction = None


OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}


def swipe_with(points, hand_size, width, height, now):
    """Returns "swipe_left", "swipe_right", "swipe_up", "swipe_down"
    or None."""
    global last_swipe_direction, last_swipe_time

    palm = points[PALM_CENTER]
    x, y = palm.x * width, palm.y * height
    swipe_history.append((now, x, y))

    while now - swipe_history[0][0] > SWIPE_WINDOW:
        swipe_history.popleft()

    # Only fast movements count: compare with where the palm was at
    # most SWIPE_WINDOW seconds ago, relative to hand size so it works
    # at any distance from the camera.
    _, start_x, start_y = swipe_history[0]
    dx = (x - start_x) / hand_size
    dy = (y - start_y) / hand_size

    if max(abs(dx), abs(dy)) < SWIPE_DISTANCE:
        return None

    if abs(dx) >= SWIPE_AXIS_RATIO * abs(dy):
        direction = "left" if dx < 0 else "right"
    elif abs(dy) >= SWIPE_AXIS_RATIO * abs(dx):
        direction = "up" if dy < 0 else "down"
    else:
        return None

    # Start over so one flick only counts once.
    swipe_history.clear()

    since = now - last_swipe_time
    if last_swipe_direction == OPPOSITE[direction] and since < SWIPE_REVERSE_BLOCK:
        return None
    if since < SWIPE_COOLDOWN:
        return None

    last_swipe_direction = direction
    last_swipe_time = now
    return "swipe_" + direction


def hand_pinched(ratio):
    # Looser threshold once zooming, like detect_click, so the zoom
    # holds through a slightly relaxed pinch.
    return ratio < (PINCH_RELEASE if zooming else PINCH_START)


def update_zoom_mode(both_pinched):
    global zoom_frames, zooming, zoom_anchor

    if both_pinched != zooming:
        zoom_frames += 1
    else:
        zoom_frames = 0

    needed = ZOOM_FRAMES_REQUIRED if both_pinched else ZOOM_EXIT_FRAMES
    if zoom_frames >= needed:
        zooming = both_pinched
        zoom_frames = 0
        zoom_anchor = None


def pinch_point(points, width, height):
    thumb, index = points[4], points[8]
    return (
        (thumb.x + index.x) / 2 * width,
        (thumb.y + index.y) / 2 * height
    )


def zoom_with(points, hand_size, other_points, other_size, width, height):
    global zoom_anchor

    a = pinch_point(points, width, height)
    b = pinch_point(other_points, width, height)

    # Relative to hand size so it works at any distance from the camera;
    # a log scale makes each step feel the same at any separation.
    separation = math.dist(a, b) / ((hand_size + other_size) / 2)
    level = math.log(max(separation, 1e-3))

    if zoom_anchor is None:
        zoom_anchor = level
        return

    steps = int((level - zoom_anchor) / ZOOM_STEP)
    if not steps:
        return

    zoom_anchor += steps * ZOOM_STEP

    if ZOOM_INVERT:
        steps = -steps

    # 120 wheel units = one notch on Windows
    pyautogui.keyDown("ctrl")
    try:
        pyautogui.scroll(steps * 120)
    finally:
        pyautogui.keyUp("ctrl")

    print("ZOOM IN" if steps > 0 else "ZOOM OUT")


def double_click_time():
    if DOUBLE_CLICK_TIME > 0:
        return DOUBLE_CLICK_TIME
    if user32 is not None:
        return user32.GetDoubleClickTime() / 1000.0
    return 0.5


def detect_click(ratio, right_ratio, now, allowed=True):
    """Returns "left", "double" or "right" when a click is sent."""
    global pinch_frames, release_frames, pinch_button
    global pinching, click_armed, last_click_time, last_left_click_time

    # Different thresholds prevent rapid state switching. Before the
    # pinch is confirmed, pick the finger touching the thumb; after,
    # stay with it until it is released.
    if pinching:
        held = ratio if pinch_button == "left" else right_ratio
        pinch_detected = held is not None and held < PINCH_RELEASE
    else:
        if ratio < PINCH_START:
            button = "left"
        elif right_ratio is not None and right_ratio < PINCH_START:
            button = "right"
        else:
            button = None

        if button != pinch_button:
            pinch_button = button
            pinch_frames = 0

        pinch_detected = button is not None

    if pinch_detected:
        pinch_frames += 1
        release_frames = 0
    else:
        release_frames += 1
        pinch_frames = 0

    clicked = None

    # Confirm the pinch before clicking.
    if not pinching and pinch_frames >= PINCH_FRAMES_REQUIRED:
        pinching = True

        if (
            allowed
            and click_armed
            and now - last_click_time >= CLICK_COOLDOWN
        ):
            if pinch_button == "right":
                pyautogui.click(button="right")
                clicked = "right"
            else:
                # Two clicks in the same spot within the system's
                # double-click time are a double-click.
                pyautogui.click()
                if now - last_left_click_time <= double_click_time():
                    clicked = "double"
                    last_left_click_time = -math.inf
                else:
                    clicked = "left"
                    last_left_click_time = now

            last_click_time = now
            click_armed = False
            print(clicked.upper() + " CLICK")

    # A deliberate release enables the next click.
    if pinching and release_frames >= RELEASE_FRAMES_REQUIRED:
        pinching = False
        pinch_button = None
        click_armed = True

    return clicked


# ---------------- SETTINGS AND ACTIONS ----------------

def parse_action(spec):
    """Checks an action string and returns (kind, value, repeat)."""
    spec = spec.strip().lower()

    if spec in ("", "none"):
        return ("none", None, 1)
    if spec == "pause":
        return ("pause", None, 1)
    if spec.startswith("profile:"):
        return ("profile", spec.split(":", 1)[1].strip(), 1)
    if spec.startswith("mouse:"):
        button = spec.split(":", 1)[1].strip()
        if button not in ("left", "right", "middle", "double"):
            raise ValueError(f"unknown mouse button '{button}'")
        return ("mouse", button, 1)

    repeat = 1
    if "*" in spec:
        spec, count = spec.rsplit("*", 1)
        try:
            repeat = int(count)
        except ValueError:
            raise ValueError(f"bad repeat count '{count}'") from None
        if not 1 <= repeat <= 20:
            raise ValueError("repeat count must be 1 to 20")

    keys = [key.strip() for key in spec.split("+")]
    for key in keys:
        if key not in pyautogui.KEYBOARD_KEYS:
            raise ValueError(f"unknown key '{key}'")

    return ("keys", keys, repeat)


def merge_gestures(user_gestures):
    """Lays the gestures from settings.json over the defaults."""
    gestures = copy.deepcopy(DEFAULT_GESTURES)
    warnings = []

    if not isinstance(user_gestures, dict):
        return gestures, ['"gestures" must be an object']

    for profile, mapping in user_gestures.items():
        if not isinstance(mapping, dict):
            warnings.append(f'gestures "{profile}" must be an object')
            continue
        gestures.setdefault(profile, {}).update(mapping)

    return gestures, warnings


def build_gesture_actions(gestures):
    """Checks every gesture's action. Returns (actions, warnings), with
    actions[profile][gesture] = {"action", "label", "parsed"}."""
    actions = {}
    warnings = []
    names = [profile for profile in gestures if profile != "all"]

    for profile, mapping in gestures.items():
        actions[profile] = {}

        for gesture, entry in mapping.items():
            where = f'{profile} / {gesture}'

            if gesture not in GESTURE_NAMES:
                warnings.append(f"{where}: unknown gesture")
                continue

            if entry is None:
                entry = "none"
            if isinstance(entry, str):
                entry = {"action": entry}
            if not isinstance(entry, dict) or not isinstance(
                entry.get("action"), str
            ):
                warnings.append(f'{where}: needs an "action" text')
                continue

            try:
                parsed = parse_action(entry["action"])
            except ValueError as error:
                warnings.append(f"{where}: {error}")
                continue

            if parsed[0] == "profile" and parsed[1] not in (
                "next", "previous", *names
            ):
                warnings.append(f"{where}: no profile named '{parsed[1]}'")
                continue

            actions[profile][gesture] = {
                "action": entry["action"],
                "label": str(entry.get("label", entry["action"])),
                "parsed": parsed,
            }

    return actions, warnings


def apply_tuning(tuning):
    """Overrides configuration constants. Returns warnings."""
    if not isinstance(tuning, dict):
        return ['"tuning" must be an object']

    warnings = []
    for name, value in tuning.items():
        if name not in TUNABLE:
            warnings.append(f"tuning: unknown setting {name}")
            continue

        current = globals()[name]
        if isinstance(current, bool):
            valid = isinstance(value, bool)
        elif isinstance(current, int):
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)

        if not valid:
            warnings.append(
                f"tuning: {name} must be {type(current).__name__}, "
                f"got {value!r}"
            )
            continue

        globals()[name] = value

    return warnings


def load_settings(path=SETTINGS_FILE):
    global gesture_actions, profiles, profile_index
    global active_region, default_min_cutoff

    try:
        with open(path) as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {}
    except ValueError as error:
        print(f"Ignoring {os.path.basename(path)}: {error}")
        data = {}

    if not isinstance(data, dict):
        print(f"Ignoring {os.path.basename(path)}: expected an object")
        data = {}

    warnings = apply_tuning(data.get("tuning", {}))
    gestures, merge_warnings = merge_gestures(data.get("gestures", {}))
    gesture_actions, action_warnings = build_gesture_actions(gestures)

    for warning in warnings + merge_warnings + action_warnings:
        print(f"Settings: {warning}")

    profiles = [name for name in gesture_actions if name != "all"]
    start = data.get("profile", profiles[0])
    if start in profiles:
        profile_index = profiles.index(start)
    else:
        print(f"Settings: no profile named '{start}'")
        profile_index = 0

    # Tuning may have changed these.
    active_region = (
        FRAME_MARGIN_X, FRAME_MARGIN_Y,
        1 - FRAME_MARGIN_X, 1 - FRAME_MARGIN_Y
    )
    default_min_cutoff = MIN_CUTOFF


def apply_filter_settings():
    for each in (filter_x, filter_y):
        each.min_cutoff = MIN_CUTOFF
        each.beta = BETA
        each.d_cutoff = DERIVATIVE_CUTOFF


def current_profile():
    return profiles[profile_index]


def action_for(gesture):
    profile_actions = gesture_actions.get(current_profile(), {})
    if gesture in profile_actions:
        return profile_actions[gesture]
    return gesture_actions.get("all", {}).get(gesture)


def switch_profile(name, now):
    global profile_index

    if name == "next":
        profile_index = (profile_index + 1) % len(profiles)
    elif name == "previous":
        profile_index = (profile_index - 1) % len(profiles)
    else:
        profile_index = profiles.index(name)

    show_action(f"Profile: {current_profile()}", now)


def set_paused(value, now):
    global paused

    paused = value
    # Let go of everything held, and of the cursor.
    reset_tracking()
    show_action("Paused" if paused else "Resumed", now)


def run_gesture_action(gesture, now):
    entry = action_for(gesture)
    if entry is None or entry["parsed"][0] == "none":
        show_action(f"{GESTURE_NAMES[gesture]}: no action", now)
        return

    kind, value, repeat = entry["parsed"]

    try:
        if kind == "keys":
            for _ in range(repeat):
                if len(value) == 1:
                    pyautogui.press(value[0])
                else:
                    pyautogui.hotkey(*value)
        elif kind == "mouse":
            if value == "double":
                pyautogui.doubleClick()
            else:
                pyautogui.click(button=value)
        elif kind == "profile":
            switch_profile(value, now)
            return
        elif kind == "pause":
            set_paused(True, now)
            return

    except pyautogui.FailSafeException:
        raise
    except Exception as error:
        show_message(f"Action failed: {error}", now)
        return

    show_action(entry["label"], now)


def show_message(text, now, seconds=3.0):
    global message, message_until

    message = text
    message_until = now + seconds
    print(text)


def show_action(text, now, seconds=1.5):
    global action_text, action_until

    action_text = text
    action_until = now + seconds
    print(text.upper())


def poll_global_hotkeys():
    """Returns "p" or "q" when Ctrl+Alt+P or Ctrl+Alt+Q was just
    pressed anywhere (Windows only)."""
    if user32 is None or not GLOBAL_HOTKEYS:
        return None

    def held(key):
        return bool(user32.GetAsyncKeyState(key) & 0x8000)

    modifiers = held(VK_CONTROL) and held(VK_MENU)
    pressed = None

    for letter in "PQ":
        down = modifiers and held(ord(letter))
        if down and letter not in hotkeys_down:
            pressed = letter.lower()
        if down:
            hotkeys_down.add(letter)
        else:
            hotkeys_down.discard(letter)

    return pressed


# ---------------- CALIBRATION ----------------

def apply_calibration(open_ratio, pinch_ratio):
    global PINCH_START, PINCH_RELEASE, FREEZE_RATIO

    gap = open_ratio - pinch_ratio
    PINCH_START = pinch_ratio + CALIBRATION_START * gap
    FREEZE_RATIO = pinch_ratio + CALIBRATION_FREEZE * gap
    PINCH_RELEASE = pinch_ratio + CALIBRATION_RELEASE * gap


def check_region(values):
    left, top, right, bottom = (float(value) for value in values)
    if not (
        0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0
        and right - left >= 0.1 and bottom - top >= 0.1
    ):
        raise ValueError("region out of range")
    return (left, top, right, bottom)


def read_calibration():
    try:
        with open(CALIBRATION_FILE) as file:
            data = json.load(file)
    except (FileNotFoundError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_calibration(**fields):
    # Keep what other calibrations saved; None removes a field.
    data = read_calibration()
    for name, value in fields.items():
        if value is None:
            data.pop(name, None)
        else:
            data[name] = value

    try:
        with open(CALIBRATION_FILE, "w") as file:
            json.dump(data, file, indent=2)
    except OSError as error:
        print(f"Could not save calibration: {error}")


def load_calibration():
    global active_region, MIN_CUTOFF

    try:
        with open(CALIBRATION_FILE) as file:
            data = json.load(file)
    except FileNotFoundError:
        return
    except ValueError:
        print("Ignoring invalid calibration file.")
        return

    try:
        if "open" in data and "pinch" in data:
            apply_calibration(float(data["open"]), float(data["pinch"]))
            print(
                f"Loaded calibration: pinch below {PINCH_START:.2f}, "
                f"release above {PINCH_RELEASE:.2f}"
            )
        if "region" in data:
            active_region = check_region(data["region"])
        if "min_cutoff" in data:
            MIN_CUTOFF = clamp(float(data["min_cutoff"]), 0.05, 5.0)
    except (ValueError, KeyError, TypeError, AttributeError):
        print("Ignoring invalid calibration file.")


def start_calibration(steps, now):
    global calibration_steps, calibration_step, calibration_step_start
    global calibration_samples

    calibration_steps = steps
    calibration_step = 0
    calibration_step_start = now
    calibration_samples = {name: [] for name, _ in steps}


def update_calibration(ratio, tip, now):
    global calibration_step, calibration_step_start

    name, instruction = calibration_steps[calibration_step]
    step_time = (
        REACH_CALIBRATION_TIME if name == "reach" else CALIBRATION_STEP_TIME
    )
    elapsed = now - calibration_step_start
    sample = tip if name == "reach" else ratio

    # Only sample once the hand has settled into the pose.
    if sample is not None and elapsed >= CALIBRATION_SETTLE_TIME:
        calibration_samples[name].append(sample)

    if elapsed >= step_time:
        calibration_step += 1
        calibration_step_start = now

        if calibration_step == len(calibration_steps):
            calibration_step = None
            if "reach" in calibration_samples:
                finish_reach_calibration(now)
            else:
                finish_calibration(now)
            return None

    remaining = step_time - elapsed
    return f"CALIBRATE: {instruction} ({remaining:.0f}s)"


def finish_calibration(now):
    if not calibration_samples["open"] or not calibration_samples["pinch"]:
        show_message("Calibration failed: keep your hand in view", now)
        return

    # Medians ignore the odd misread frame.
    open_ratio = statistics.median(calibration_samples["open"])
    pinch_ratio = statistics.median(calibration_samples["pinch"])

    if open_ratio - pinch_ratio < 0.1:
        show_message("Calibration failed: poses too similar, try again", now)
        return

    apply_calibration(open_ratio, pinch_ratio)
    save_calibration(open=open_ratio, pinch=pinch_ratio)

    show_message(
        f"Calibrated: pinch below {PINCH_START:.2f}, "
        f"release above {PINCH_RELEASE:.2f}",
        now
    )


def reach_region(samples):
    """The area covered by fingertip samples, ignoring the outermost
    few percent as stray detections."""
    xs = statistics.quantiles([x for x, _ in samples], n=100)
    ys = statistics.quantiles([y for _, y in samples], n=100)
    return check_region((
        clamp(xs[2], 0.0, 1.0), clamp(ys[2], 0.0, 1.0),
        clamp(xs[96], 0.0, 1.0), clamp(ys[96], 0.0, 1.0)
    ))


def finish_reach_calibration(now):
    global active_region

    samples = calibration_samples["reach"]
    if len(samples) < 20:
        show_message("Calibration failed: keep your hand in view", now)
        return

    try:
        active_region = reach_region(samples)
    except ValueError:
        show_message("Calibration failed: move your finger farther", now)
        return

    save_calibration(region=list(active_region))
    show_message("Reach calibrated: that area now covers the screen", now)


def scale_region(factor, now):
    global active_region

    # Grow or shrink around the center, staying inside the frame. A
    # smaller region means less hand movement per screen width.
    left, top, right, bottom = active_region
    half_w = clamp((right - left) / 2 * factor, 0.1, 0.5)
    half_h = clamp((bottom - top) / 2 * factor, 0.1, 0.5)
    center_x = clamp((left + right) / 2, half_w, 1 - half_w)
    center_y = clamp((top + bottom) / 2, half_h, 1 - half_h)

    active_region = (
        center_x - half_w, center_y - half_h,
        center_x + half_w, center_y + half_h
    )
    save_calibration(region=list(active_region))
    show_message(f"Sensitivity: {1 / (2 * half_w):.2f}x", now)


def set_smoothing(min_cutoff, now):
    global MIN_CUTOFF

    MIN_CUTOFF = clamp(min_cutoff, 0.05, 5.0)
    apply_filter_settings()
    save_calibration(min_cutoff=MIN_CUTOFF)
    show_message(f"Smoothing: {MIN_CUTOFF:.2f} (lower = steadier)", now)


def reset_sensitivity(now):
    global active_region

    active_region = (
        FRAME_MARGIN_X, FRAME_MARGIN_Y,
        1 - FRAME_MARGIN_X, 1 - FRAME_MARGIN_Y
    )
    set_smoothing(default_min_cutoff, now)
    save_calibration(region=None, min_cutoff=None)
    show_message("Sensitivity and smoothing reset", now)


# ---------------- DISPLAY ----------------

FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE = (255, 255, 255)


def draw_text(frame, text, origin, scale=0.65, color=WHITE, thickness=2):
    # A dark outline keeps text readable on bright backgrounds.
    cv2.putText(frame, text, origin, FONT, scale, (0, 0, 0),
                thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, origin, FONT, scale, color,
                thickness, cv2.LINE_AA)


def draw_right(frame, text, y, scale=0.6, color=WHITE):
    (text_w, _), _ = cv2.getTextSize(text, FONT, scale, 2)
    draw_text(frame, text, (frame.shape[1] - text_w - 15, y), scale, color)


def draw_progress(frame, progress, color):
    x, y, w, h = 20, 82, 220, 8
    cv2.rectangle(frame, (x, y), (x + w, y + h), WHITE, 1)
    cv2.rectangle(frame, (x, y), (x + int(w * progress), y + h), color, -1)


def draw_panel(frame, lines, top):
    # Translucent box behind a list of lines.
    height = 19 * len(lines) + 12
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, top), (frame.shape[1] - 10, top + height),
                  (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    for row, line in enumerate(lines):
        cv2.putText(frame, line, (20, top + 22 + 19 * row), FONT, 0.45,
                    WHITE, 1, cv2.LINE_AA)


def help_lines():
    lines = [
        f"Profile: {current_profile()}",
        "Point: move cursor",
        "Pinch thumb+index: click (twice quickly: double-click)",
        "Index up, pinch thumb+middle: right-click",
        "Peace sign, move up/down: scroll",
        "Open palm, then fist: grab. Open palm: drop",
        "Pinch both hands, move apart/together: zoom",
        "Both palms open (hold): pause / resume",
    ]

    for gesture, name in GESTURE_NAMES.items():
        entry = action_for(gesture)
        if entry is not None and entry["parsed"][0] != "none":
            lines.append(f"{name}: {entry['label']}")

    lines += [
        "Keys: P pause  M profile  H help  D debug  L landmarks  Q quit",
        "      +/- sensitivity  [ ] smoothing  0 reset",
        "      C calibrate pinch  R calibrate reach",
    ]
    return lines


def draw_hud(frame, status, color, ratio_text, fps, process_ms, now):
    height, width = frame.shape[:2]

    if paused:
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), (0, 0, 255), 6)

    draw_text(frame, status, (20, 35),
              0.8 if len(status) < 30 else 0.55, color)
    draw_text(frame, ratio_text, (20, 70))

    if hud_warning:
        draw_text(frame, hud_warning, (20, 118), 0.55, (0, 140, 255))

    draw_right(frame, f"FPS: {fps:.0f}  {process_ms:.0f} ms", 35)
    draw_right(frame, f"Profile: {current_profile()}", 62, 0.55, (255, 220, 120))

    if now < action_until:
        (text_w, _), _ = cv2.getTextSize(action_text, FONT, 1.0, 2)
        draw_text(frame, action_text, ((width - text_w) // 2, height - 60),
                  1.0, (0, 255, 0))

    if show_help:
        draw_panel(frame, help_lines(), 90)
    elif show_debug:
        draw_panel(frame, debug_lines, 130)

    draw_text(
        frame, "H = help   P = pause   Q = quit", (20, height - 20),
        0.55, WHITE, 1
    )


def measure_brightness(frame, previous):
    small = cv2.resize(frame, (32, 24), interpolation=cv2.INTER_AREA)
    value = float(small.mean())
    if previous is None:
        return value
    return previous + 0.1 * (value - previous)


# ---------------- GESTURE LOGIC ----------------

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils


def process_hands(frame, found, width, height, now):
    """Runs the gesture logic for a frame with at least one hand.
    Returns (status, color, ratio text, calibration sample)."""
    global last_mode_time, click_lock_until, click_lock_point
    global hud_warning, debug_lines

    hand = pick_primary_hand(found)
    points = hand.landmark

    if SHOW_LANDMARKS:
        for each in found:
            mp_draw.draw_landmarks(frame, each, mp_hands.HAND_CONNECTIONS)

    status = "Show hand"
    ratio_text = "Pinch ratio: --"
    color = WHITE
    sample = None
    both_pinched = False

    index_tip = points[8]
    hand_size, ratio = measure_hand(points, width, height)
    in_view = hand_in_view(points)

    gesture = None
    if hand_size > 1.0:
        gesture = classify_pose(points, hand_size, width, height)

    if not in_view:
        hud_warning = "Keep your whole hand inside the frame"

    # The other hand is used for zooming and the pause gesture.
    other_points = None
    other_gesture = None
    if len(found) > 1:
        other = found[1] if hand is found[0] else found[0]
        other_points = other.landmark
        other_size, other_ratio = measure_hand(other_points, width, height)

        if other_size > 1.0:
            other_gesture = classify_pose(
                other_points, other_size, width, height
            )

        # Zooming is only available outside drag and drop.
        both_pinched = (
            hand_size > 1.0
            and other_ratio is not None
            and grab_state == "idle"
            and hand_pinched(ratio)
            and hand_pinched(other_ratio)
        )

    if show_debug:
        debug_lines = [
            f"Pose: {gesture}   other hand: {other_gesture}",
            f"Fingers: {finger_states(points, width, height)}",
            f"Hand size: {hand_size:.0f} px   in view: {in_view}",
        ]

    # Both palms open and held: pause or resume. Checked before
    # anything else so it also works while paused.
    both_palms = gesture == "palm" and other_gesture == "palm"
    if calibration_step is None and pause_hold.update(
        both_palms, now, PAUSE_HOLD_TIME
    ):
        set_paused(not paused, now)

    if paused:
        progress = pause_hold.progress(now, PAUSE_HOLD_TIME)
        if progress > 0:
            draw_progress(frame, progress, (0, 255, 0))
        return (
            "PAUSED - hold both palms open to resume",
            (0, 0, 255), "", None
        )

    if calibration_step is None:
        update_zoom_mode(both_pinched)

    if gesture is not None and calibration_step is None:
        update_grab(gesture)

        # Scrolling and swiping are only available outside drag and drop.
        if grab_state == "idle":
            update_scroll_mode(gesture == "peace")
            update_swipe_mode(gesture == "three")
        else:
            reset_scroll()
            reset_swipe()

    # Held poses only count outside other modes, with the whole hand
    # in view so a half-seen hand cannot trigger them.
    free = (
        gesture is not None
        and calibration_step is None
        and grab_state == "idle"
        and not (zooming or both_pinched or scrolling or swiping)
        and in_view
    )
    if thumbs_hold.update(free and gesture == "thumbs_up", now, POSE_HOLD_TIME):
        run_gesture_action("thumbs_up", now)
    if rock_hold.update(free and gesture == "rock", now, PROFILE_HOLD_TIME):
        run_gesture_action("rock", now)

    if hand_size <= 1.0:
        status = "Adjust hand position"

    elif calibration_step is not None:
        # Gestures are paused while measuring the hand.
        sample = (ratio, (index_tip.x, index_tip.y))
        ratio_text = f"Pinch ratio: {ratio:.2f}"

    elif grab_state != "idle":
        # 4. Drag and drop (the palm steers, it stays put
        # while the fingers curl)
        move_cursor(points, PALM_CENTER, now)
        reset_click()
        last_mode_time = now

        if grab_state == "dragging":
            status = "DRAGGING - open palm to drop"
            color = (0, 0, 255)
        else:
            status = "READY - close fist to grab"
            color = (255, 128, 0)

        palm = points[PALM_CENTER]
        cv2.circle(
            frame,
            (int(palm.x * width), int(palm.y * height)),
            16, color, -1 if grab_state == "dragging" else 2
        )

    elif zooming or both_pinched:
        # 5. Zoom (cursor and clicks paused; apps zoom
        # around the cursor)
        hold_click()
        reset_scroll()
        last_mode_time = now

        if zooming and both_pinched:
            zoom_with(
                points, hand_size,
                other_points, other_size,
                width, height
            )

        if zooming:
            status = "ZOOM - move hands apart or together"
            color = (255, 0, 128)
        else:
            status = "Hold both pinches to zoom"
            color = (0, 255, 255)

        if other_points is not None:
            a = pinch_point(points, width, height)
            b = pinch_point(other_points, width, height)
            a = (int(a[0]), int(a[1]))
            b = (int(b[0]), int(b[1]))
            cv2.line(frame, a, b, color, 2)
            cv2.circle(frame, a, 10, color, -1)
            cv2.circle(frame, b, 10, color, -1)

    elif scrolling:
        # 3. Scrolling (cursor and clicks paused)
        scroll_with(points)
        reset_click()
        last_mode_time = now

        status = "SCROLL"
        color = (255, 255, 0)

        for tip in (points[8], points[12]):
            cv2.circle(
                frame,
                (int(tip.x * width), int(tip.y * height)),
                10, color, 2
            )

    elif swiping:
        # 6. Swipes (cursor and clicks paused)
        reset_click()
        last_mode_time = now

        swipe = swipe_with(points, hand_size, width, height, now)
        if swipe:
            run_gesture_action(swipe, now)

        status = "SWIPE - flick left, right, up or down"
        color = (255, 200, 0)

        trail = [(int(x), int(y)) for _, x, y in swipe_history]
        for start, end in zip(trail, trail[1:]):
            cv2.line(frame, start, end, color, 3)
        palm = points[PALM_CENTER]
        cv2.circle(
            frame, (int(palm.x * width), int(palm.y * height)),
            12, color, 2
        )

    elif gesture in ("thumbs_up", "rock"):
        # 7. Held poses (cursor and clicks paused)
        reset_click()
        last_mode_time = now

        if gesture == "thumbs_up":
            hold, hold_time = thumbs_hold, POSE_HOLD_TIME
        else:
            hold, hold_time = rock_hold, PROFILE_HOLD_TIME

        entry = action_for(gesture)
        label = entry["label"] if entry else "no action"
        status = f"{GESTURE_NAMES[gesture]}: {label}"
        color = (0, 255, 0) if hold.fired else (255, 0, 255)

        progress = hold.progress(now, hold_time)
        if progress > 0:
            draw_progress(frame, progress, color)

    elif gesture == "fist":
        # A fist without an open palm first does nothing,
        # and must not be read as a pinch.
        reset_click()
        last_mode_time = now
        status = "Open palm first to drag"

    else:
        # 1. Cursor movement (held still while pinching, and for a
        # moment after a click in case a second click follows)
        right_ratio = right_pinch_ratio(points, hand_size, width, height)
        aim_ratio = ratio if right_ratio is None else min(ratio, right_ratio)

        if now < click_lock_until:
            moved = math.hypot(
                index_tip.x - click_lock_point[0],
                (index_tip.y - click_lock_point[1]) * height / width
            )
            if moved > CLICK_LOCK_MOVE:
                click_lock_until = 0.0
        locked = now < click_lock_until

        if not pinching and aim_ratio >= FREEZE_RATIO and not locked:
            move_cursor(points, INDEX_TIP, now)

        # 2. Pinch detection (left, right and double-click)
        clicked = detect_click(
            ratio, right_ratio, now,
            allowed=now - last_mode_time >= MODE_SETTLE_TIME
        )

        if clicked == "left":
            click_lock_until = now + double_click_time()
            click_lock_point = (index_tip.x, index_tip.y)
            show_action("Click", now, 0.6)
        elif clicked == "double":
            click_lock_until = 0.0
            show_action("Double-click", now)
        elif clicked == "right":
            show_action("Right-click", now)

        ratio_text = f"Pinch ratio: {ratio:.2f}"
        if right_ratio is not None:
            ratio_text += f"   middle: {right_ratio:.2f}"

        if pinching:
            status = "RIGHT PINCH" if pinch_button == "right" else "PINCH"
            color = (0, 255, 0)
        elif aim_ratio < FREEZE_RATIO:
            status = "AIMING"
            color = (0, 255, 255)
        elif locked:
            status = "Pinch again to double-click"
            color = (0, 255, 128)
        else:
            status = "MOVING"
            color = (0, 165, 255)

        if ratio < PINCH_START:
            cv2.circle(
                frame,
                (int(index_tip.x * width), int(index_tip.y * height)),
                12, color, 2
            )
        elif right_ratio is not None and right_ratio < PINCH_START:
            middle_tip = points[12]
            cv2.circle(
                frame,
                (int(middle_tip.x * width), int(middle_tip.y * height)),
                12, color, 2
            )

    # Show progress toward pausing over whatever else is happening.
    progress = pause_hold.progress(now, PAUSE_HOLD_TIME)
    if progress > 0:
        status = "Keep both palms open to pause"
        color = (0, 0, 255)
        draw_progress(frame, progress, color)

    return status, color, ratio_text, sample


# ---------------- MAIN LOOP ----------------

def handle_key(key, now):
    """Handles a key pressed in the camera window. Returns False to quit."""
    global show_help, show_debug, SHOW_LANDMARKS

    if key in (ord("q"), 27):
        return False

    if key == ord("p"):
        set_paused(not paused, now)
    elif key == ord("m"):
        switch_profile("next", now)
    elif key == ord("h"):
        show_help = not show_help
    elif key == ord("d"):
        show_debug = not show_debug
    elif key == ord("l"):
        SHOW_LANDMARKS = not SHOW_LANDMARKS
    elif key in (ord("+"), ord("=")):
        scale_region(SENSITIVITY_STEP, now)
    elif key in (ord("-"), ord("_")):
        scale_region(1 / SENSITIVITY_STEP, now)
    elif key == ord("["):
        set_smoothing(MIN_CUTOFF / SMOOTHING_STEP, now)
    elif key == ord("]"):
        set_smoothing(MIN_CUTOFF * SMOOTHING_STEP, now)
    elif key == ord("0"):
        reset_sensitivity(now)
    elif key in (ord("c"), ord("r")) and calibration_step is None:
        # Let go of anything held before measuring.
        reset_tracking()
        start_calibration(
            CALIBRATION_STEPS if key == ord("c") else REACH_STEPS, now
        )

    return True


def main():
    global lost_frames, hud_warning

    load_settings()
    load_calibration()
    apply_filter_settings()

    camera = CameraReader(CAMERA_INDEX)
    if not camera.open():
        raise SystemExit(
            f"Cannot open webcam {CAMERA_INDEX}. Close other apps using "
            "the camera, or set CAMERA_INDEX in settings.json."
        )

    camera.start()
    cursor_mover.start()

    cv2.namedWindow(WINDOW_NAME)
    if ALWAYS_ON_TOP:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)

    print(f"AirControl started, profile: {current_profile()}")
    if user32 is not None and GLOBAL_HOTKEYS:
        print("Ctrl+Alt+P pauses, Ctrl+Alt+Q quits from anywhere.")

    fps = 0.0
    process_ms = 0.0
    brightness = None
    frame_id = 0
    last_frame_time = time.monotonic()

    try:
        with mp_hands.Hands(
            max_num_hands=2,
            model_complexity=MODEL_COMPLEXITY,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        ) as hands:

            while True:
                frame_id, frame = camera.read(frame_id, timeout=0.5)
                now = time.monotonic()
                hud_warning = ""

                if cursor_mover.failsafe:
                    raise pyautogui.FailSafeException()

                if frame is None:
                    # No picture: let go of everything until it is back.
                    reset_tracking()
                    frame = np.zeros((CAMERA_H, CAMERA_W, 3), np.uint8)
                    height, width = frame.shape[:2]
                    status = (
                        "Waiting for camera..." if frame_id == 0
                        else "Camera not responding - reconnecting..."
                    )
                    color = (0, 0, 255)
                    ratio_text = ""

                else:
                    # Smoothed frames per second, shown on screen.
                    frame_time = now - last_frame_time
                    last_frame_time = now
                    if frame_time > 0:
                        fps += 0.1 * (1.0 / frame_time - fps)

                    frame = cv2.flip(frame, 1)
                    height, width = frame.shape[:2]

                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Lets MediaPipe use the frame without copying it.
                    rgb.flags.writeable = False
                    started = time.perf_counter()
                    results = hands.process(rgb)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    process_ms += 0.1 * (elapsed_ms - process_ms)

                    brightness = measure_brightness(frame, brightness)
                    sample = None

                    # Show the active region that maps to the screen.
                    left, top, right, bottom = active_region
                    cv2.rectangle(
                        frame,
                        (int(left * width), int(top * height)),
                        (int(right * width), int(bottom * height)),
                        (255, 0, 255), 1
                    )

                    if results.multi_hand_landmarks:
                        lost_frames = 0
                        status, color, ratio_text, sample = process_hands(
                            frame, results.multi_hand_landmarks,
                            width, height, now
                        )

                    else:
                        status = (
                            "PAUSED - hold both palms open to resume"
                            if paused else "Show hand"
                        )
                        color = (0, 0, 255) if paused else WHITE
                        ratio_text = "Pinch ratio: --"

                        # Let held poses run out, and reset the cursor
                        # filter after tracking is lost.
                        for hold in (pause_hold, thumbs_hold, rock_hold):
                            hold.update(False, now, 0.0)

                        lost_frames += 1
                        if lost_frames >= TRACKING_LOST_FRAMES:
                            reset_tracking()

                    if brightness < LOW_LIGHT_LEVEL:
                        hud_warning = "Low light: face a light source"

                    if calibration_step is not None:
                        ratio, tip = sample if sample else (None, None)
                        calibration_status = update_calibration(ratio, tip, now)
                        if calibration_status:
                            status = calibration_status
                            color = (255, 0, 255)

                        # Show the area covered so far.
                        reach = calibration_samples.get("reach")
                        if calibration_step is not None and reach:
                            xs = [x for x, _ in reach]
                            ys = [y for _, y in reach]
                            cv2.rectangle(
                                frame,
                                (int(min(xs) * width), int(min(ys) * height)),
                                (int(max(xs) * width), int(max(ys) * height)),
                                (0, 255, 0), 2
                            )

                if now < message_until:
                    status = message
                    color = (255, 0, 255)

                draw_hud(frame, status, color, ratio_text, fps, process_ms, now)
                cv2.imshow(WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key != 0xFF and not handle_key(key, now):
                    break

                hotkey = poll_global_hotkeys()
                if hotkey == "q":
                    break
                if hotkey == "p":
                    set_paused(not paused, now)

                # Closing the window quits too.
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break

    except pyautogui.FailSafeException:
        print("Emergency stop triggered.")

    finally:
        # Release a held drag even if the fail-safe fired in a corner.
        pyautogui.FAILSAFE = False
        cursor_mover.stop()
        if cursor_mover.is_alive():
            cursor_mover.join(timeout=0.5)
        reset_grab()
        camera.stop()
        if camera.is_alive():
            camera.join(timeout=1.0)
        cv2.destroyAllWindows()
        print("AirControl stopped.")


if __name__ == "__main__":
    main()
