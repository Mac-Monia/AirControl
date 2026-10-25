
import cv2
import mediapipe as mp
import pyautogui
import math
import time
import json
import os
import threading
import statistics


# ---------------- CONFIGURATION ----------------

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

SCREEN_W, SCREEN_H = pyautogui.size()

# Camera
CAMERA_INDEX = 0
CAMERA_W = 640
CAMERA_H = 480
CAMERA_FPS = 30

# 1 = more accurate landmarks, 0 = faster (use 0 if the FPS shown
# on screen is below about 20)
MODEL_COMPLEXITY = 1

# Only this inner part of the camera frame is mapped to the screen,
# so the screen edges are reachable without the hand leaving the view.
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

# Pinch tuning: 3D distance relative to hand size
PINCH_START = 0.22
PINCH_RELEASE = 0.35

# Freeze the cursor as the fingers close so the click lands on target
FREEZE_RATIO = 0.30

# Require a short, stable gesture
PINCH_FRAMES_REQUIRED = 3
RELEASE_FRAMES_REQUIRED = 2
CLICK_COOLDOWN = 0.35

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

# Landmarks the cursor can follow
INDEX_TIP = 8
PALM_CENTER = 9
# How fast the cursor eases back to the fingertip after following the palm
OFFSET_DECAY = 0.85

# Frames without a hand before tracking is reset; avoids dropping a
# drag on a single missed detection.
TRACKING_LOST_FRAMES = 5

# Pinch calibration (press C): measures your hand and overrides the
# pinch thresholds above. Results are saved next to this script.
CALIBRATION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "calibration.json"
)
CALIBRATION_STEPS = (
    ("open", "Point with index finger, thumb relaxed"),
    ("pinch", "Pinch thumb and index together"),
)
# Seconds per step; the first part of each step is ignored while
# the hand settles.
CALIBRATION_STEP_TIME = 2.5
CALIBRATION_SETTLE_TIME = 1.0
# Where each threshold sits between your pinched (0) and open (1) ratio
CALIBRATION_START = 0.30
CALIBRATION_FREEZE = 0.45
CALIBRATION_RELEASE = 0.55

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

                if target is not None:
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

# ---------------- STATE ----------------

filter_x = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
filter_y = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
cursor_mover = CursorMover()
tracking_landmark = None
offset_x = 0.0
offset_y = 0.0
lost_frames = 0
primary_wrist = None  # last position of the hand that steers the cursor

pinch_frames = 0
release_frames = 0
pinching = False
click_armed = True
last_click_time = 0.0

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

calibration_step = None  # index into CALIBRATION_STEPS while running
calibration_step_start = 0.0
calibration_samples = {}
calibration_message = ""
calibration_message_until = 0.0

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


def map_to_screen(value, margin, size):
    # Stretch the active region of the frame to the full screen.
    span = 1.0 - 2 * margin
    normalized = clamp((value - margin) / span, 0.0, 1.0)
    return normalized * (size - 1)


def move_cursor(points, landmark, now):
    global tracking_landmark, offset_x, offset_y

    point = points[landmark]
    target_x = map_to_screen(point.x, FRAME_MARGIN_X, SCREEN_W)
    target_y = map_to_screen(point.y, FRAME_MARGIN_Y, SCREEN_H)

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

    filter_x.reset()
    filter_y.reset()
    tracking_landmark = None
    offset_x = 0.0
    offset_y = 0.0
    primary_wrist = None
    reset_click()
    reset_scroll()
    reset_grab()
    reset_zoom()


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
    global pinch_frames, release_frames, pinching, click_armed

    pinch_frames = 0
    release_frames = 0
    pinching = False
    click_armed = True


def hold_click():
    global pinch_frames, release_frames, pinching, click_armed

    # Treat the pinch as already used, so letting go of one hand
    # after zooming does not click.
    pinch_frames = 0
    release_frames = 0
    pinching = True
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


def is_peace_sign(points, width, height):
    return (
        finger_extended(points, 8, 6, width, height)
        and finger_extended(points, 12, 10, width, height)
        and finger_folded(points, 16, 14, width, height)
        and finger_folded(points, 20, 18, width, height)
    )


def is_open_palm(points, width, height):
    return all(
        finger_extended(points, tip, pip, width, height)
        for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18))
    )


def is_fist(points, width, height):
    return all(
        finger_folded(points, tip, pip, width, height)
        for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18))
    )


def update_grab(gesture):
    global grab_state, grab_pending, grab_frames

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


