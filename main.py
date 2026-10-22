
import cv2
import mediapipe as mp
import pyautogui
import math
import time


# ---------------- CONFIGURATION ----------------

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

SCREEN_W, SCREEN_H = pyautogui.size()

# Cursor tuning
SMOOTHING = 0.18
DEAD_ZONE = 3.0

# Pinch tuning: distance relative to palm width
PINCH_START = 0.40
PINCH_RELEASE = 0.55

# Require a short, stable gesture
PINCH_FRAMES_REQUIRED = 2
RELEASE_FRAMES_REQUIRED = 2
CLICK_COOLDOWN = 0.35

# ---------------- STATE ----------------

cursor_x = None
cursor_y = None

pinch_frames = 0
release_frames = 0
pinching = False
click_armed = True
last_click_time = 0.0

# ---------------- HELPERS ----------------

def clamp(value, low, high):
    return max(low, min(value, high))


def landmark_distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def move_cursor(index_tip):
    global cursor_x, cursor_y

    # Map the fingertip to the full screen.
    target_x = index_tip.x * (SCREEN_W - 1)
    target_y = index_tip.y * (SCREEN_H - 1)

    if cursor_x is None:
        cursor_x = target_x
        cursor_y = target_y
    else:
        dx = target_x - cursor_x
        dy = target_y - cursor_y

        # Ignore small changes caused by landmark noise.
        if math.hypot(dx, dy) >= DEAD_ZONE:
            cursor_x += SMOOTHING * dx
            cursor_y += SMOOTHING * dy

    pyautogui.moveTo(
        round(clamp(cursor_x, 0, SCREEN_W - 1)),
        round(clamp(cursor_y, 0, SCREEN_H - 1))
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

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise SystemExit("Cannot open webcam.")

try:
    with mp_hands.Hands(
        max_num_hands=1,
        model_complexity=0,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.7
    ) as hands:

        while True:
            ok, frame = camera.read()

            if not ok:
                break

            frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            status = "Show hand"
            ratio_text = "Pinch ratio: --"
            color = (255, 255, 255)

            if results.multi_hand_landmarks:
                hand = results.multi_hand_landmarks[0]
                points = hand.landmark

                mp_draw.draw_landmarks(
                    frame, hand, mp_hands.HAND_CONNECTIONS
                )

                # 1. Cursor movement
                index_tip = points[8]
                move_cursor(index_tip)

                # 2. Pinch detection
                thumb_tip = points[4]

                # Width across the palm.
                palm_width = landmark_distance(
                    points[5], points[17]
                )

                pinch_distance = landmark_distance(
                    thumb_tip, index_tip
                )

                if palm_width > 0.001:
                    ratio = pinch_distance / palm_width

                    detect_click(ratio, time.monotonic())

                    ratio_text = f"Pinch ratio: {ratio:.2f}"

                    if pinching:
                        status = "PINCH"
                        color = (0, 255, 0)
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
                    status = "Adjust hand position"

            else:
                # Reset the cursor filter after tracking is lost.
                cursor_x = None
                cursor_y = None
                pinch_frames = 0
                release_frames = 0
                pinching = False
                click_armed = True

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
