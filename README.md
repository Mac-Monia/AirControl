# AirControl

AirControl is a Python-based hand-tracking project that lets you control your computer's mouse cursor using hand gestures captured through a webcam.

The project uses MediaPipe for real-time hand landmark detection, OpenCV for webcam processing and visualization, and PyAutoGUI for mouse control.

## Features

- **Real-Time Hand Tracking:** Detects hand landmarks using a webcam.
- **Gesture-Based Cursor Control:** Moves the mouse cursor using the index fingertip.
- **Cursor Smoothing:** Applies exponential smoothing to reduce unwanted cursor movement.
- **Dead-Zone Filtering:** Ignores small movements to help reduce jitter.
- **Pinch-to-Click:** Simulates a mouse click when the thumb and index fingertip come together.
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

### 3. Exit the application

Press `Q` while the camera window is active.

## Configuration

AirControl's behavior can be adjusted by changing the configuration constants in `air_control.py`.

| Parameter                 | Description                                                     |
| ------------------------- | --------------------------------------------------------------- |
| `SMOOTHING`               | Controls how quickly the cursor follows the detected fingertip. |
| `DEAD_ZONE`               | Ignores small cursor-position changes.                          |
| `PINCH_START`             | Determines the threshold for starting a pinch gesture.          |
| `PINCH_RELEASE`           | Determines the threshold for releasing a pinch.                 |
| `PINCH_FRAMES_REQUIRED`   | Sets how many consecutive frames are needed to confirm a pinch. |
| `RELEASE_FRAMES_REQUIRED` | Sets how many consecutive frames are needed to confirm release. |
| `CLICK_COOLDOWN`          | Sets the minimum interval between mouse clicks.                 |

### Tuning tips

- If the cursor is too shaky, experiment with a smaller `SMOOTHING` value.
- If the cursor feels slow, increase `SMOOTHING gradually`.
- If small hand movements move the cursor too much, increase `DEAD_ZONE` slightly.
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
├── main.py     # Main hand-tracking and mouse-control logic
├── README.md          # Project documentation
└── .gitignore         # Files excluded from Git
```

The exact files in your repository may differ as development continues.

## Current Status

AirControl is under active development. Current work focuses on improving cursor stability, reducing tracking jitter, and making pinch-to-click interactions more reliable.

## Future Improvements

- More advanced cursor filtering, such as a One Euro filter.
- Cursor calibration and configurable sensitivity.
- Improved pinch detection and click reliability.
- Gesture-based scrolling and dragging.
- Support for additional hand gestures.
- Performance and usability improvements.

## Contributing

Contributions, suggestions, and bug reports are welcome.

If you want to improve AirControl, consider testing cursor accuracy, measuring click reliability, or improving the hand-tracking pipeline.

## License

No license has been specified yet.