def apply_calibration(open_ratio, pinch_ratio):
    global PINCH_START, PINCH_RELEASE, FREEZE_RATIO

    gap = open_ratio - pinch_ratio
    PINCH_START = pinch_ratio + CALIBRATION_START * gap
    FREEZE_RATIO = pinch_ratio + CALIBRATION_FREEZE * gap
    PINCH_RELEASE = pinch_ratio + CALIBRATION_RELEASE * gap


def load_calibration():
    try:
        with open(CALIBRATION_FILE) as file:
            data = json.load(file)
        apply_calibration(float(data["open"]), float(data["pinch"]))
        print(
            f"Loaded calibration: pinch below {PINCH_START:.2f}, "
            f"release above {PINCH_RELEASE:.2f}"
        )
    except FileNotFoundError:
        pass
    except (ValueError, KeyError, TypeError):
        print("Ignoring invalid calibration file.")


def start_calibration(now):
    global calibration_step, calibration_step_start, calibration_samples

    calibration_step = 0
    calibration_step_start = now
    calibration_samples = {name: [] for name, _ in CALIBRATION_STEPS}


def show_message(text, now, seconds=3.0):
    global calibration_message, calibration_message_until

    calibration_message = text
    calibration_message_until = now + seconds
    print(text)


def update_calibration(ratio, now):
    global calibration_step, calibration_step_start

    name, instruction = CALIBRATION_STEPS[calibration_step]
    elapsed = now - calibration_step_start

    # Only sample once the hand has settled into the pose.
    if ratio is not None and elapsed >= CALIBRATION_SETTLE_TIME:
        calibration_samples[name].append(ratio)

    if elapsed >= CALIBRATION_STEP_TIME:
        calibration_step += 1
        calibration_step_start = now

        if calibration_step == len(CALIBRATION_STEPS):
            calibration_step = None
            finish_calibration(now)
            return None

    remaining = CALIBRATION_STEP_TIME - elapsed
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

    with open(CALIBRATION_FILE, "w") as file:
        json.dump({"open": open_ratio, "pinch": pinch_ratio}, file, indent=2)

    show_message(
        f"Calibrated: pinch below {PINCH_START:.2f}, "
        f"release above {PINCH_RELEASE:.2f}",
        now
    )


def detect_click(ratio, now):
    global pinch_frames, release_frames
    global pinching, click_armed, last_click_time

    # Different thresholds prevent rapid state switching.
    if pinching:
        pinch_detected = ratio < PINCH_RELEASE
    else:
        pinch_detected = ratio < PINCH_START

    if pinch_detected:
        pinch_frames += 1
        release_frames = 0
    else:
        release_frames += 1
        pinch_frames = 0

    # Confirm the pinch before clicking.
    if not pinching and pinch_frames >= PINCH_FRAMES_REQUIRED:
        pinching = True

        if click_armed and now - last_click_time >= CLICK_COOLDOWN:
            pyautogui.click()
            last_click_time = now
            click_armed = False
            print("CLICK")

    # A deliberate release enables the next click.
    if pinching and release_frames >= RELEASE_FRAMES_REQUIRED:
        pinching = False
        click_armed = True


# ---------------- CAMERA ----------------

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

camera = cv2.VideoCapture(CAMERA_INDEX)

if not camera.isOpened():
    raise SystemExit("Cannot open webcam.")

camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_W)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)
camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
# Always process the newest frame to keep latency low.
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

load_calibration()
cursor_mover.start()

fps = 0.0
last_frame_time = time.monotonic()

