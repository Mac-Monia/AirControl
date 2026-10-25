# AirControl

AirControl is a Python-based hand-tracking project that lets you control your computer's mouse cursor using hand gestures captured through a webcam.

The project uses MediaPipe for real-time hand landmark detection, OpenCV for webcam processing and visualization, and PyAutoGUI for mouse control.

## Features

- **Real-Time Hand Tracking:** Detects hand landmarks using a webcam.
- **Gesture-Based Cursor Control:** Moves the mouse cursor using the index fingertip.
- **Adaptive Cursor Smoothing:** Uses a One Euro filter: steady when your hand is still, responsive when it moves fast.
- **Active Region Mapping:** Maps an inner area of the camera frame to the full screen so edges are easy to reach.
- **Smooth Cursor Output:** Moves the cursor on its own thread, gliding between camera frames instead of jumping once per frame.
- **Pinch Calibration:** Press `C` to measure your own hand and set the click thresholds automatically.
- **Click Aim Lock:** Freezes the cursor as your fingers close so clicks land where you aimed.
- **Pinch-to-Click:** Simulates a mouse click when the thumb and index fingertip come together, measured in 3D relative to hand size.
- **Peace-Sign Scrolling:** Raise your index and middle fingers (ring and pinky folded) and move your hand up or down to scroll.
- **Drag and Drop:** Open your palm to get ready, close your fist to grab, and open your palm again to drop.
- **Two-Hand Pinch Zoom:** Pinch with both hands and move them apart to zoom in, or together to zoom out.
- **Click Stabilization:** Uses consecutive-frame confirmation and separate pinch and release thresholds to reduce accidental clicks.
- **Visual Feedback:** Displays hand landmarks, pinch status, and tracking information in a live camera window.
- **Emergency Fail-Safe:** Keeps PyAutoGUI's fail-safe enabled.

## Technologies

- Python
- OpenCV
- MediaPipe
- PyAutoGUI

## Prerequisites

Before running AirControl, make sure you have:

- Python installed.
- A working webcam.
- A desktop environment that supports mouse control.
- Git installed if you want to clone the repository.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Mac-Monia/AirControl.git
cd AirControl
```

### 2. Create a virtual environment

On Windows:

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

### 4. Install the dependencies

```bash
python -m pip install opencv-python mediapipe pyautogui
```

## Usage

### 1. Start AirControl

From the project directory, run:

```bash
python main.py
```

### 2. Control the cursor

Position your hand in front of the webcam.

- Move your index fingertip to move the mouse cursor.
- Bring your thumb and index fingertip together to trigger a mouse click.
- Release the pinch before performing another click.
- Make a peace sign (index and middle fingers up) and move your hand up or down to scroll. The cursor stays still while scrolling.
- To drag and drop: open your palm over the object, close your fist to grab it, move your hand, then open your palm to drop it. A fist on its own does nothing.
- To zoom: pinch your thumb and index finger on both hands, then move your hands apart to zoom in or closer together to zoom out. Release the pinches to stop. Zooming sends Ctrl + mouse wheel, so it works in browsers, image viewers, maps and most editors, and zooms around the cursor.

### 3. Calibrate the pinch (recommended on first run)

Press `C` and follow the prompts in the camera window:

1. Point with your index finger, thumb relaxed (2.5 seconds).
2. Pinch your thumb and index finger together (2.5 seconds).

The click thresholds are set from your hand and saved to `calibration.json`, which loads automatically next time. Recalibrate if clicks trigger too early or too late.

### 4. Exit the application

Press `Q` while the camera window is active.

## Configuration

AirControl's behavior can be adjusted by changing the configuration constants in `main.py`.

| Parameter                 | Description                                                     |
| ------------------------- | --------------------------------------------------------------- |
| `FRAME_MARGIN_X/Y`        | Size of the frame border excluded from screen mapping.          |
| `MIN_CUTOFF`              | Smoothing when the hand is still (lower = less jitter).         |
| `BETA`                    | Responsiveness during fast movement (higher = less lag).        |
| `FREEZE_RATIO`            | Pinch ratio below which the cursor stops moving to aim a click. |
| `MODEL_COMPLEXITY`        | 1 = more accurate, 0 = faster. Use 0 if the on-screen FPS is low. |
| `CURSOR_GLIDE`            | How quickly the cursor glides to its target (lower = snappier). |
| `PINCH_START`             | Determines the threshold for starting a pinch gesture.          |
| `PINCH_RELEASE`           | Determines the threshold for releasing a pinch.                 |
| `PINCH_FRAMES_REQUIRED`   | Sets how many consecutive frames are needed to confirm a pinch. |
| `RELEASE_FRAMES_REQUIRED` | Sets how many consecutive frames are needed to confirm release. |
| `CLICK_COOLDOWN`          | Sets the minimum interval between mouse clicks.                 |
| `SCROLL_SPEED`            | How far the page scrolls per hand movement.                     |
| `SCROLL_DEAD_ZONE`        | Ignores small hand movements while scrolling.                   |
| `SCROLL_INVERT`           | Reverses the scroll direction.                                  |
| `FINGER_EXTENDED_RATIO`   | How straight a finger must be to count as raised.               |
| `GRAB_FRAMES_REQUIRED`    | Frames a palm or fist must be held to grab or drop.             |
| `READY_EXIT_FRAMES`       | Frames of another gesture before drag mode is cancelled.        |
| `ZOOM_FRAMES_REQUIRED`    | Frames both hands must pinch before zooming starts.             |
| `ZOOM_EXIT_FRAMES`        | Frames without a two-hand pinch before zooming stops.           |
| `ZOOM_STEP`               | How far the hands must move per zoom step (lower = faster).     |
| `ZOOM_INVERT`             | Reverses the zoom direction.                                    |

### Tuning tips

- If the cursor is shaky while your hand is still, lower `MIN_CUTOFF`.
- If the cursor lags behind fast movements, increase `BETA` gradually.
- If you can't reach the screen edges, increase `FRAME_MARGIN_X/Y`; if the cursor is too sensitive, decrease them.
- If the cursor stops too early before a click, lower `FREEZE_RATIO` (keep it above `PINCH_START`).
- If pinching does not trigger a click, inspect the displayed pinch ratio and adjust the pinch thresholds.
- If accidental clicks occur, lower `PINCH_START` and test again.

Change one parameter at a time and test under consistent lighting and camera positioning.

## Safety

AirControl controls your actual mouse, so use it carefully.

- Keep `pyautogui.FAILSAFE = True`.
- Moving the cursor to the top-left corner of the screen can trigger PyAutoGUI's emergency fail-safe.
- Avoid running the application while performing sensitive operations.
- Close the application when you are finished testing.

## Project Structure

```text
AirControl/
├── .venv/             # Local virtual environment (not committed)
├── main.py            # Main hand-tracking and mouse-control logic
├── README.md          # Project documentation
└── .gitignore         # Files excluded from Git
```

The exact files in your repository may differ as development continues.

## Current Status

AirControl is under active development. Current work focuses on improving cursor stability, reducing tracking jitter, and making pinch-to-click interactions more reliable.

## Future Improvements

- Cursor calibration and configurable sensitivity.
- Improved pinch detection and click reliability.
- Support for additional hand gestures.
- Performance and usability improvements.

## Contributing

Contributions, suggestions, and bug reports are welcome.

If you want to improve AirControl, consider testing cursor accuracy, measuring click reliability, or improving the hand-tracking pipeline.

## License

No license has been specified yet.
