
import cv2
import mediapipe as mp
import pyautogui
import math
import time


# ---------------- CONFIGURATION ----------------

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

SCREEN_W, SCREEN_H = pyautogui.size()

# Camera
CAMERA_INDEX = 0
CAMERA_W = 640
CAMERA_H = 480

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

# ---------------- STATE ----------------

filter_x = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
filter_y = OneEuroFilter(MIN_CUTOFF, BETA, DERIVATIVE_CUTOFF)
last_cursor = None

pinch_frames = 0
release_frames = 0
pinching = False
click_armed = True
last_click_time = 0.0

scroll_frames = 0
scrolling = False
scroll_anchor_y = None
scroll_remainder = 0.0

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


def move_cursor(index_tip, now):
    global last_cursor

    target_x = map_to_screen(index_tip.x, FRAME_MARGIN_X, SCREEN_W)
    target_y = map_to_screen(index_tip.y, FRAME_MARGIN_Y, SCREEN_H)

    x = filter_x(target_x, now)
    y = filter_y(target_y, now)

    position = (
        round(clamp(x, SCREEN_EDGE_PADDING, SCREEN_W - 1 - SCREEN_EDGE_PADDING)),
        round(clamp(y, SCREEN_EDGE_PADDING, SCREEN_H - 1 - SCREEN_EDGE_PADDING))
    )

    # Skip redundant OS calls when the cursor has not moved.
    if position != last_cursor:
        pyautogui.moveTo(*position)
        last_cursor = position


def reset_tracking():
    global last_cursor
    global pinch_frames, release_frames, pinching, click_armed

    filter_x.reset()
    filter_y.reset()
    last_cursor = None
    pinch_frames = 0
    release_frames = 0
    pinching = False
    click_armed = True
    reset_scroll()


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
# Always process the newest frame to keep latency low.
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

try:
    with mp_hands.Hands(
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    ) as hands:

        while True:
            ok, frame = camera.read()

            if not ok:
                break

            now = time.monotonic()

            frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Lets MediaPipe use the frame without copying it.
            rgb.flags.writeable = False
            results = hands.process(rgb)

            status = "Show hand"
            ratio_text = "Pinch ratio: --"
            color = (255, 255, 255)

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
                hand = results.multi_hand_landmarks[0]
                points = hand.landmark

                mp_draw.draw_landmarks(
                    frame, hand, mp_hands.HAND_CONNECTIONS
                )

                index_tip = points[8]
                thumb_tip = points[4]

                # Hand size: the larger of palm width and palm length,
                # so the ratio stays stable when the hand rotates.
                hand_size = max(
                    landmark_distance(points[5], points[17], width, height),
                    landmark_distance(points[0], points[9], width, height)
                )

                pinch_distance = landmark_distance(
                    thumb_tip, index_tip, width, height
                )

                if hand_size > 1.0:
                    ratio = pinch_distance / hand_size

                    update_scroll_mode(
                        is_peace_sign(points, width, height)
                    )

                if hand_size <= 1.0:
                    status = "Adjust hand position"

                elif scrolling:
                    # 3. Scrolling (cursor and clicks paused)
                    scroll_with(points)

                    pinch_frames = 0
                    release_frames = 0
                    pinching = False
                    click_armed = True

                    status = "SCROLL"
                    color = (255, 255, 0)

                    for tip in (points[8], points[12]):
                        cv2.circle(
                            frame,
                            (int(tip.x * width), int(tip.y * height)),
                            10, color, 2
                        )

                else:
                    # 1. Cursor movement (held still while pinching)
                    if not pinching and ratio >= FREEZE_RATIO:
                        move_cursor(index_tip, now)

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
                reset_tracking()

            cv2.putText(
                frame, status, (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
            )

            cv2.putText(
                frame, ratio_text, (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2
            )

            cv2.putText(
                frame, "Q = quit", (20, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1
            )

            cv2.imshow("AirControl", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

except pyautogui.FailSafeException:
    print("Emergency stop triggered.")

finally:
    camera.release()
    cv2.destroyAllWindows()
    print("AirControl stopped.")