try:
    with mp_hands.Hands(
        max_num_hands=2,
        model_complexity=MODEL_COMPLEXITY,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    ) as hands:

        while True:
            ok, frame = camera.read()

            if not ok:
                break

            now = time.monotonic()

            # Smoothed frames per second, shown on screen.
            frame_time = now - last_frame_time
            last_frame_time = now
            if frame_time > 0:
                fps += 0.1 * (1.0 / frame_time - fps)

            if cursor_mover.failsafe:
                raise pyautogui.FailSafeException()

            frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Lets MediaPipe use the frame without copying it.
            rgb.flags.writeable = False
            results = hands.process(rgb)

            status = "Show hand"
            ratio_text = "Pinch ratio: --"
            color = (255, 255, 255)
            calibration_ratio = None
            both_pinched = False

            # Show the active region that maps to the screen.
            cv2.rectangle(
                frame,
                (int(FRAME_MARGIN_X * width), int(FRAME_MARGIN_Y * height)),
                (
                    int((1 - FRAME_MARGIN_X) * width),
                    int((1 - FRAME_MARGIN_Y) * height)
                ),
                (255, 0, 255), 1
            )

            if results.multi_hand_landmarks:
                lost_frames = 0
                found = results.multi_hand_landmarks
                hand = pick_primary_hand(found)
                points = hand.landmark

                for each in found:
                    mp_draw.draw_landmarks(
                        frame, each, mp_hands.HAND_CONNECTIONS
                    )

                index_tip = points[8]
                hand_size, ratio = measure_hand(points, width, height)

                # The other hand is only used for zooming.
                other_points = None
                if len(found) > 1:
                    other = found[1] if hand is found[0] else found[0]
                    other_points = other.landmark
                    other_size, other_ratio = measure_hand(
                        other_points, width, height
                    )

                    # Zooming is only available outside drag and drop.
                    both_pinched = (
                        hand_size > 1.0
                        and other_ratio is not None
                        and grab_state == "idle"
                        and hand_pinched(ratio)
                        and hand_pinched(other_ratio)
                    )

                if calibration_step is None:
                    update_zoom_mode(both_pinched)

                if hand_size > 1.0 and calibration_step is None:
                    if is_open_palm(points, width, height):
                        gesture = "palm"
                    elif is_fist(points, width, height):
                        gesture = "fist"
                    elif is_peace_sign(points, width, height):
                        gesture = "peace"
                    else:
                        gesture = "other"

                    update_grab(gesture)

                    # Scrolling is only available outside drag and drop.
                    if grab_state == "idle":
                        update_scroll_mode(gesture == "peace")
                    else:
                        reset_scroll()

                if hand_size <= 1.0:
                    status = "Adjust hand position"

                elif calibration_step is not None:
                    # Gestures are paused while measuring the hand.
                    calibration_ratio = ratio
                    ratio_text = f"Pinch ratio: {ratio:.2f}"

                elif grab_state != "idle":
                    # 4. Drag and drop (the palm steers, it stays put
                    # while the fingers curl)
                    move_cursor(points, PALM_CENTER, now)
                    reset_click()

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

                    status = "SCROLL"
                    color = (255, 255, 0)

                    for tip in (points[8], points[12]):
                        cv2.circle(
                            frame,
                            (int(tip.x * width), int(tip.y * height)),
                            10, color, 2
                        )

                elif gesture == "fist":
                    # A fist without an open palm first does nothing,
                    # and must not be read as a pinch.
                    reset_click()
                    status = "Open palm first to drag"

                else:
                    # 1. Cursor movement (held still while pinching)
                    if not pinching and ratio >= FREEZE_RATIO:
                        move_cursor(points, INDEX_TIP, now)

                    # 2. Pinch detection
                    detect_click(ratio, now)

                    ratio_text = f"Pinch ratio: {ratio:.2f}"

                    if pinching:
                        status = "PINCH"
                        color = (0, 255, 0)
                    elif ratio < FREEZE_RATIO:
                        status = "AIMING"
                        color = (0, 255, 255)
                    else:
                        status = "MOVING"
                        color = (0, 165, 255)

                    if ratio < PINCH_START:
                        cv2.circle(
                            frame,
                            (
                                int(index_tip.x * width),
                                int(index_tip.y * height)
                            ),
                            12, color, 2
                        )

            else:
                # Reset the cursor filter after tracking is lost.
                lost_frames += 1
                if lost_frames >= TRACKING_LOST_FRAMES:
                    reset_tracking()

            if calibration_step is not None:
                calibration_status = update_calibration(calibration_ratio, now)
                if calibration_status:
                    status = calibration_status
                    color = (255, 0, 255)

            if now < calibration_message_until:
                status = calibration_message
                color = (255, 0, 255)

            cv2.putText(
                frame, status, (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8 if len(status) < 30 else 0.55, color, 2
            )

            cv2.putText(
                frame, ratio_text, (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2
            )

            cv2.putText(
                frame, f"FPS: {fps:.0f}", (width - 110, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2
            )

            cv2.putText(
                frame, "C = calibrate   Q = quit", (20, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1
            )

            cv2.imshow("AirControl", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("c") and calibration_step is None:
                # Let go of anything held before measuring.
                reset_click()
                reset_scroll()
                reset_grab()
                reset_zoom()
                start_calibration(now)

except pyautogui.FailSafeException:
    print("Emergency stop triggered.")

finally:
    # Release a held drag even if the fail-safe fired in a corner.
    pyautogui.FAILSAFE = False
    cursor_mover.stop()
    if cursor_mover.is_alive():
        cursor_mover.join(timeout=0.5)
    reset_grab()
    camera.release()
    cv2.destroyAllWindows()
    print("AirControl stopped.")
