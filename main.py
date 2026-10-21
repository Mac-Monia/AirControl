
import pyautogui
import cv2
import mediapipe as mp

# Terminal output filtering
MOVEMENT_THRESHOLD = 0.02
previous_x = None
previous_y = None

# Higher alpha = more responsive cursor
SMOOTHING = 0.5
smooth_x = None
smooth_y = None

# Webcam control region (normalized coordinates)
FRAME_MARGIN_X = 0.10
FRAME_MARGIN_Y = 0.10

# Mouse setup
pyautogui.FAILSAFE = True
screen_width, screen_height = pyautogui.size()

# Initialize MediaPipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
)

# Open webcam
camera = cv2.VideoCapture(0)

# Request a modest resolution to reduce processing load
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not camera.isOpened():
    raise RuntimeError(
        "Could not open webcam. Check camera permissions "
        "and whether another app is using the camera."
    )

print("AirControl started. Press Q to quit.")

try:
    while True:
        success, frame = camera.read()

        if not success:
            print("Could not read a webcam frame.")
            break

        # Mirror the webcam image
        frame = cv2.flip(frame, 1)

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Avoid unnecessary image copies during processing
        rgb_frame.flags.writeable = False
        results = hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        hand_detected = results.multi_hand_landmarks is not None

        if hand_detected:
            hand_landmarks = results.multi_hand_landmarks[0]

            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
            )

            # Read the index fingertip (landmark 8)
            raw_x = hand_landmarks.landmark[8].x
            raw_y = hand_landmarks.landmark[8].y

            # Print only meaningful raw-coordinate changes
            if previous_x is None:
                print(
                    f"Index fingertip: "
                    f"x={raw_x:.3f}, y={raw_y:.3f}"
                )
                previous_x = raw_x
                previous_y = raw_y

            else:
                movement = (
                    (raw_x - previous_x) ** 2
                    + (raw_y - previous_y) ** 2
                ) ** 0.5

                if movement >= MOVEMENT_THRESHOLD:
                    print(
                        f"Index fingertip: "
                        f"x={raw_x:.3f}, y={raw_y:.3f}"
                    )
                    previous_x = raw_x
                    previous_y = raw_y

            # Smooth the fingertip position
            if smooth_x is None:
                smooth_x = raw_x
                smooth_y = raw_y
            else:
                smooth_x = (
                    SMOOTHING * raw_x
                    + (1 - SMOOTHING) * smooth_x
                )
                smooth_y = (
                    SMOOTHING * raw_y
                    + (1 - SMOOTHING) * smooth_y
                )

            # Restrict movement to the control region
            mapped_x = (smooth_x - FRAME_MARGIN_X) / (1 - 2 * FRAME_MARGIN_X)
            mapped_y = (smooth_y - FRAME_MARGIN_Y) / (1 - 2 * FRAME_MARGIN_Y)

            # Keep mapped coordinates between 0 and 1
            mapped_x = max(0.0, min(mapped_x, 1.0))
            mapped_y = max(0.0, min(mapped_y, 1.0))

            # Convert to screen pixels
            screen_x = int(mapped_x * (screen_width - 1))
            screen_y = int(mapped_y * (screen_height - 1))

            # Keep the cursor inside the screen
            screen_x = max(0, min(screen_x, screen_width - 1))
            screen_y = max(0, min(screen_y, screen_height - 1))

            # Move the cursor immediately
            pyautogui.moveTo(screen_x, screen_y, duration=0)

            status = "HAND DETECTED"

        else:
            status = "NO HAND DETECTED"

            # Reset tracking state when the hand disappears
            smooth_x = None
            smooth_y = None
            previous_x = None
            previous_y = None

        # Display tracking status
        cv2.putText(
            frame,
            status,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0) if hand_detected else (0, 0, 255),
            2,
        )

        cv2.imshow("AirControl - Hand Tracking", frame)

        # Press Q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    hands.close()
    cv2.destroyAllWindows()
